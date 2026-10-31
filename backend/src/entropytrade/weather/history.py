"""Immutable retained weather snapshots over original forward and shadow receipts.

No network, credential or execution access. Official binary results never manufacture
scalar weather labels. The first snapshot freezes calendar partitions for later snapshots.
"""

import json
import re
import shutil
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.dataset import make_rows
from entropytrade.data.schema import DatasetConfig, MarketEvidence, Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import (
    ContractSample,
    ExperimentData,
    PredictionBundle,
    weather_data,
)
from entropytrade.families.public import forward_data
from entropytrade.features.pipeline import build_features
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import temporal_plan
from entropytrade.ml.experiment import ModelingConfig, _examples
from entropytrade.weather.collection import WeatherConfig

SCHEMA = "retained-weather-v1"
MAX_INPUTS = 128
MAX_BYTES = 256_000_000
LIMITATIONS = [
    "Original receipt clocks are preserved; importing a receipt does not backfill availability.",
    "Hourly forecast maxima are proxies. Official binary outcomes do not supply scalar highs.",
    "Source-matched integer settlement highs, independent dates and timely labels gate fitting.",
    "No certified effective fees or executable historical depth; no empirical returns claimed.",
    "Protected final holdout is excluded from research, fitting and evaluation.",
]


def snapshot_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("select a retained weather dataset ID")
    return value


def _file(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or not path.resolve().is_relative_to(root.resolve())
        or any(p.is_symlink() for p in (path, *path.parents) if p != root.parent)
        or not path.is_file()
    ):
        raise ValueError("unsafe or missing retained weather input")
    return path


