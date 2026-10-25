"""Bounded, read-only projections. Labels and protected date rows never enter tool outputs."""

import json
import sqlite3
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field

from entropytrade.data.sources import file_hash
from entropytrade.domain.base import DomainModel
from entropytrade.features.registry import FEATURE_NAMES, feature_schema, scientific_hash


class EvidenceConfig(DomainModel):
    root: Path
    features: str
    model_results: str | None = None
    # Explicit protection boundary; agent arguments cannot change this.
    holdout_start: date
    max_rows: int = Field(default=100_000, ge=1, le=200_000)
    load_timeout_seconds: int = Field(default=20, ge=1, le=60)


class EvidenceQuery(DomainModel):
    topic: Literal["coverage", "markets", "features", "models", "history"]
    offset: int = Field(default=0, ge=0, le=100_000)
    limit: int = Field(default=10, ge=1, le=20)
    ticker: str | None = Field(default=None, max_length=100)


def _path(config: EvidenceConfig, relative: str) -> Path:
    path = (config.root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(config.root.resolve()):
        raise ValueError("evidence path must remain within the configured dataset root")
    return path


def _json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 2_000_000:
        raise ValueError("evidence document exceeds size budget")
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise ValueError("evidence document must be an object")
    return result


class ResearchEvidence:
    """Built by trusted orchestration, never by an agent. No general file/SQL/network tool."""

    def __init__(
        self, config: EvidenceConfig, *, history: list[dict[str, Any]] | None = None
    ) -> None:
        started = time.monotonic()
        self.config = config
        directory = _path(config, config.features)
        model_result = _json(_path(config, config.model_results)) if config.model_results else None
        protected_events = (
            set(model_result.get("split", {}).get("holdout", [])) if model_result else set()
        )
        path = directory / "features.parquet"
        # Resolve each file too: a symlink inside an approved directory cannot escape it.
        for item in (path, directory / "manifest.json", directory / "features.sha256"):
            if not item.resolve().is_relative_to(config.root.resolve()):
                raise ValueError("evidence symlink escaped root")
        manifest = _json(directory / "manifest.json")
        manifest_payload = dict(manifest)
        version = manifest_payload.pop("feature_version")
        if scientific_hash(manifest_payload) != version:
            raise ValueError("feature manifest identity mismatch")
        if path.stat().st_size > 32_000_000:
            raise ValueError("research partition exceeds file size budget")
        if file_hash(path) != (directory / "features.sha256").read_text().strip():
            raise ValueError("feature artifact checksum mismatch")
        metadata = pq.ParquetFile(path).metadata
        if (
            sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
            > 64_000_000
        ):
            raise ValueError("research partition exceeds decoded size budget")
        if metadata.num_rows > config.max_rows:
            raise ValueError("dataset exceeds research row budget; use a bounded partition")
        columns = [
            "event_id",
            "market_ticker",
            "target_date",
            "decision_time",
            "station",
            "city",
            "strike_json",
            "rules_json",
            "rules_known_at_decision",
            "contract_existed_at_decision",
            "feature_eligible",
            "feature_values_json",
            "feature_evidence_json",
            "temperature_target_f",
            "execution_fidelity",
        ]
        # The scalar label is counted internally only; no label value is retained or exposed.
        rows = pq.read_table(
            path, columns=columns, filters=[("target_date", "<", config.holdout_start.isoformat())]
        ).to_pylist()
        rows = [row for row in rows if row["event_id"] not in protected_events]
        self.markets: list[dict[str, Any]] = []
        self.feature_counts: Counter[str] = Counter()
        scalar_events = set()
        for row in rows:
            if row["temperature_target_f"] is not None:
                scalar_events.add(row["event_id"])
            values = json.loads(row["feature_values_json"])
            self.feature_counts.update(n for n in FEATURE_NAMES if values.get(n) is not None)
            row["known_forecast_sources"] = sorted(
                {
                    item["provider"]
                    for item in json.loads(row["feature_evidence_json"])["forecast_evidence"]
                }
            )
            rules = json.loads(row["rules_json"])
            self.markets.append(
                {
                    "event_id": row["event_id"],
                    "market_ticker": row["market_ticker"],
                    "series": row["event_id"].split("-")[0],
                    "target_date": row["target_date"],
                    "decision_time": row["decision_time"],
                    "station": row["station"],
                    "city": row["city"],
                    "strike": json.loads(row["strike_json"]),
                    "relationships": "shared daily high; exhaustive coverage unverified",
                    "rules": {
                        k: rules.get(k)
                        for k in (
                            "rules_primary",
                            "rules_secondary",
                            "settlement_sources",
                            "settlement_basis",
                            "rules_hash",
                            "captured_at",
                        )
                    },
                    "rules_known": row["rules_known_at_decision"],
                    "exists": row["contract_existed_at_decision"],
                    "eligible": row["feature_eligible"],
                    "execution_fidelity": row["execution_fidelity"],
                }
            )
        self.coverage = {
            "data_kind": manifest["data_kind"],
            "source_dataset": manifest["source_dataset"],
            "feature_version": manifest["feature_version"],
            "feature_file_hash": file_hash(path),
            "independent_events": len({r["event_id"] for r in rows}),
            "date_blocks": len({r["target_date"] for r in rows}),
            "rows": len(rows),
            "contracts": len({r["market_ticker"] for r in rows}),
            "eligible_events": len({r["event_id"] for r in rows if r["feature_eligible"]}),
            "scalar_label_events": len(scalar_events),
            "dates": sorted({r["target_date"] for r in rows}),
            "execution_fidelity": dict(Counter(r["execution_fidelity"] for r in rows)),
            "feature_nonmissing_rows": dict(self.feature_counts),
            "protection": "all outcomes withheld; rows on/after configured holdout start excluded",
            "configured_source_kinds": [
                "kalshi",
                "open-meteo",
                "nws",
                "weather-company",
                "nws-cli",
            ],
            "timing": "features require receipt/publication evidence; hourly maxima are proxies",
            "interpreter_capabilities": {
                "supported_subset": [
                    "informational YES",
                    "fixed contracts",
                    "immediate orders",
                    "feature conjunctions",
                    "explicit hold-to-settlement marker",
                ],
                "requires_R4": [
                    "NO entries",
                    "per-spec spread limits",
                    "fees/net edge",
                    "hedging",
                    "holding-period exits",
                    "other exit predicates",
                    "realistic replay chronology and shared liquidity",
                ],
                "minimum_edge_basis": "legacy gross probability minus ask, not net of fees",
                "execution_in_R3": False,
            },
        }
        self.models: dict[str, Any] = {"status": "not_supplied", "models": {}}
        if config.model_results:
            if model_result is None:
                raise ValueError("model result unavailable")
            result = model_result
            if result["feature_version"] != manifest["feature_version"]:
                raise ValueError("model result belongs to a different feature matrix")
            # Never expose split IDs, predictions, holdout/walk-forward metrics or raw result JSON.
            allowed = {r["event_id"] for r in rows}
            split = result.get("split", {})
            validation_allowed = (
                bool(split.get("validation")) and set(split["validation"]) <= allowed
            )
            self.models = {
                k: result.get(k)
                for k in ("run_id", "data_kind", "status", "eligible_events", "reason", "refusals")
            }
            self.models["models"] = {
                name: {
                    "artifact_hash": item["artifact_hash"],
                    "calibration": item["calibration"],
                    "validation": item.get("metrics", {}).get("validation")
                    if validation_allowed
                    else None,
                }
                for name, item in result["models"].items()
            }
            for name, diagnostic in self.models["models"].items():
                permitted_names = {
                    "climatology",
                    "raw_forecast",
                    "forecast_error",
                    "ridge",
                    "boosting",
                }
                available = False
                if name in permitted_names:
                    artifact = _path(
                        config, str(Path(config.model_results).parent / (name + ".joblib"))
                    )
                    available = (
                        artifact.is_file()
                        and artifact.stat().st_size <= 32_000_000
                        and file_hash(artifact) == diagnostic["artifact_hash"]
                    )
                diagnostic["artifact_available"] = available
                diagnostic["validation_is_permitted"] = validation_allowed
            self.models["source_hash"] = file_hash(_path(config, config.model_results))
        self.coverage["by_series"] = {}
        for series in sorted({m["series"] for m in self.markets}):
            scoped = [r for r in rows if r["event_id"].split("-")[0] == series]
            self.coverage["by_series"][series] = {
                "eligible_events": len({r["event_id"] for r in scoped if r["feature_eligible"]}),
                "scalar_label_events": len(
                    {r["event_id"] for r in scoped if r["temperature_target_f"] is not None}
                ),
                "source_counts": dict(
                    Counter(source for row in scoped for source in row["known_forecast_sources"])
                ),
                "features": dict(
                    Counter(
                        n
                        for r in scoped
                        for n in FEATURE_NAMES
                        if json.loads(r["feature_values_json"]).get(n) is not None
                    )
                ),
            }
        self.history = history or []
        self.calls: list[dict[str, Any]] = []
        if time.monotonic() - started > config.load_timeout_seconds:
            raise TimeoutError("research evidence load exceeded deadline")

    def inspect(self, query: EvidenceQuery) -> dict[str, Any]:
        if len(self.calls) >= 32:
            raise ValueError("research tool-call budget exhausted")
        if query.topic == "coverage":
            value: Any = self.coverage
        elif query.topic == "features":
            value = {
                **feature_schema(),
                "prediction_interface": {
                    "name": "model_yes_probability",
                    "version": "r2-prediction-v1",
                    "availability": "requires a real fitted artifact and decision-time inputs",
                    "missing": "no prediction; never replace with a candle or a binary rule fire",
                },
            }
        elif query.topic == "models":
            value = self.models
        else:
            items = self.history if query.topic == "history" else self.markets
            if query.ticker:
                items = [r for r in items if r.get("market_ticker") == query.ticker]
            value = {
                "items": items[query.offset : query.offset + query.limit],
                "next_offset": query.offset + query.limit
                if len(items) > query.offset + query.limit
                else None,
                "total": len(items),
            }
        envelope = {"untrusted_evidence": value, "query": query.model_dump(mode="json")}
        if len(json.dumps(envelope)) > 24_000:
            raise ValueError("tool output too large; request a smaller page")
        envelope["evidence_id"] = scientific_hash(envelope)
        self.calls.append(envelope)
        return envelope


def previous_research(path: Path) -> list[dict[str, Any]]:
    """Only our typed, deliberately outcome-free research history, using fixed SQL."""
    if not path.exists():
        return []
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=2)
    try:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='agent_research_runs'"
        ).fetchone():
            return []
        rows = db.execute(
            "SELECT payload FROM agent_research_runs ORDER BY rowid DESC LIMIT 20"
        ).fetchall()
        return [
            {
                "run_id": r["run_id"],
                "mode": r["mode"],
                "hypotheses": [
                    {k: h[k] for k in ("hypothesis_id", "mechanism", "variables", "market_family")}
                    for h in r.get("hypotheses", [])
                ],
                "candidates": r.get("candidates", []),
                "decisions": [
                    {k: d[k] for k in ("candidate_id", "status", "spec_hash", "critic")}
                    for d in r.get("decisions", [])
                ],
            }
            for (payload,) in rows
            if len(payload) <= 2_000_000
            for r in [json.loads(payload)]
        ]
    finally:
        db.close()
