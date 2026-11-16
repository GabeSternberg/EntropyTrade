"""Read-only, receipt-time prospective forecast diagnostics. Never historical validation.

Reports are deterministic projections of committed cycles, not mutable scores or a new
training dataset. Offline workspace restore uses exactly the same verifier as the website.
"""

import argparse
import csv
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs, identifier
from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus
from entropytrade.domain.market import Market
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import ContractSample, ExperimentData, PredictionBundle
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather
from entropytrade.research.paper_models import PortableResearchModel
from entropytrade.tracking.history import verified_inputs
from entropytrade.tracking.models import score
from entropytrade.tracking.reconciliation import is_reconciliation, same_frozen_terms, terms
from entropytrade.tracking.replay import verify

MAX_BYTES = 256_000_000
MIN_EVENTS = 10
MIN_DATES = 5
LIMITATIONS = [
    "Prospective monitoring only; never historical validation, simulated trading accounting "
    "or evidence of profitability. No fitting, promotion or orders.",
    "One earliest retained pre-close observation per contract; later polls cannot replace "
    "a missing/refused forecast or increase independent counts. Strikes share event weight.",
    "Latest verified official binary receipt at the cutoff is used. Revisions are visible; "
    "original predictions, receipts, first accounting settlements and holdouts stay unchanged.",
    "Diagnostics require ten matched events on five target dates per model/data group. "
    "These are descriptive diagnostics, without confidence or significance claims.",
    "Offline verification establishes retained lineage and computation, not external source truth. "
    "Synthetic examples establish software behavior only.",
]


def at(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value))


