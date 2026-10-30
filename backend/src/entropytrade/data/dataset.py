"""Deterministic point-in-time joins with separate eventual labels and low-fidelity context."""

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.recording import recorded_inputs
from entropytrade.data.schema import DatasetConfig, MarketEvidence, MarketState, Observation
from entropytrade.data.sources import decisions, file_hash, load_sources
from entropytrade.domain.enums import MarketStatus
from entropytrade.domain.ids import canonical_json, content_hash
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.time import utc_now
from entropytrade.exchange.settlement import ticker_target_date

VERSION = "daily-high-pit-v1"


def build_dataset(
    *, config: DatasetConfig, sources: Sequence[Path], output: Path, recorder: Path | None = None
) -> dict[str, Any]:
    markets: list[MarketEvidence] = []
    observations: list[Observation] = []
    states: list[MarketState] = []
    inputs: dict[str, str] = {}
    warnings: list[str] = []
    for index, root in enumerate(sources):
        found, observed, hashes, notes = load_sources(root, config)
        markets.extend(m.revalidated(raw_ref=f"source{index}/{m.raw_ref}") for m in found)
        observations.extend(o.revalidated(raw_ref=f"source{index}/{o.raw_ref}") for o in observed)
        inputs.update({f"source{index}/{key}": value for key, value in hashes.items()})
        warnings.extend(notes)
        path = root / "market_states.jsonl"
        if path.exists():
            inputs[f"source{index}/market_states.jsonl"] = file_hash(path)
            for line in path.read_text(encoding="utf-8").splitlines():
                state = MarketState.model_validate_json(line)
                raw = (root / state.raw_ref).resolve()
                if not raw.is_relative_to(root.resolve()) or file_hash(raw) != state.raw_hash:
                    raise ValueError("market state raw evidence mismatch")
                inputs[f"source{index}/{state.raw_ref}"] = state.raw_hash
                states.append(state)
    if recorder is not None:
        metadata, recorded, digest = recorded_inputs(recorder)
        markets.extend(metadata)
        states.extend(recorded)
        inputs["recording_committed_snapshot"] = digest
    code = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    version = content_hash(
        {
            "code": code,
            "schema": VERSION,
            "config": config.model_dump(mode="json"),
            "inputs": inputs,
        }
    )
    rows, missing = make_rows(config, markets, observations, states, version)
    coverage = {
        "rows": len(rows),
        "contracts": len({r["market_ticker"] for r in rows}),
        "events": len({r["event_id"] for r in rows}),
        "missing_event_dates": missing,
        "execution_fidelity": dict(Counter(r["execution_fidelity"] for r in rows)),
        "rows_with_strict_features": sum(r["features_json"] != "{}" for r in rows),
        "outcomes_known": sum(r["outcome"] is not None for r in rows),
        "rules_known_at_decision": sum(r["rules_known_at_decision"] for r in rows),
        "forecast_observations": len(observations),
        "uncertain_observations": sum(
            o.timing_basis in ("unknown", "assumed") for o in observations
        ),
    }
    coverage["by_city"] = {
        location.name: {
            "contracts": len({r["market_ticker"] for r in rows if r["city"] == location.name}),
            "events": len({r["event_id"] for r in rows if r["city"] == location.name}),
            "rows": sum(r["city"] == location.name for r in rows),
            "outcomes_known": sum(
                r["city"] == location.name and r["outcome"] is not None for r in rows
            ),
            "strict_feature_rows": sum(
                r["city"] == location.name and r["features_json"] != "{}" for r in rows
            ),
        }
        for location in config.locations
    }
    coverage["missing_data"] = {
        "no_strict_feature_values": sum(r["features_json"] == "{}" for r in rows),
        "historical_rule_version_unverified": sum(not r["rules_known_at_decision"] for r in rows),
        "no_executable_book": sum(not r["executable"] for r in rows),
        "unresolved_outcome": sum(r["outcome"] is None for r in rows),
    }
    manifest = {
        "dataset_version": version,
        "schema_version": VERSION,
        "code_hashes": code,
        "config": config.model_dump(mode="json"),
        "inputs": inputs,
        "coverage": coverage,
        "warnings": sorted(set(warnings)),
        "rows_hash": content_hash({"rows": rows}),
        "limitations": [
            "Historical metadata is not proof of historical rule versions.",
            "Event time is not receipt or publication time.",
            "Only strict features_json is eligible for point-in-time modeling.",
        ],
    }
    destination = output / version.removeprefix("sha256:")
    if destination.exists():
        stored = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        if stored != manifest:
            raise ValueError("dataset version collision or incomplete output; inspect destination")
        checksums = json.loads((destination / "checksums.json").read_text())
        if set(checksums) != {
            "rows.parquet",
            "observations.parquet",
            "manifest.json",
            "coverage.json",
        }:
            raise ValueError("dataset artifact checksum inventory changed")
        for name, digest in checksums.items():
            if file_hash(destination / name) != digest:
                raise ValueError("existing dataset artifact was modified")
        return manifest
    output.mkdir(parents=True, exist_ok=True)
    staging = output / (".building-" + version.removeprefix("sha256:"))
    staging.mkdir()  # Concurrent writers fail safely; incomplete builds never look complete.
    columns: dict[str, pa.DataType] = {
        "event_id": pa.string(),
        "market_ticker": pa.string(),
        "decision_time": pa.string(),
        "dataset_version": pa.string(),
        "city": pa.string(),
        "station": pa.string(),
        "target_date": pa.string(),
        "strike_json": pa.string(),
        "rules_hash": pa.string(),
        "rules_json": pa.string(),
        "rules_known_at_decision": pa.bool_(),
        "contract_existed_at_decision": pa.bool_(),
        "features_json": pa.string(),
        "excluded_features_json": pa.string(),
        "market_state_json": pa.string(),
        "historical_context_json": pa.string(),
        "execution_fidelity": pa.string(),
        "executable": pa.bool_(),
        "outcome": pa.string(),
        "outcome_available_at": pa.string(),
        "provenance_json": pa.string(),
        "quality_json": pa.string(),
    }
    pq.write_table(
        pa.Table.from_pylist(rows, schema=pa.schema(list(columns.items()))),
        staging / "rows.parquet",
        compression="zstd",
    )
    observation_rows = [
        {
            "source_id": o.source_id,
            "entity_id": o.entity_id,
            "valid_on": o.valid_on.isoformat(),
            "variable": o.variable,
            "timing_basis": o.timing_basis,
            "payload_json": o.model_dump_json(),
        }
        for o in sorted(observations, key=lambda o: o.model_dump_json())
    ]
    pq.write_table(
        pa.Table.from_pylist(
            observation_rows,
            schema=pa.schema(
                [
                    (name, pa.string())
                    for name in (
                        "source_id",
                        "entity_id",
                        "valid_on",
                        "variable",
                        "timing_basis",
                        "payload_json",
                    )
                ]
            ),
        ),
        staging / "observations.parquet",
        compression="zstd",
    )
    (staging / "rows.parquet.sha256").write_text(file_hash(staging / "rows.parquet") + "\n")
    (staging / "manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    (staging / "coverage.json").write_text(canonical_json(coverage) + "\n", encoding="utf-8")
    (staging / "checksums.json").write_text(
        canonical_json(
            {
                name: file_hash(staging / name)
                for name in (
                    "rows.parquet",
                    "observations.parquet",
                    "manifest.json",
                    "coverage.json",
                )
            }
        )
    )
    # Operational build time is deliberately outside the deterministic dataset manifest.
    (staging / "build.json").write_text(
        json.dumps(
            {"built_at": utc_now().isoformat(), "source_roots": [str(p.resolve()) for p in sources]}
        )
    )
    staging.rename(destination)
    return manifest


def make_rows(
    config: DatasetConfig,
    markets: Sequence[MarketEvidence],
    observations: Sequence[Observation],
    states: Sequence[MarketState],
    version: str,
    receipt_decisions: dict[str, tuple[datetime, ...]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[MarketEvidence]] = {}
    locations = {p.series: p for p in config.locations}
    for evidence in markets:
        market = evidence.market
        series = market.series_ticker or market.ticker.split("-", 1)[0]
        if series not in locations:
            continue
        day = ticker_target_date(market.ticker)
        if day is not None and config.start <= day <= config.end:
            grouped.setdefault(market.ticker, []).append(evidence)
    rows: list[dict[str, Any]] = []
    present: set[str] = set()
    for ticker, history in sorted(grouped.items()):
        history.sort(key=lambda e: (e.market.rules.captured_at, e.raw_hash))
        latest = history[-1]
        day = ticker_target_date(ticker)
        if day is None:
            continue
        series = latest.market.series_ticker or ticker.split("-", 1)[0]
        location = locations[series]
        present.add(f"{series}:{day}")
        for decision in (
            decisions(day, config.decision_utc)
            if receipt_decisions is None
            else receipt_decisions.get(ticker, ())
        ):
            known = [
                e
                for e in history
                if e.capture_basis == "receipt" and e.market.rules.captured_at <= decision
            ]
            chosen = known[-1] if known else history[0]
            market = chosen.market
            related = [
                o
                for o in observations
                if o.source_id in config.sources
                and o.entity_id in (location.station, ticker)
                and o.valid_on == day
            ]
            visible: dict[str, Observation] = {}
            excluded: list[dict[str, object]] = []
            for observation in sorted(
                related,
                key=lambda o: (
                    o.available_at or datetime.min.replace(tzinfo=decision.tzinfo),
                    o.revised_at or o.available_at or datetime.min.replace(tzinfo=decision.tzinfo),
                    o.raw_hash,
                    o.model_dump_json(),
                ),
            ):
                if observation.known_at(decision) and observation.role == "feature":
                    visible[observation.source_id + ":" + observation.variable] = observation
                else:
                    excluded.append(
                        {
                            "source": observation.source_id,
                            "variable": observation.variable,
                            "timing_basis": observation.timing_basis,
                            "role": observation.role,
                        }
                    )
            state, executable = _state_asof(states, ticker, decision, config.max_age_seconds)
            outcome = latest.market.result
            label = (
                outcome.value
                if latest.market.status is MarketStatus.FINALIZED
                and outcome is not None
                and outcome.value in ("yes", "no")
                else None
            )
            rows.append(
                {
                    "event_id": market.event_ticker,
                    "market_ticker": ticker,
                    "decision_time": decision.isoformat(),
                    "dataset_version": version,
                    "city": location.name,
                    "station": location.station,
                    "target_date": day.isoformat(),
                    "strike_json": canonical_json(
                        None if market.strike is None else market.strike.model_dump(mode="json")
                    ),
                    "rules_hash": market.rules.rules_hash,
                    "rules_json": market.rules.model_dump_json(),
                    "rules_known_at_decision": bool(known),
                    "contract_existed_at_decision": bool(known)
                    or (chosen.created_at is not None and chosen.created_at <= decision),
                    "features_json": canonical_json({k: str(v.value) for k, v in visible.items()}),
                    "excluded_features_json": canonical_json(excluded),
                    "market_state_json": (
                        state.model_dump_json()
                        if state is not None and state.available_at is not None
                        else None
                    ),
                    "historical_context_json": (
                        state.model_dump_json()
                        if state is not None and state.available_at is None
                        else None
                    ),
                    "execution_fidelity": "missing" if state is None else state.fidelity,
                    "executable": executable
                    and bool(known)
                    and market.open_time <= decision < market.close_time
                    and market.rules.settlement_basis == "contract_text"
                    and market.strike is not None
                    and market.strike.is_evaluable,
                    "outcome": label,
                    "outcome_available_at": latest.market.rules.captured_at.isoformat()
                    if label and latest.capture_basis == "receipt"
                    else None,
                    "provenance_json": canonical_json(
                        {
                            "metadata": chosen.model_dump(mode="json"),
                            "outcome": {
                                "source": "kalshi_resolved_contract",
                                "raw_ref": latest.raw_ref,
                                "raw_hash": latest.raw_hash,
                            },
                            "features": {k: v.model_dump(mode="json") for k, v in visible.items()},
                        }
                    ),
                    "quality_json": canonical_json(
                        {
                            "metadata_reconstructed": not bool(known),
                            "outcome_used_as_feature": False,
                            "settlement_basis": market.rules.settlement_basis,
                            "listing_evidence": "exchange_created_time"
                            if chosen.created_at
                            else "unknown",
                            "excluded_observations": len(excluded),
                            "state_available_at_proven": state is not None
                            and state.available_at is not None,
                        }
                    ),
                }
            )
    from entropytrade.data.sources import days

    missing = [
        f"{p.series}:{day}"
        for p in config.locations
        for day in days(config.start, config.end)
        if f"{p.series}:{day}" not in present
    ]
    return rows, missing


def _state_asof(
    states: Sequence[MarketState], ticker: str, decision: datetime, max_age: int
) -> tuple[MarketState | None, bool]:
    eligible = [
        s
        for s in states
        if s.market_ticker == ticker
        and s.event_time <= decision
        and (s.available_at is None or s.available_at <= decision)
    ]
    if not eligible:
        return None, False
    state = max(
        eligible,
        key=lambda s: (s.available_at or s.event_time, s.fidelity == "invalid", s.raw_hash),
    )
    fresh = (
        state.available_at is not None
        and (decision - state.available_at).total_seconds() <= max_age
    )
    if state.fidelity == "invalid":
        return None, False
    depth = False
    if state.fidelity == "order_book":
        book = OrderBook.model_validate(state.payload)
        depth = bool(book.bids) and bool(book.asks) and not book.is_crossed
    return state, bool(fresh and depth and state.fidelity == "order_book")
