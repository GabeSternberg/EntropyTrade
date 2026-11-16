"""Bounded retained-history selection and causal verification; no network or execution access."""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.exchange.kalshi.recorded import public_book_from_body
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.experiments.data import ExperimentData
from entropytrade.families.public import forward_data as forward_data
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather
from entropytrade.research.paper_models import PortableResearchModel
from entropytrade.tracking.reconciliation import is_reconciliation
from entropytrade.tracking.replay import verify

if TYPE_CHECKING:
    from entropytrade.api.jobs import Jobs

PARTITION_SIZE = 128


def entries(jobs: "Jobs") -> list[dict[str, Any]]:
    with jobs.connect() as db:
        runs = db.execute(
            "SELECT id, created_at FROM jobs WHERE status='completed' "
            "AND json_extract(request, '$.family')='weather' "
            "AND json_extract(request, '$.mode')='public' ORDER BY created_at, id"
        ).fetchall()
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cycles = (
            db.execute(
                "SELECT c.id, c.monitor_id, c.started_at, "
                "json_extract(c.result, '$.cycle_mode') AS cycle_mode FROM shadow_cycles c "
                "JOIN monitors m ON m.id=c.monitor_id WHERE m.family='weather' "
                "AND c.status='completed' ORDER BY c.started_at, c.id"
            ).fetchall()
            if "shadow_cycles" in tables
            else []
        )
    return sorted(
        [{"id": r["id"], "kind": "public", "at": r["created_at"], "monitor_id": None} for r in runs]
        + [
            {
                "id": r["id"],
                "kind": "shadow",
                "at": r["started_at"],
                "monitor_id": r["monitor_id"],
                **({"outcome_only": True} if r["cycle_mode"] == "reconcile_only" else {}),
            }
            for r in cycles
        ],
        key=lambda r: (r["at"], r["kind"], r["id"]),
    )


def input_root(jobs: "Jobs", entry: dict[str, Any]) -> Path:
    from entropytrade.api.jobs import identifier

    if entry["kind"] == "public":
        return jobs.root / "runs" / identifier(entry["id"])
    return jobs.root / "shadow" / identifier(entry["monitor_id"]) / identifier(entry["id"])


def catalog(jobs: "Jobs") -> dict[str, Any]:
    rows = entries(jobs)
    partitions: list[dict[str, Any]] = []
    for offset in range(0, len(rows), PARTITION_SIZE):
        members = rows[offset : offset + PARTITION_SIZE]
        partitions.append(
            {
                "partition_id": scientific_hash(members).removeprefix("sha256:"),
                "number": len(partitions) + 1,
                "inputs": len(members),
                "shadow_cycles": sum(m["kind"] == "shadow" for m in members),
                "first_at": members[0]["at"],
                "last_at": members[-1]["at"],
                "members": members,
            }
        )
    return {"total_inputs": len(rows), "partition_size": PARTITION_SIZE, "partitions": partitions}


def anchor(jobs: "Jobs") -> date:
    """Read only checksummed market metadata globally; expensive feature work stays bounded.

    Selection of a later page must never create a later training/holdout boundary.
    """
    dates: list[date] = []
    for entry in entries(jobs):
        if entry.get("outcome_only"):
            continue
        root = input_root(jobs, entry) / "public"
        manifest = json.loads((root / "manifest.json").read_text())
        if (
            scientific_hash({k: v for k, v in manifest.items() if k != "dataset_version"})
            != manifest["dataset_version"]
        ):
            raise ValueError("history anchor manifest identity mismatch")
        if file_hash(root / "markets.jsonl") != manifest["checksums"]["markets.jsonl"]:
            raise ValueError("history anchor market checksum mismatch")
        for line in (root / "markets.jsonl").read_text().splitlines():
            target = MarketEvidence.model_validate_json(line).market.rules.settlement_target_date
            if target is not None:
                dates.append(target)
    if not dates:
        raise ValueError("No retained weather target dates")
    return min(dates)