def _cycles(jobs: Jobs, monitor_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # A single read transaction pins membership even while the collector commits new cycles.
    with jobs.connect() as db:
        db.execute("BEGIN")
        row = db.execute("SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)).fetchone()
        if row is None:
            raise ValueError("unknown monitor")
        monitor = dict(row)
        cycles = [
            dict(c)
            for c in db.execute(
                "SELECT * FROM shadow_cycles WHERE monitor_id=? ORDER BY sequence", (monitor_id,)
            )
        ]
    if len(cycles) > 1000:
        raise ValueError("prospective cycle budget exceeded")
    return monitor, cycles


def _inputs(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    if is_reconciliation(result):
        return verified_inputs(root)
    inputs: dict[str, Any] = json.loads((root / "decision-inputs.json").read_text())
    data = ExperimentData.model_validate(inputs["data"])
    research = (result.get("model_binding") or {}).get("kind") == "research_weather_v1"
    if data.data_kind == "synthetic" and not research:
        # A synthetic replay cannot certify public sources and is never grouped with real data.
        verify(root)
    else:
        inputs = verified_inputs(root)
        spec = StrategySpec.model_validate(inputs["spec"])
        markets = {c["ticker"]: Market.model_validate(c["market"]) for c in result["contracts"]}
        sources = {}
        for line in (root / "public/markets.jsonl").read_text().splitlines():
            evidence = MarketEvidence.model_validate_json(line)
            sources[evidence.market.ticker] = evidence
        for contract in result["contracts"]:
            evidence = sources[contract["ticker"]]
            if (
                markets[contract["ticker"]] != evidence.market
                or contract["raw_hash"] != evidence.raw_hash
                or contract["raw_ref"] != "public/" + evidence.raw_ref
            ):
                raise ValueError("frozen forecast contract differs from public receipt")
        bundle = PredictionBundle.model_validate(inputs["bundle"])
        if research:
            from entropytrade.tracking import history
            from entropytrade.tracking.research_features import reconstruct_research_data

            reconstructed = reconstruct_research_data(
                root, history.forward_data(root / "public"), result, result["execution"]
            )
            # decision_inputs intentionally excludes full source provenance. Restore
            # only the verified scoring markers in memory; original bytes stay intact.
            scoring = data.revalidated(
                provenance={
                    key: reconstructed.provenance[key]
                    for key in ("adapter", "feature_schema_hash", "deployment_created_at")
                }
                | {"research_window_at": result["research_window_at"]}
            )
        else:
            scoring = data.revalidated(provenance={"adapter": "public-forward-v1:weather"})
        expected = score(
            spec,
            scoring,
            result.get("model_binding"),
            markets,
        )
        if bundle.records != expected.records or bundle.source_hash != expected.source_hash:
            raise ValueError("saved forecasts differ from frozen model scoring")
    return inputs


def _outcomes(root: Path, result: dict[str, Any]) -> list[dict[str, Any]]:
    summary = json.loads((root / "outcomes/summary.json").read_text())
    if any(result.get(k) != v for k, v in summary.items()):
        raise ValueError("outcome summary differs from committed cycle")
    hashes = {a["path"]: a["sha256"] for a in result["artifacts"]}
    if "outcomes/summary.json" not in hashes:
        raise ValueError("outcome summary is not committed")
    rows = []
    for receipt in summary["outcome_receipts"]:
        ref = receipt["raw_ref"]
        path = (root / ref).resolve()
        if (
            Path(ref).parent.as_posix() != "outcomes"
            or not path.is_relative_to((root / "outcomes").resolve())
            or hashes.get(ref) != receipt["sha256"]
            or file_hash(path) != receipt["sha256"]
        ):
            raise ValueError("outcome receipt checksum/path mismatch")
        try:
            body = json.loads(path.read_bytes())
        except (ValueError, UnicodeError):
            body = {}  # Retain malformed/error responses as explicit outcome refusals.
        rows.append({"receipt": receipt, "body": body})
    return rows


def _label(observed: dict[str, Any], original: Market, cutoff: datetime) -> dict[str, Any] | None:
    receipt = observed["receipt"]
    received = at(receipt["received_at"])
    if received > cutoff:
        return None
    paths = {
        f"/trade-api/v2/markets/{original.ticker}",
        f"/trade-api/v2/historical/markets/{original.ticker}",
    }
    if receipt["path"] not in paths:
        return None
    row = {"receipt": receipt, "available_at": received.isoformat(), "reason": None}
    try:
        if receipt["status"] != 200:
            raise ValueError("outcome_http_failure")
        body = observed["body"]["market"]
        market = market_from_body(body, captured_at=received, series=original.series_ticker or "")
        if not same_frozen_terms(market, original):
            raise ValueError("outcome_contract_terms_changed")
        if (
            market.status is not MarketStatus.FINALIZED
            or market.result not in {MarketResult.YES, MarketResult.NO}
            or body.get("is_provisional") not in {None, False}
            or market.settlement_ts is None
            or not original.close_time <= market.settlement_ts <= received
            or market.settlement_value != (1 if market.result is MarketResult.YES else 0)
        ):
            raise ValueError("outcome_not_verified_final_binary")
        row.update(result=market.result.value, settled_at=market.settlement_ts.isoformat())
    except (ValueError, KeyError, TypeError, GatewayError) as exc:
        row["reason"] = str(exc)
    return row


def _observation(
    sample: ContractSample, inputs: dict[str, Any], cycle: dict[str, Any]
) -> dict[str, Any]:
    data = ExperimentData.model_validate(inputs["data"])
    bundle = PredictionBundle.model_validate(inputs["bundle"])
    spec = StrategySpec.model_validate(inputs["spec"])
    matches = [p for p in bundle.records if p.ticker == sample.ticker]
    reason = None
    prediction = matches[0] if len(matches) == 1 else None
    if prediction is None:
        reason = "missing_or_ambiguous_prediction"
    elif (
        not prediction.usable(sample)
        or prediction.partition != "forward"
        or prediction.feature_version != data.feature_version
        or bundle.model_metadata.get("data_kind") != data.data_kind
        or spec.model_ref is None
        or prediction.model_hash != spec.model_ref.version
        or prediction.family != spec.model_ref.family
        or prediction.calibration
        not in (
            {"none", "uncalibrated baseline"}
            if spec.calibration.value == "none"
            else {spec.calibration.value}
        )
        or (spec.calibration.value != "none" and prediction.calibrated_before is None)
    ):
        reason = "prediction_identity_clock_partition_or_provenance"
    elif not sample.eligible or not sample.rules_known:
        reason = "unavailable_features_or_rules"
    # Quote, fee, signal and monetary risk refusals do not invalidate an otherwise
    # causal forecast. Keep their saved execution status separate from diagnostics.
    saved_decision: dict[str, Any] = next(
        (r for r in json.loads(cycle["result"])["decisions"] if r["ticker"] == sample.ticker), {}
    )
    return {
        "ticker": sample.ticker,
        "event_id": sample.event_id,
        "target_date": sample.target_date.isoformat(),
        "decision_time": sample.decision_time.isoformat(),
        "close_time": sample.close_time.isoformat(),
        "data_kind": data.data_kind,
        "dataset_version": data.dataset_version,
        "feature_version": data.feature_version,
        "feature_hash": sample.feature_hash,
        "source_versions": sample.versions,
        "sources": sorted(sample.sources),
        "features_available_at": sample.features_available_at.isoformat(),
        "cycle_id": cycle["id"],
        "cycle_digest": cycle["digest"],
        "poll_observations": 1,
        "prediction": prediction.model_dump(mode="json") if prediction else None,
        "model_refusals": bundle.refusals,
        "shadow_decision": {
            "status": saved_decision.get("status"),
            "reasons": saved_decision.get("reasons", []),
        },
        "status": "refused" if reason else "pending",
        "reason": reason,
        "outcome": None,
        "outcome_history": [],
        "outcome_revisions": 0,
    }


def _diagnostics(rows: list[dict[str, Any]], *, integrity_failed: bool) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        p = row["prediction"]
        if p is not None:
            groups[scientific_hash([row["data_kind"], p["model_hash"], p["calibration"]])].append(
                row
            )
    result = []
    for key, observations in sorted(groups.items()):
        first = observations[0]
        matched = [r for r in observations if r["status"] == "matched"]
        events = {r["event_id"] for r in matched}
        dates = {r["target_date"] for r in matched}
        eligible = not integrity_failed and len(events) >= MIN_EVENTS and len(dates) >= MIN_DATES
        metrics = None
        if eligible:
            sizes = Counter(r["event_id"] for r in matched)
            brier = loss = 0.0
            bins: dict[int, list[tuple[float, int, float]]] = defaultdict(list)
            for row in matched:
                p = float(row["prediction"]["probability_yes"])
                y = int(row["outcome"]["result"] == "yes")
                weight = 1 / (len(events) * sizes[row["event_id"]])
                brier += weight * (p - y) ** 2
                clipped = min(1 - 1e-15, max(1e-15, p))
                loss -= weight * (y * math.log(clipped) + (1 - y) * math.log(1 - clipped))
                bins[min(9, int(p * 10))].append((p, y, weight))
            metrics = {
                "event_weighted_brier": round(brier, 12),
                "event_weighted_log_loss": round(loss, 12),
                "log_loss_clip": 1e-15,
                "reliability_bins": [
                    {
                        "lower": b / 10,
                        "upper": (b + 1) / 10,
                        "contracts": len(values),
                        "weight": round(sum(w for _, _, w in values), 12),
                        "mean_probability": round(
                            sum(p * w for p, _, w in values) / sum(w for _, _, w in values), 12
                        ),
                        "observed_yes_rate": round(
                            sum(y * w for _, y, w in values) / sum(w for _, _, w in values), 12
                        ),
                    }
                    for b, values in sorted(bins.items())
                ],
            }
        result.append(
            {
                "group_id": key,
                "data_kind": first["data_kind"],
                "model_hash": first["prediction"]["model_hash"],
                "calibration": first["prediction"]["calibration"],
                "matched_contracts": len(matched),
                "independent_events": len(events),
                "independent_dates": len(dates),
                "status": "diagnostics_available" if eligible else "insufficient",
                "reason": None
                if eligible
                else "integrity_failure"
                if integrity_failed
                else "requires_10_matched_events_on_5_dates",
                "metrics": metrics,
            }
        )
    return result


def report(jobs: Jobs, monitor_id: str, *, as_of: datetime | None = None) -> dict[str, Any]:
    monitor, cycles = _cycles(jobs, monitor_id)
    protected: set[str] = set()
    binding = json.loads(monitor["model_binding"]) if monitor["model_binding"] else None
    research_model = None
    if binding and binding.get("snapshot"):
        if scientific_hash(
            {k: v for k, v in binding.items() if k != "binding_hash"}
        ) != binding.get("binding_hash"):
            raise ValueError("monitor protection binding mismatch")
        if binding.get("kind") == "research_weather_v1":
            research_model = PortableResearchModel.model_validate(binding["snapshot"])
            protected.update(research_model.protected_events)
        else:
            protected.update(FrozenWeather.model_validate(binding["snapshot"]).protected_events)
    verified = []
    failures = []
    lifecycle = Counter(c["status"] for c in cycles)
    budget = 0
    for cycle in cycles:
        if cycle["status"] not in {"completed", "failed"} or not cycle["result"]:
            continue
        root = jobs.root / "shadow" / identifier(monitor_id) / identifier(cycle["id"])
        try:
            result = json.loads(cycle["result"])
            if (
                scientific_hash(result) != cycle["digest"]
                or json.loads((root / "result.json").read_text()) != result
            ):
                raise ValueError("cycle differs from committed digest")
            if result.get("submission_enabled") is not False:
                raise ValueError("cycle submission boundary mismatch")
            for artifact in result["artifacts"]:
                path = (root / artifact["path"]).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError("artifact path escaped cycle")
                budget += path.stat().st_size
                if budget > MAX_BYTES:
                    raise ValueError("prospective evidence exceeds 256 MB budget")
            if not any(a["path"] == "decision-inputs.json" for a in result["artifacts"]):
                failures.append(
                    {"cycle_id": cycle["id"], "reason": "no_committed_prediction_inputs"}
                )
                continue
            inputs = _inputs(root, result)
            if StrategySpec.model_validate(inputs["spec"]).spec_hash() != monitor["spec_hash"]:
                raise ValueError("cycle strategy differs from frozen monitor")
            protected.update(inputs["data"]["protected_events"])
            data = ExperimentData.model_validate(inputs["data"])
            if (
                not is_reconciliation(result)
                and data.data_kind == "real"
                and result.get("model_binding") != binding
            ):
                raise ValueError("cycle model differs from frozen monitor")
            for contract in result["contracts"]:
                Market.model_validate(contract["market"])
            labels = _outcomes(root, result)
            verified.append((cycle, inputs, data, labels, result))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            failures.append({"cycle_id": cycle["id"], "reason": str(exc)[:300], "integrity": True})
            if budget > MAX_BYTES:
                break
    clocks = [s.decision_time for _, _, d, _, _ in verified for s in d.samples]
    clocks += [at(o["receipt"]["received_at"]) for _, _, _, labels, _ in verified for o in labels]
    cutoff = ensure_utc(as_of) if as_of is not None else max(clocks, default=None)
    selected: dict[str, dict[str, Any]] = {}
    originals: dict[str, Market] = {}
    excluded: set[str] = set()
    all_labels = [o for _, _, _, labels, _ in verified for o in labels]
    market_maps = {
        cycle["id"]: {c["ticker"]: Market.model_validate(c["market"]) for c in result["contracts"]}
        for cycle, _, _, _, result in verified
    }
    samples = sorted(
        [
            (s, cycle, inputs, result)
            for cycle, inputs, data, _, result in verified
            for s in data.samples
        ],
        key=lambda item: (item[0].decision_time, item[1]["id"], item[0].ticker),
    )
    for sample, cycle, inputs, _result in samples:
        markets = market_maps[cycle["id"]]
        if sample.event_id in protected or (
            research_model is not None
            and research_model.protects(
                series=sample.family,
                target_date=sample.target_date,
                event_id=sample.event_id,
            )
        ):
            excluded.add(sample.event_id)
            continue
        if (
            cutoff is None
            or sample.decision_time > cutoff
            or sample.decision_time >= sample.close_time
        ):
            continue
        row = selected.get(sample.ticker)
        market = markets.get(sample.ticker)
        if row is not None:
            row["poll_observations"] += 1
            if row["decision_time"] == sample.decision_time.isoformat():
                other = _observation(sample, inputs, cycle)
                if (
                    other["prediction"] != row["prediction"]
                    or other["feature_hash"] != row["feature_hash"]
                    or other["data_kind"] != row["data_kind"]
                ):
                    row.update(status="refused", reason="conflicting_predictions_at_same_clock")
            if (
                market is None
                or sample.ticker not in originals
                or terms(market) != terms(originals[sample.ticker])
            ):
                row.update(status="refused", reason="contract_terms_changed")
            if (
                row["target_date"] != sample.target_date.isoformat()
                or row["event_id"] != sample.event_id
            ):
                row.update(status="refused", reason="contract_event_or_date_changed")
            continue
        row = _observation(sample, inputs, cycle)
        if (
            market is None
            or market.event_ticker != sample.event_id
            or market.close_time != sample.close_time
        ):
            row.update(status="refused", reason="missing_matching_contract")
        else:
            originals[sample.ticker] = market
        selected[sample.ticker] = row
    for ticker, row in selected.items():
        if ticker not in originals or cutoff is None:
            continue
        labels = [label for o in all_labels if (label := _label(o, originals[ticker], cutoff))]
        labels.sort(key=lambda label: (label["available_at"], scientific_hash(label["receipt"])))
        # Receipt identity is immutable; duplicated polls never add independent outcomes.
        row["outcome_history"] = list({scientific_hash(o["receipt"]): o for o in labels}.values())
        valid = [o for o in row["outcome_history"] if o["reason"] is None]
        row["outcome_revisions"] = sum(
            (a["result"], a["settled_at"]) != (b["result"], b["settled_at"])
            for a, b in pairwise(valid)
        )
        if valid:
            latest = valid[-1]
            if (
                len(
                    {
                        (o["result"], o["settled_at"])
                        for o in valid
                        if o["available_at"] == latest["available_at"]
                    }
                )
                > 1
            ):
                row.update(status="refused", reason="conflicting_outcomes_at_same_clock")
            elif at(latest["available_at"]) <= at(row["decision_time"]):
                row.update(status="refused", reason="outcome_not_subsequent")
            else:
                row["outcome"] = latest
                if row["status"] == "pending":
                    row["status"] = "matched"
    rows = sorted(selected.values(), key=lambda r: (r["decision_time"], r["ticker"]))
    integrity_failed = any(f.get("integrity") for f in failures)
    if integrity_failed:
        # A damaged cycle may contain protection that cannot be verified. Do not expose
        # another cycle's forecasts while the union of protected boundaries is uncertain.
        rows = []
    groups = _diagnostics(rows, integrity_failed=integrity_failed)
    result = {
        "schema": "prospective-shadow-evaluation-v1",
        "monitor_id": monitor_id,
        "spec_hash": monitor["spec_hash"],
        "policy": {
            "minimum_matched_events": MIN_EVENTS,
            "minimum_matched_dates": MIN_DATES,
            "selection": "earliest_retained_preclose_observation_per_contract",
            "weighting": "equal_event_weight_with_equal_contract_weight_within_event",
        },
        "as_of": cutoff.isoformat() if cutoff else None,
        "status": "refused"
        if integrity_failed
        else "diagnostics_available"
        if any(g["metrics"] for g in groups)
        else "insufficient",
        "counts": {
            **{s: sum(r["status"] == s for r in rows) for s in ("pending", "refused", "matched")},
            "contracts": len(rows),
            "poll_observations": sum(r["poll_observations"] for r in rows),
            "independent_events": len({r["event_id"] for r in rows}),
            "independent_dates": len({r["target_date"] for r in rows}),
            "matched_events": len({r["event_id"] for r in rows if r["status"] == "matched"}),
            "matched_dates": len({r["target_date"] for r in rows if r["status"] == "matched"}),
            "excluded_protected_events": len(excluded),
            "protected_boundary_events": len(protected),
        },
        "cycle_statuses": dict(sorted(lifecycle.items())),
        "cycle_failures": failures,
        "evidence": [{"cycle_id": c["id"], "digest": c["digest"]} for c, *_ in verified],
        "observations": rows,
        "diagnostics": groups,
        "limitations": LIMITATIONS,
        "submission_enabled": False,
        "historical_validation": False,
        "performance": None,
    }
    return {**result, "report_hash": scientific_hash(result)}


def csv_report(value: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "report_hash",
            "as_of",
            "data_kind",
            "ticker",
            "event_id",
            "target_date",
            "decision_time",
            "status",
            "reason",
            "probability_yes",
            "official_result",
            "outcome_available_at",
            "outcome_revisions",
            "poll_observations",
        ]
    )
    for row in value["observations"]:
        fields = [
            value["report_hash"],
            value["as_of"],
            row["data_kind"],
            row["ticker"],
            row["event_id"],
            row["target_date"],
            row["decision_time"],
            row["status"],
            row["reason"],
            (row["prediction"] or {}).get("probability_yes"),
            (row["outcome"] or {}).get("result"),
            (row["outcome"] or {}).get("available_at"),
            row["outcome_revisions"],
            row["poll_observations"],
        ]
        writer.writerow(
            [
                "'" + f if isinstance(f, str) and f.startswith(("=", "+", "-", "@")) else f
                for f in fields
            ]
        )
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--monitor", required=True)
    parser.add_argument("--as-of", type=at)
    args = parser.parse_args()
    print(  # noqa: T201 - local read-only replay command
        json.dumps(
            report(Jobs(args.workspace), args.monitor, as_of=args.as_of),
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