def load_snapshot(root: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(_file(root, "snapshot.json").read_text())
    if (
        manifest["schema"] != SCHEMA
        or scientific_hash(manifest["identity"]) != manifest["dataset_id"]
    ):
        raise ValueError("weather snapshot identity mismatch")
    identifier = manifest["dataset_id"].removeprefix("sha256:")
    if root.name not in {identifier, ".building-" + identifier}:
        raise ValueError("weather snapshot path/identity mismatch")
    checksums = manifest["checksums"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(checksums) | {"snapshot.json"}:
        raise ValueError("weather snapshot inventory mismatch")
    for name, digest in checksums.items():
        if file_hash(_file(root, name)) != digest:
            raise ValueError("weather snapshot checksum mismatch")
    features = root / manifest["features"]
    feature_manifest = json.loads(_file(root, manifest["features"] + "/manifest.json").read_text())
    if (
        scientific_hash({k: v for k, v in feature_manifest.items() if k != "feature_version"})
        != feature_manifest["feature_version"]
    ):
        raise ValueError("weather feature manifest identity mismatch")
    if (
        feature_manifest["temporal_boundaries"] != manifest["identity"]["temporal_boundaries"]
        or feature_manifest.get("protected_events", []) != manifest["identity"]["protected_events"]
    ):
        raise ValueError("weather snapshot protection mismatch")
    data = weather_data(features)
    if data.dataset_version != manifest["dataset_id"]:
        raise ValueError("weather snapshot feature lineage mismatch")
    if manifest["readiness"] != readiness(features):
        raise ValueError("weather snapshot readiness mismatch")
    return manifest


def readiness(features: Path) -> dict[str, Any]:
    manifest = json.loads((features / "manifest.json").read_text())
    rows = pq.read_table(features / "features.parquet").to_pylist()
    protected = set(manifest.get("protected_events", []))
    cuts = tuple(date.fromisoformat(d) for d in manifest["temporal_boundaries"])
    boundaries = (cuts[0], cuts[1], cuts[2])
    allowed = [
        r for r in rows if r["event_id"] not in protected and r["target_date"] < cuts[2].isoformat()
    ]
    try:
        plan = temporal_plan(rows, boundaries)
        partition_failure = None
    except ValueError as exc:
        plan = None
        partition_failure = str(exc)
    capture_audit = manifest.get("retained_capture_audit", [])
    counts = {
        "capture_failures": sum(len(c["failures"]) for c in capture_audit),
        "incomplete_captures": sum(not c["universe_complete"] for c in capture_audit),
        "rows": len(rows),
        "contracts": len({r["market_ticker"] for r in rows}),
        "independent_events": len({r["event_id"] for r in rows}),
        "date_blocks": len({r["target_date"] for r in rows}),
        "protected_events": len({r["event_id"] for r in rows} & protected),
        "eligible_events": len({r["event_id"] for r in allowed if r["feature_eligible"]}),
        "scalar_label_events": len(
            {r["event_id"] for r in allowed if r["temperature_target_f"] is not None}
        ),
        "binary_label_events": len({r["event_id"] for r in allowed if r["outcome"] is not None}),
    }
    blockers = []
    if counts["capture_failures"] or counts["incomplete_captures"]:
        blockers.append("Retained acquisition was incomplete; inspect original failure receipts")
    config = ModelingConfig()
    partitions: dict[str, Any] = {}
    for name, start, end, minimum in (
        ("fit", date.min, cuts[0], config.min_train_events),
        ("calibration", cuts[0], cuts[1], config.min_calibration_events),
        ("validation", cuts[1], cuts[2], config.min_evaluation_events),
    ):
        selected = [r for r in allowed if start.isoformat() <= r["target_date"] < end.isoformat()]
        ids = tuple(sorted({r["event_id"] for r in selected}))
        cutoff = (
            plan.fit_asof
            if plan is not None and name == "fit"
            else plan.calibration_asof
            if plan is not None and name == "calibration"
            else datetime.combine(end, datetime.min.time(), UTC)
        )
        examples = _examples(selected, ids, cutoff)
        count = len(examples)
        partitions[name] = {
            "events": len(ids),
            "dates": len({r["target_date"] for r in selected}),
            "timely_source_matched_events": count,
            "minimum_events": minimum,
            "shortage": max(0, minimum - count),
            "label_cutoff": cutoff.isoformat(),
        }
        if count < minimum:
            blockers.append(
                f"{name}: {count}/{minimum} independent source-matched events "
                f"available before {cutoff.isoformat()}"
            )
    if partition_failure:
        blockers.append(partition_failure)
    if plan and set(plan.fit + plan.calibration + plan.validation) & protected:
        blockers.append("Source-protected events overlap model partitions; fitting remains refused")
    if counts["eligible_events"] == 0:
        blockers.append("No complete known forecast with verified contract semantics")
    if counts["scalar_label_events"] == 0:
        blockers.append(
            "No source-matched integer settlement highs; binary results cannot substitute"
        )
    return {
        **counts,
        "status": "ready_for_model_gates" if not blockers else "insufficient_data",
        "capture_audit": capture_audit,
        **({"cohort": manifest["retained_cohort"]} if "retained_cohort" in manifest else {}),
        **(
            {"shadow_audit": manifest["retained_shadow_audit"]}
            if "retained_shadow_audit" in manifest
            else {}
        ),
        "partitions": partitions,
        "blockers": blockers,
        "temporal_boundaries": manifest["temporal_boundaries"],
        "limitations": [
            "Verified cycle-specific sized depth is retained; stale/missing books "
            "and uncertified fees refuse execution."
            if "retained_shadow_audit" in manifest and "executable historical depth" in line
            else line
            for line in LIMITATIONS
        ],
    }


def _observations(items: Sequence[Observation]) -> list[Observation]:
    unique: dict[str, Observation] = {}
    conflicts: dict[str, set[str]] = {}
    for item in items:
        payload = item.model_dump(mode="json")
        key = scientific_hash(
            {
                k: v
                for k, v in payload.items()
                if k not in {"raw_ref", "raw_hash", "available_at", "received_at", "ingested_at"}
            }
        )
        revision = scientific_hash(
            {
                k: payload[k]
                for k in (
                    "source_id",
                    "entity_id",
                    "model",
                    "variable",
                    "valid_at",
                    "valid_on",
                    "revision_id",
                )
            }
        )
        if item.revision_id:
            conflicts.setdefault(revision, set()).add(str(item.value))
        previous = unique.get(key)
        if previous is None or (
            item.available_at or datetime.max.replace(tzinfo=UTC),
            item.raw_ref,
        ) < (previous.available_at or datetime.max.replace(tzinfo=UTC), previous.raw_ref):
            unique[key] = item
    if any(len(values) > 1 for values in conflicts.values()):
        raise ValueError("conflicting values in one retained forecast revision")
    return sorted(unique.values(), key=lambda o: o.model_dump_json())


def build_snapshot(
    output: Path,
    captures: Sequence[Path],
    *,
    outcome_roots: Sequence[Path] = (),
    protected_events: frozenset[str] = frozenset(),
    frozen_anchor: date | None = None,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(captures) > MAX_INPUTS or len(outcome_roots) > MAX_INPUTS:
        raise ValueError(
            "weather history exceeds 128 inputs; select an operator-reviewed partition"
        )
    return _build_snapshot(
        output,
        captures,
        outcome_roots=outcome_roots,
        protected_events=protected_events,
        frozen_anchor=frozen_anchor,
        selection=selection,
    )


def _build_snapshot(
    output: Path,
    captures: Sequence[Path],
    *,
    outcome_roots: Sequence[Path],
    protected_events: frozenset[str],
    frozen_anchor: date | None,
    selection: dict[str, Any] | None,
) -> dict[str, Any]:
    """Shared assembly after bounded partition verification (including cohort batches)."""
    from entropytrade.tracking.worker import terms

    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("weather snapshot output cannot traverse symlinks")
    if not captures:
        raise ValueError(
            "No retained weather receipts. Fetch public weather sources "
            "or collect shadow cycles first"
        )
    from entropytrade.tracking.history import verified_inputs

    shadow: dict[str, tuple[Path, dict[str, Any]]] = {}
    shadow_captures: dict[Path, ExperimentData] = {}
    for capture_root in captures:
        if (capture_root.parent / "decision-inputs.json").is_file():
            inputs = verified_inputs(capture_root.parent)
            saved = ExperimentData.model_validate(inputs["data"])
            protected_events |= saved.protected_events
            shadow_captures[capture_root] = saved
            shadow[file_hash(capture_root.parent / "result.json")] = (capture_root.parent, inputs)
    unique: dict[str, Path] = {}
    for root in captures:
        data = forward_data(root)
        if data.provenance["capture"]["family"] != "weather":
            raise ValueError("weather snapshots cannot ingest another market family")
        unique[data.dataset_version] = root
    prior = [load_snapshot(p) for p in sorted(output.glob("[0-9a-f]" * 64))]
    partitions = {tuple(p["identity"]["temporal_boundaries"]) for p in prior}
    if len(partitions) > 1:
        raise ValueError("conflicting frozen weather partitions")
    for p in prior:
        protected_events |= frozenset(p["identity"]["protected_events"])
    markets: list[MarketEvidence] = []
    observed: list[Observation] = []
    decisions: dict[str, set[datetime]] = {}
    locations: dict[str, Any] = {}
    copies: dict[str, Path] = {}
    capture_audit = []
    for index, (_version, root) in enumerate(sorted(unique.items())):
        manifest = json.loads((root / "manifest.json").read_text())
        prefix = f"receipts/{index:04d}"
        capture = json.loads((root / "capture.json").read_text())
        capture_audit.append({"dataset_version": _version, **capture})
        for name in ["manifest.json", *manifest["checksums"]]:
            copies[prefix + "/" + name] = _file(root, name)
        config = WeatherConfig.model_validate(manifest["weather_config"])
        for location in config.locations:
            previous = locations.setdefault(location.series, location)
            if previous != location:
                raise ValueError("weather location configuration changed")
        at = datetime.fromisoformat(manifest["decision_time"])
        for line in (root / "markets.jsonl").read_text().splitlines():
            item = MarketEvidence.model_validate_json(line)
            markets.append(item.revalidated(raw_ref=prefix + "/" + item.raw_ref))
            if root not in shadow_captures and item.market.open_time <= at < item.market.close_time:
                decisions.setdefault(item.market.ticker, set()).add(at)
        observed.extend(
            Observation.model_validate_json(line).revalidated(
                raw_ref=prefix + "/" + Observation.model_validate_json(line).raw_ref
            )
            for line in (root / "observations.jsonl").read_text().splitlines()
        )
    for saved in shadow_captures.values():
        for sample in saved.samples:
            if any(
                m.market.ticker == sample.ticker
                and m.market.open_time <= sample.decision_time < m.market.close_time
                for m in markets
            ):
                decisions.setdefault(sample.ticker, set()).add(sample.decision_time)
    shadow_copies: dict[str, str] = {}
    for digest, (cycle_root, _inputs) in sorted(shadow.items()):
        prefix = "shadow/" + digest
        shadow_copies[digest] = prefix
        result = json.loads((cycle_root / "result.json").read_text())
        copies[prefix + "/result.json"] = _file(cycle_root, "result.json")
        for artifact in result["artifacts"]:
            name = artifact["path"]
            copies[prefix + "/" + name] = _file(cycle_root, name)
    if not decisions:
        raise ValueError("Retained receipts have no weather contracts open at a recorded decision")
    by_ticker: dict[str, list[MarketEvidence]] = {}
    for evidence in markets:
        by_ticker.setdefault(evidence.market.ticker, []).append(evidence)
    outcome_inputs: dict[str, str] = {}
    unique_outcomes = {
        file_hash(_file(root, "outcomes/summary.json")): root for root in outcome_roots
    }
    for index, (_digest, root) in enumerate(sorted(unique_outcomes.items())):
        summary = _file(root, "outcomes/summary.json")
        prefix = f"labels/{index:04d}"
        copies[prefix + "/summary.json"] = summary
        outcome_inputs[file_hash(summary)] = file_hash(summary)
        for record in json.loads(summary.read_text())["outcomes"]:
            receipt = record["receipt"]
            path = _file(root, receipt["raw_ref"])
            if file_hash(path) != receipt["sha256"]:
                raise ValueError("weather outcome receipt checksum mismatch")
            relative = prefix + "/" + Path(receipt["raw_ref"]).name
            copies[relative] = path
            at = datetime.fromisoformat(receipt["received_at"])
            payload = json.loads(path.read_text())["market"]
            market = market_from_body(
                payload, captured_at=at, series=record["ticker"].split("-")[0]
            )
            originals = by_ticker.get(market.ticker, [])
            if (
                any(terms(market) != terms(o.market) for o in originals)
                or market.ticker != record["ticker"]
                or receipt["status"] != 200
                or market.status is not MarketStatus.FINALIZED
                or market.result not in {MarketResult.YES, MarketResult.NO}
                or market.settlement_ts is None
                or not market.close_time <= market.settlement_ts <= at
                or market.settlement_value != (1 if market.result is MarketResult.YES else 0)
                or payload.get("is_provisional") not in {None, False}
                or record["available_at"] != receipt["received_at"]
                or record["result"] != market.result.value
            ):
                raise ValueError("weather binary label lacks matching finalized receipt semantics")
            if not originals:
                continue  # Later label partitions may also contain unrelated contracts.
            markets.append(
                MarketEvidence(
                    market=market,
                    capture_basis="receipt",
                    raw_ref=relative,
                    raw_hash=file_hash(path),
                )
            )
    dates = [
        m.market.rules.settlement_target_date
        for m in markets
        if m.market.rules.settlement_target_date is not None
    ]
    if not dates:
        raise ValueError("No verified weather target dates in retained receipts")
    anchor = frozen_anchor or min(dates)
    if min(dates) < anchor:
        raise ValueError("selected receipts precede frozen weather anchor")
    boundaries = (
        list(next(iter(partitions)))
        if partitions
        else [(anchor + timedelta(days=d)).isoformat() for d in (48, 60, 90)]
    )
    if prior and anchor.isoformat() < min(p["identity"]["anchor"] for p in prior):
        raise ValueError(
            "new weather inputs precede frozen anchor; use a separately reviewed partition"
        )
    protected_events |= frozenset(
        m.market.event_ticker
        for m in markets
        if m.market.rules.settlement_target_date
        and m.market.rules.settlement_target_date.isoformat() >= boundaries[2]
    )
    identity = {
        "schema": SCHEMA,
        "captures": sorted(unique),
        "outcome_inputs": sorted(outcome_inputs),
        "anchor": min(p["identity"]["anchor"] for p in prior) if prior else anchor.isoformat(),
        "temporal_boundaries": boundaries,
        "protected_events": sorted(protected_events),
        "shadow_cycles": sorted(shadow),
        "selection": selection,
        "code": {
            name: file_hash(Path(__file__).parents[1] / name)
            for name in (
                "weather/history.py",
                "tracking/history.py",
                "tracking/replay.py",
                "data/dataset.py",
                "features/pipeline.py",
                "features/registry.py",
                "ml/evaluation.py",
                "ml/experiment.py",
            )
        },
    }
    version = scientific_hash(identity)
    destination = output / version.removeprefix("sha256:")
    if destination.exists():
        return load_snapshot(destination)
    output.mkdir(parents=True, exist_ok=True)
    staging = output / (".building-" + version.removeprefix("sha256:"))
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    if sum(p.stat().st_size for p in copies.values()) > MAX_BYTES:
        raise ValueError("retained weather inputs exceed 256 MB budget")
    for name, path in copies.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    # Validate copied inputs, so a concurrent change cannot publish mixed evidence.
    for name, path in copies.items():
        if file_hash(staging / name) != file_hash(path):
            raise ValueError("weather receipt changed during snapshot")
    for index in range(len(unique)):
        forward_data(staging / f"receipts/{index:04d}")
    for prefix in shadow_copies.values():
        verified_inputs(staging / prefix)
    protected_targets = {
        (locations[m.market.series_ticker].station, m.market.rules.settlement_target_date)
        for m in markets
        if m.market.event_ticker in protected_events and m.market.series_ticker in locations
    }
    observations = _observations(
        [
            o
            for o in observed
            if not (o.role == "observation" and (o.entity_id, o.valid_on) in protected_targets)
        ]
    )
    dataset_config = DatasetConfig(
        locations=tuple(locations[k] for k in sorted(locations)), start=min(dates), end=max(dates)
    )
    rows, _ = make_rows(
        dataset_config,
        markets,
        observations,
        [],
        version,
        {k: tuple(sorted(v)) for k, v in decisions.items()},
    )
    for row in rows:
        finalized = [
            m
            for m in markets
            if m.market.ticker == row["market_ticker"] and m.market.status is MarketStatus.FINALIZED
        ]
        if len({m.market.result for m in finalized}) > 1:
            raise ValueError("conflicting official binary outcome revisions")
        if finalized and row["event_id"] not in protected_events:
            chosen = min(finalized, key=lambda m: m.market.rules.captured_at)
            row["outcome"] = chosen.market.result.value if chosen.market.result else None
            row["outcome_available_at"] = chosen.market.rules.captured_at.isoformat()
    # Exact cycle-specific joins: a missing/deferred book never borrows another cycle's depth.
    by_decision: dict[tuple[str, str], ContractSample] = {}
    for saved in shadow_captures.values():
        for sample in saved.samples:
            key = (sample.ticker, sample.decision_time.isoformat())
            if key in by_decision and by_decision[key] != sample:
                raise ValueError("conflicting shadow samples at one decision clock")
            by_decision[key] = sample
    labels = {}
    for row in rows:
        if row["event_id"] in protected_events:
            row["outcome"] = None
            row["outcome_available_at"] = None
        labels[row["market_ticker"]] = (row["outcome"], row["outcome_available_at"])
        matched = by_decision.get((row["market_ticker"], row["decision_time"]))
        if matched is None:
            continue
        row["market_state_json"] = None
        row["execution_fidelity"] = matched.fidelity
        row["executable"] = False
        if matched.book is not None:
            row["market_state_json"] = json.dumps(
                {
                    "fidelity": "order_book",
                    "available_at": matched.book.received_at.isoformat(),
                    "payload": matched.book.model_dump(mode="json"),
                }
            )
            row["executable"] = (
                bool(matched.book.bids and matched.book.asks)
                and not matched.book.is_crossed
                and (matched.decision_time - matched.book.received_at).total_seconds() <= 60
                and matched.rules_known
                and matched.decision_time < matched.close_time
            )
        provenance = json.loads(row["provenance_json"])
        provenance["shadow"] = {
            "feature_hash": matched.feature_hash,
            "versions": matched.versions,
            "features_available_at": matched.features_available_at.isoformat(),
        }
        row["provenance_json"] = json.dumps(provenance, sort_keys=True)
    replay_cycles = []
    for digest, (_cycle_root, inputs) in sorted(shadow.items()):
        saved = ExperimentData.model_validate(inputs["data"])
        samples = []
        for sample in saved.samples:
            if sample.event_id in protected_events:
                continue
            outcome, available = labels.get(sample.ticker, (None, None))
            samples.append(sample.revalidated(outcome=outcome, outcome_available_at=available))
        replay_cycles.append(
            {
                "result_sha256": digest,
                "evidence": shadow_copies[digest],
                "original_replay_verified": True,
                "frozen_spec": inputs["spec"],
                "prediction_bundle": PredictionBundle.model_validate(inputs["bundle"])
                .revalidated(
                    records=tuple(
                        p
                        for p in PredictionBundle.model_validate(inputs["bundle"]).records
                        if p.event_id not in protected_events and any(p.usable(s) for s in samples)
                    ),
                )
                .model_dump(mode="json"),
                "saved_decisions": [
                    d
                    for d in json.loads((_cycle_root / "result.json").read_text())["decisions"]
                    if d["event_id"] not in protected_events
                ],
                "fee_evidence": json.loads((_cycle_root / "execution/summary.json").read_text())[
                    "fee_evidence"
                ],
                "experiment_data": saved.revalidated(
                    samples=tuple(samples),
                    protected_events=protected_events,
                    provenance={
                        "purpose": "saved forward shadow samples with subsequent labels",
                        "source_dataset": saved.dataset_version,
                        "source_feature_version": saved.feature_version,
                    },
                ).model_dump(mode="json"),
            }
        )
    shadow_audit = {
        "verified_cycles": len(shadow),
        "decision_samples": len(by_decision),
        "sized_books": sum(s.book is not None for s in by_decision.values()),
        "closed_decisions": sum(s.decision_time >= s.close_time for s in by_decision.values()),
        "stale_books": sum(
            s.book is not None and (s.decision_time - s.book.received_at).total_seconds() > 60
            for s in by_decision.values()
        ),
        "labelled_samples": sum(
            labels.get(s.ticker, (None, None))[0] is not None
            for s in by_decision.values()
            if s.event_id not in protected_events
        ),
        "execution_blockers": [
            "Missing later labels refuse historical evaluation"
            if any(
                labels.get(s.ticker, (None, None))[0] is None
                for s in by_decision.values()
                if s.event_id not in protected_events
            )
            else "Later binary labels retain their original receipt clocks; "
            "scalar model gates still apply",
            "Stale or missing depth refuses executable backtesting",
            "Certified effective historical fees are unavailable; no fee coefficient substituted",
        ],
        "replay_inputs": "shadow-replay.json",
        "limitation": "Forward predictions retain their partition; never promoted to validation. "
        "Replay certifies software consistency, not profitability.",
    }
    (staging / "shadow-replay.json").write_text(
        json.dumps(
            {
                "schema": "retained-shadow-replay-v1",
                "dataset_id": version,
                "submission_enabled": False,
                "cycles": replay_cycles,
            },
            sort_keys=True,
            indent=2,
        )
    )
    dataset = staging / "dataset"
    dataset.mkdir()
    pq.write_table(pa.Table.from_pylist(rows), dataset / "rows.parquet", compression="zstd")
    pq.write_table(
        pa.Table.from_pylist(
            [{"payload_json": o.model_dump_json()} for o in observations],
            schema=pa.schema([("payload_json", pa.string())]),
        ),
        dataset / "observations.parquet",
        compression="zstd",
    )
    source_manifest = {
        "dataset_version": version,
        "data_kind": "real",
        "config": dataset_config.model_dump(mode="json"),
        "retained_capture_audit": capture_audit,
        "retained_shadow_audit": shadow_audit,
        "temporal_boundaries": boundaries,
        "protected_events": sorted(protected_events),
    }
    if selection and "cohort" in selection:
        source_manifest["retained_cohort"] = selection["cohort"]
    (dataset / "manifest.json").write_text(json.dumps(source_manifest, sort_keys=True))
    features = build_features(dataset=dataset, archives=(), output=staging / "features")
    feature_path = "features/" + features["feature_version"].removeprefix("sha256:")
    result = {
        "schema": SCHEMA,
        "dataset_id": version,
        "identity": identity,
        "features": feature_path,
        "capture_count": len(unique),
        "observation_count": len(observations),
        "shadow_audit": shadow_audit,
        "readiness": readiness(staging / feature_path),
        "checksums": {
            p.relative_to(staging).as_posix(): file_hash(p)
            for p in sorted(staging.rglob("*"))
            if p.is_file()
        },
    }
    (staging / "snapshot.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    load_snapshot(staging)
    staging.rename(destination)
    return result