def selected_inputs(
    jobs: "Jobs", partition_id: str | None, outcome_partition_id: str | None
) -> tuple[list[Path], list[Path], frozenset[str]]:
    partitions = catalog(jobs)["partitions"]
    if partition_id is None and len(partitions) > 1:
        raise ValueError("history exceeds 128 inputs; select a browser history partition")
    chosen = next((p for p in partitions if p["partition_id"] == partition_id), None)
    if partition_id is None:
        chosen = partitions[0] if partitions else {"members": []}
    if chosen is None:
        raise ValueError("history partition changed or is unknown; refresh the catalog")
    labels = (
        chosen
        if outcome_partition_id is None
        else next((p for p in partitions if p["partition_id"] == outcome_partition_id), None)
    )
    if labels is None:
        raise ValueError("outcome partition changed or is unknown; refresh the catalog")
    return member_inputs(jobs, chosen["members"], labels["members"])


def member_inputs(
    jobs: "Jobs", members: list[dict[str, Any]], label_members: list[dict[str, Any]]
) -> tuple[list[Path], list[Path], frozenset[str]]:
    """Verified capture/outcome roots and workspace-wide protection for catalog members.

    Members must come from `catalog`; callers may pass any bounded subset of one partition.
    """
    from entropytrade.api.recovery import check_artifacts

    if len(members) > PARTITION_SIZE or len(label_members) > PARTITION_SIZE:
        raise ValueError("history selection exceeds one bounded partition")
    captures = [input_root(jobs, e) / "public" for e in members if not e.get("outcome_only")]
    protected: set[str] = set()
    research_models: list[PortableResearchModel] = []
    # Protection belongs to the workspace, independent of the selected receipt page.
    with jobs.connect() as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        bindings = (
            db.execute("SELECT model_binding FROM monitors WHERE family='weather'")
            if "monitors" in tables
            else []
        )
        for row in bindings:
            binding = json.loads(row[0]) if row[0] else None
            if binding and binding.get("snapshot"):
                if scientific_hash(
                    {k: v for k, v in binding.items() if k != "binding_hash"}
                ) != binding.get("binding_hash"):
                    raise ValueError("history model protection hash mismatch")
                if binding.get("kind") == "research_weather_v1":
                    research_model = PortableResearchModel.model_validate(binding["snapshot"])
                    research_models.append(research_model)
                    protected.update(research_model.protected_events)
                else:
                    protected.update(
                        FrozenWeather.model_validate(binding["snapshot"]).protected_events
                    )
        selected = {e["id"]: e for e in members + label_members if e["kind"] == "shadow"}
        for entry in selected.values():
            row = db.execute(
                "SELECT result, digest FROM shadow_cycles WHERE id=?", (entry["id"],)
            ).fetchone()
            result = json.loads(row["result"])
            root = input_root(jobs, entry)
            if (
                scientific_hash(result) != row["digest"]
                or json.loads((root / "result.json").read_text()) != result
            ):
                raise ValueError("retained weather cycle differs from committed evidence")
            if is_reconciliation(result):
                from entropytrade.tracking.reconciliation import verify_reconciliation

                verify_reconciliation(root, result)
                continue
            if not {"public/manifest.json", "outcomes/summary.json", "decision-inputs.json"} <= {
                a["path"] for a in result["artifacts"]
            }:
                raise ValueError("retained weather cycle lacks committed replay evidence")
            check_artifacts(root, result["artifacts"])
            protected.update(
                ExperimentData.model_validate(
                    json.loads((root / "decision-inputs.json").read_text())["data"]
                ).protected_events
            )
    for capture in captures:
        for line in (capture / "markets.jsonl").read_text().splitlines():
            market = MarketEvidence.model_validate_json(line).market
            target = market.rules.settlement_target_date or ticker_target_date(market.ticker)
            if target is not None and any(
                model.protects(
                    series=market.series_ticker or "",
                    target_date=target,
                    event_id=market.event_ticker,
                )
                for model in research_models
            ):
                protected.add(market.event_ticker)
    outcomes = [input_root(jobs, entry) for entry in label_members if entry["kind"] == "shadow"]
    return captures, outcomes, frozenset(protected)


