"""Receipt-time reporting, synthetic diagnostic math and authentic fail-closed evidence."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.prospective import at, csv_report, report
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import outcomes
from tests.exchange.test_gateway_http import _market_body
from tests.integration.prospective_fixture import commit, controlled_inputs, seed
from tests.unit.test_public_families import WHEN
from tests.unit.test_tracking import contract, monitor


def test_dedup_revisions_event_weighted_diagnostics_and_determinism(tmp_path: Path) -> None:
    receipt = seed(tmp_path / "workspace")
    value = receipt["report"]
    assert value == report(Jobs(tmp_path / "workspace"), receipt["monitor_id"])
    assert value["status"] == "diagnostics_available"
    assert value["counts"] == {
        "pending": 1,
        "refused": 1,
        "matched": 11,
        "contracts": 13,
        "poll_observations": 39,
        "independent_events": 12,
        "independent_dates": 12,
        "matched_events": 10,
        "matched_dates": 10,
        "excluded_protected_events": 0,
        "protected_boundary_events": 1,
    }
    assert value["cycle_failures"] == []
    assert value["performance"] is None
    assert not value["historical_validation"]
    assert not value["submission_enabled"]
    group = value["diagnostics"][0]
    assert group["data_kind"] == "synthetic"
    assert group["metrics"]["event_weighted_brier"] == pytest.approx(0.0875)
    assert sum(b["weight"] for b in group["metrics"]["reliability_bins"]) == pytest.approx(1)
    first = value["observations"][0]
    assert first["outcome_revisions"] == 1
    assert first["outcome"]["result"] == "no"
    assert first["poll_observations"] == 3
    assert first["prediction"]["probability_yes"] == "0.75"
    assert first["shadow_decision"]["status"] == "blocked"
    assert "sized_book" in first["shadow_decision"]["reasons"]
    assert len(first["outcome_history"]) == 2
    old = report(
        Jobs(tmp_path / "workspace"), receipt["monitor_id"], as_of=WHEN + timedelta(days=14)
    )
    assert old["observations"][0]["outcome"]["result"] == "yes"
    assert old["observations"][0]["outcome_revisions"] == 0
    assert old["diagnostics"][0]["metrics"]["event_weighted_brier"] == 0.0625
    missing = next(r for r in value["observations"] if r["status"] == "refused")
    assert missing["reason"] == "missing_or_ambiguous_prediction"
    assert missing["outcome"]["result"] == "yes"
    assert "KXHIGHPHIL-26NOV06" not in json.dumps(value["observations"])
    assert csv_report(value) == csv_report(value)
    assert len(csv_report(value).splitlines()) == 14


def test_late_receipts_cannot_be_backdated_to_settlement_and_restart_is_identical(
    tmp_path: Path,
) -> None:
    receipt = seed(tmp_path / "workspace")
    jobs = Jobs(tmp_path / "workspace")
    mid = receipt["monitor_id"]
    # Settlement is one minute after close; the official HTTP response arrives an hour later.
    early = report(jobs, mid, as_of=WHEN + timedelta(hours=1, minutes=30))
    assert early["counts"]["pending"] == 2  # the event has two strike contracts
    assert early["counts"]["matched"] == 0
    assert all(g["metrics"] is None for g in early["diagnostics"])
    assert all(r["outcome"] is None for r in early["observations"])
    before = report(jobs, mid)
    TrackingStore(Jobs(tmp_path / "workspace")).recover()
    assert report(Jobs(tmp_path / "workspace"), mid) == before


@pytest.mark.parametrize(
    "case",
    [
        "holdout",
        "fit_future",
        "calibration_clock",
        "wrong_model",
        "wrong_feature",
        "wrong_provenance",
        "ambiguous",
        "absent",
    ],
)
def test_invalid_forecasts_refuse_without_fallback_or_metrics(tmp_path: Path, case: str) -> None:
    store = TrackingStore(Jobs(tmp_path / "workspace"))
    mid = monitor(store)
    inputs, contracts, _ = controlled_inputs()
    record = inputs["bundle"]["records"][0]
    if case == "holdout":
        record["partition"] = "holdout"
    elif case == "fit_future":
        record["fitted_before"] = (WHEN + timedelta(days=1)).isoformat()
    elif case == "calibration_clock":
        inputs["spec"]["calibration"] = "platt"
        inputs["spec"]["model_kind"] = "domain_statistical"
        record["calibration"] = "platt"
    elif case == "wrong_model":
        record["model_hash"] = "sha256:" + "b" * 64
    elif case == "wrong_feature":
        record["feature_version"] = "sha256:" + "b" * 64
    elif case == "wrong_provenance":
        inputs["bundle"]["model_metadata"]["data_kind"] = "real"
    elif case == "ambiguous":
        inputs["bundle"]["records"].append(dict(record))
    else:
        inputs["bundle"]["records"] = []
    commit(store, mid, inputs, contracts, [])
    value = report(store.jobs, mid)
    assert value["observations"][0]["status"] == "refused"
    assert all(g["metrics"] is None for g in value["diagnostics"])


@pytest.mark.parametrize(
    "case", ["provisional", "changed", "future_settlement", "payout", "not_final"]
)
def test_invalid_official_outcomes_remain_pending_with_receipt_refusals(
    tmp_path: Path, case: str
) -> None:
    store = TrackingStore(Jobs(tmp_path / "workspace"))
    mid = monitor(store)
    inputs, contracts, bodies = controlled_inputs()
    body = dict(
        bodies[0],
        status="finalized",
        result="yes",
        settlement_value_dollars="1.0000",
        settlement_ts=(WHEN + timedelta(hours=1, minutes=1)).isoformat(),
    )
    if case == "provisional":
        body["is_provisional"] = True
    elif case == "changed":
        body["floor_strike"] = 88
    elif case == "future_settlement":
        body["settlement_ts"] = (WHEN + timedelta(days=1)).isoformat()
    elif case == "payout":
        body["settlement_value_dollars"] = "0.0000"
    else:
        body["status"] = "settled"
    commit(store, mid, inputs, contracts, [(body, (WHEN + timedelta(hours=2)).isoformat())])
    value = report(store.jobs, mid)
    first = value["observations"][0]
    assert first["status"] == "pending"
    assert first["outcome"] is None
    assert first["outcome_history"][0]["reason"]
    assert all(g["metrics"] is None for g in value["diagnostics"])


def test_integrity_failure_suppresses_all_metrics_and_interruption_is_visible(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    receipt = seed(workspace)
    store = TrackingStore(Jobs(workspace))
    mid = receipt["monitor_id"]
    cycle = receipt["report"]["evidence"][0]["cycle_id"]
    (workspace / "shadow" / mid / cycle / "decision-inputs.json").write_text("{}")
    store.control(mid, "resume")
    assert store.claim()
    store.recover()
    value = report(store.jobs, mid)
    assert value["status"] == "refused"
    assert value["cycle_statuses"]["interrupted"] == 1
    assert value["cycle_failures"][0]["integrity"]
    assert value["observations"] == []
    assert all(g["metrics"] is None for g in value["diagnostics"])


def test_scarce_authentic_evidence_never_invents_probabilities_or_diagnostics(
    tmp_path: Path,
) -> None:
    value = seed(tmp_path / "authentic", authentic=True)["report"]
    assert value["status"] == "insufficient"
    assert not value["cycle_failures"]
    assert value["counts"]["matched"] == 0
    assert value["counts"]["refused"] == 24
    assert value["counts"]["poll_observations"] == 48
    assert value["diagnostics"] == []
    assert all(r["prediction"] is None and r["data_kind"] == "real" for r in value["observations"])


def test_finalized_contracts_are_rechecked_without_starving_pending_contracts(
    tmp_path: Path,
) -> None:
    contracts = [contract() for _ in range(14)]
    for i, item in enumerate(contracts):
        ticker = item["ticker"] + str(i)
        item["ticker"] = ticker
        item["market"]["market"]["ticker"] = ticker
        item["market"]["market"]["rules"]["market_ticker"] = ticker
        if i >= 7:
            item["outcome"] = {"result": "yes"}
    seen = []

    def wire(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path.split("/")[-1])
        assert request.method == "GET"
        return httpx.Response(200, json={"market": dict(_market_body(), ticker=seen[-1])})

    first = asyncio.run(
        outcomes(
            tmp_path / "first",
            contracts,
            transport=httpx.MockTransport(wire),
            clock=SimulatedClock(WHEN),
        )
    )
    assert len(seen) == 10
    assert first["outcome_deferred"] == 4
    assert sum(c["outcome"] is None for c in contracts if c["ticker"] in seen) == 5
    for c in contracts:
        if c["ticker"] in seen:
            c["last_attempt"] = WHEN.isoformat()
    seen.clear()
    asyncio.run(
        outcomes(
            tmp_path / "second",
            contracts,
            transport=httpx.MockTransport(wire),
            clock=SimulatedClock(WHEN),
        )
    )
    assert all(c["ticker"] in seen for c in contracts if not c["last_attempt"])


def test_naive_cutoff_is_rejected(tmp_path: Path) -> None:
    receipt = seed(tmp_path / "workspace")
    with pytest.raises(ValueError, match="naive"):
        report(Jobs(tmp_path / "workspace"), receipt["monitor_id"], as_of=WHEN.replace(tzinfo=None))
    assert at(WHEN.isoformat()) == WHEN


def test_csv_neutralizes_formula_cells() -> None:
    inputs, _, _ = controlled_inputs()
    row: dict[str, Any] = {
        "ticker": "=formula",
        "event_id": "+formula",
        "target_date": "date",
        "data_kind": "synthetic",
        "decision_time": "clock",
        "status": "refused",
        "reason": "@bad",
        "prediction": None,
        "outcome": None,
        "outcome_revisions": 0,
        "poll_observations": 1,
    }
    assert inputs
    result = csv_report({"report_hash": "hash", "as_of": None, "observations": [row]})
    assert "'=formula" in result
    assert "'+formula" in result
    assert "'@bad" in result


def test_later_protection_excludes_all_prior_observations_and_nested_predictions(
    tmp_path: Path,
) -> None:
    store = TrackingStore(Jobs(tmp_path / "workspace"))
    mid = monitor(store)
    inputs, contracts, _ = controlled_inputs()
    commit(store, mid, inputs, contracts, [])
    protected = inputs["data"]["samples"][0]["event_id"]
    assert protected in json.dumps(report(store.jobs, mid)["observations"])
    inputs["data"]["protected_events"].append(protected)
    commit(store, mid, inputs, contracts, [])
    value = report(store.jobs, mid)
    assert protected not in json.dumps(value)
    assert value["counts"]["excluded_protected_events"] == 1
    assert value["counts"]["contracts"] == 11


def test_rehashed_authentic_contract_forgery_is_refused(tmp_path: Path) -> None:
    workspace = tmp_path / "authentic"
    receipt = seed(workspace, authentic=True)
    jobs = Jobs(workspace)
    cycle = receipt["report"]["evidence"][0]["cycle_id"]
    path = workspace / "shadow" / receipt["monitor_id"] / cycle / "result.json"
    result = json.loads(path.read_text())
    result["contracts"][0]["market"]["strike"]["floor_strike"] = "999"
    # Retain structural validity while changing contract rules independently of source bytes.
    result["contracts"][0]["market"]["rules"]["rules_primary"] += " FORGED"
    path.write_text(json.dumps(result))
    with jobs.connect() as db:
        db.execute(
            "UPDATE shadow_cycles SET result=?, digest=? WHERE id=?",
            (json.dumps(result), scientific_hash(result), cycle),
        )
    value = report(jobs, receipt["monitor_id"])
    assert value["status"] == "refused"
    assert value["cycle_failures"][0]["integrity"]


def test_same_clock_conflicting_outcomes_refuse_instead_of_choosing_best(tmp_path: Path) -> None:
    store = TrackingStore(Jobs(tmp_path / "workspace"))
    mid = monitor(store)
    inputs, contracts, bodies = controlled_inputs()
    body = dict(
        bodies[0],
        status="finalized",
        result="yes",
        settlement_value_dollars="1.0000",
        settlement_ts=(WHEN + timedelta(hours=1, minutes=1)).isoformat(),
    )
    clock = (WHEN + timedelta(hours=2)).isoformat()
    opposite = dict(body, result="no", settlement_value_dollars="0.0000")
    commit(store, mid, inputs, contracts, [(body, clock), (opposite, clock)])
    first = report(store.jobs, mid)["observations"][0]
    assert first["status"] == "refused"
    assert first["reason"] == "conflicting_outcomes_at_same_clock"
    assert first["outcome"] is None