def verified_inputs(root: Path) -> dict[str, Any]:
    """Reproduce saved decisions AND bind every saved book to its original raw GET receipt."""
    result = json.loads((root / "result.json").read_text())
    if is_reconciliation(result):
        from entropytrade.tracking.reconciliation import verify_reconciliation

        return verify_reconciliation(root, result)
    verify(root)
    inputs: dict[str, Any] = json.loads((root / "decision-inputs.json").read_text())
    saved = ExperimentData.model_validate(inputs["data"])
    public = forward_data(root / "public")
    research = (result.get("model_binding") or {}).get("kind") == "research_weather_v1"
    if research:
        from entropytrade.tracking.research_features import reconstruct_research_data

        public = reconstruct_research_data(root, public, result, result["execution"])
    if (
        saved.dataset_version != public.dataset_version
        or saved.feature_version != public.feature_version
        or saved.data_kind != public.data_kind
    ):
        raise ValueError("shadow source version mismatch")
    result = json.loads((root / "result.json").read_text())
    summary = json.loads((root / "execution/summary.json").read_text())
    if (
        summary != result["execution"]
        or result["submission_enabled"] is not False
        or summary["submission_enabled"] is not False
        or result["dataset_version"] != saved.dataset_version
        or result["feature_version"] != saved.feature_version
    ):
        raise ValueError("shadow execution summary mismatch")
    at = datetime.fromisoformat(summary["decision_time"])
    originals = {s.ticker: s for s in public.samples}
    for sample in saved.samples:
        original = originals[sample.ticker]
        if research:
            features = original.features
            expected_hash = original.feature_hash
        else:
            features = {
                **original.features,
                "hours_to_close": Decimal(str((sample.close_time - at).total_seconds()))
                / Decimal(3600),
            }
            expected_hash = scientific_hash(
                {
                    "source_features": original.feature_hash,
                    "decision": at.isoformat(),
                    "features": {k: str(v) for k, v in features.items()},
                }
            )
        if (
            sample.decision_time != at
            or sample.features != features
            or sample.feature_hash != expected_hash
            or sample.features_available_at != original.features_available_at
            or sample.versions != original.versions
            or sample.sources != original.sources
            or sample.event_id != original.event_id
            or sample.close_time != original.close_time
            or sample.target_date != original.target_date
            or sample.family != original.family
            or sample.eligible != original.eligible
            or sample.rules_known
            != (original.rules_known and sample.ticker not in result["changed_terms"])
            or sample.outcome is not None
            or sample.outcome_available_at is not None
        ):
            raise ValueError("shadow decision clock/features differ from source receipts")
        if sample.book is None:
            continue
        receipts = [
            r
            for r in summary["receipts"]
            if r["status"] == 200
            and r["path"] == f"/trade-api/v2/markets/{sample.ticker}/orderbook"
        ]
        if len(receipts) != 1:
            raise ValueError("shadow book lacks unique successful receipt")
        receipt = receipts[0]
        path = root / receipt["raw_ref"]
        if (
            not path.resolve().is_relative_to(root.resolve())
            or file_hash(path) != receipt["sha256"]
        ):
            raise ValueError("shadow raw book checksum/path mismatch")
        book = public_book_from_body(
            json.loads(path.read_text()),
            ticker=sample.ticker,
            received_at=datetime.fromisoformat(receipt["received_at"]),
        )
        if (
            book != sample.book
            or book.received_at > at
            or (book.exchange_ts and book.exchange_ts > at)
        ):
            raise ValueError("shadow book differs from causal receipt")
    if research:
        from entropytrade.domain.strategy import StrategySpec
        from entropytrade.research.paper_models import score_research_model

        markets = {
            evidence.market.ticker: evidence.market
            for evidence in (
                MarketEvidence.model_validate_json(line)
                for line in (root / "public/markets.jsonl").read_text().splitlines()
            )
        }
        expected = score_research_model(
            StrategySpec.model_validate(inputs["spec"]), public, result["model_binding"], markets
        )
        if (
            inputs["bundle"]["records"]
            != [record.model_dump(mode="json") for record in expected.records]
            or inputs["bundle"]["source_hash"] != expected.source_hash
            or inputs["bundle"]["model_metadata"].get("original_metadata_hash")
            != scientific_hash(expected.model_metadata)
        ):
            raise ValueError("research paper predictions differ from frozen portable model")
    return inputs
