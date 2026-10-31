"""Causal paper execution, caps, recovery and settlement; all successful cases synthetic."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.accounting import account_hash, reproduce, verify_export
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from tests.paper_support import paper_inputs
from tests.unit.test_tracking import monitor


def test_causal_fills_accounting_and_offline_json_reproduction() -> None:
    inputs = paper_inputs()
    original = json.dumps(inputs, sort_keys=True)
    result = reproduce(inputs)
    assert result == reproduce(json.loads(original))
    assert json.dumps(inputs, sort_keys=True) == original
    assert result["summary"]["data_kind"] == "synthetic"
    assert result["summary"]["cash"] == "998.960000"
    assert result["summary"]["fees"] == "0.040000"
    assert result["summary"]["equity_at_cost"] == "999.960000"
    assert result["summary"]["realized_pnl"] == "-0.040000"
    assert result["summary"]["positions"][0]["quantity"] == "2.00"
    execution = result["executions"][0]
    assert execution["status"] == "filled"
    assert execution["fills"][0]["executed_at"] > result["decisions"][0]["decision_time"]
    assert execution["fills"][0]["yes_price"] == "0.5000"
    assert not result["submission_enabled"]


@pytest.mark.parametrize("case", ["missing", "future", "too_early", "closed", "crossed"])
def test_causal_execution_refusals(case: str) -> None:
    inputs = paper_inputs()
    ticker, book = next(iter(inputs["execution_books"].items()))
    when = datetime.fromisoformat(inputs["decision_inputs"]["data"]["samples"][0]["decision_time"])
    if case == "missing":
        inputs["execution_books"] = {}
    elif case == "future":
        book["received_at"] = (when + timedelta(seconds=10)).isoformat()
    elif case == "too_early":
        book["received_at"] = when.isoformat()
    elif case == "closed":
        book["received_at"] = inputs["close_times"][ticker]
        inputs["as_of"] = book["received_at"]
    else:
        book["asks"][0]["price"] = ".40"
    result = reproduce(inputs)
    assert not result["state"]["ledger"]["fills"]
    assert result["summary"]["cash"] == "1000.000000"
    assert result["executions"][0]["status"] == "blocked"


def test_price_improvement_clamp_partial_ioc_fok_and_liquidity_not_reused() -> None:
    inputs = paper_inputs()
    ticker, book = next(iter(inputs["execution_books"].items()))
    book["asks"][0].update(price=".48", quantity="3.00")
    first = reproduce(inputs)
    assert first["executions"][0]["fills"][0]["yes_price"] == "0.5000"
    again = paper_inputs(first["state"], seconds=60)
    again["execution_books"][ticker]["asks"] = book["asks"]
    second = reproduce(again)
    assert second["executions"][0]["order"]["filled_quantity"] == "1.00"
    assert second["executions"][0]["unsubmitted_quantity"] == "1.00"
    assert second["summary"]["positions"][0]["quantity"] == "3.00"
    third_inputs = paper_inputs(second["state"], seconds=120)
    third_inputs["execution_books"][ticker]["asks"] = book["asks"]
    third = reproduce(third_inputs)
    assert third["executions"][0]["reason"] == "liquidity_exhausted"
    assert third["summary"]["fill_count"] == 2
    opposite_change = paper_inputs(third["state"], seconds=150)
    opposite_change["execution_books"][ticker]["asks"] = book["asks"]
    opposite_change["execution_books"][ticker]["bids"][0]["price"] = ".41"
    assert reproduce(opposite_change)["executions"][0]["reason"] == "liquidity_exhausted"
    # A repeated old payload after an intervening changed book still has no capacity.
    changed_inputs = paper_inputs(third["state"], seconds=180)
    changed = reproduce(changed_inputs)
    old = paper_inputs(changed["state"], seconds=240)
    old["execution_books"][ticker]["asks"] = book["asks"]
    assert reproduce(old)["executions"][0]["reason"] == "liquidity_exhausted"
    fok = paper_inputs()
    fok["decision_inputs"]["spec"]["execution"]["time_in_force"] = "fill_or_kill"
    fok["execution_books"][ticker]["asks"][0]["quantity"] = "1.00"
    refused = reproduce(fok)
    assert not refused["state"]["ledger"]["fills"]
    assert refused["executions"][0]["reason"] == "insufficient_fok_capacity"


def test_fee_transition_expiry_conflict_and_execution_risk() -> None:
    inputs = paper_inputs()
    version = FeeVersion.model_validate(inputs["decision_inputs"]["fee_versions"][0])
    assert version.policy is not None
    when = datetime.fromisoformat(inputs["decision_inputs"]["data"]["samples"][0]["decision_time"])
    boundary = when + timedelta(seconds=1)
    earlier = version.revalidated(policy=version.policy.revalidated(effective_to=boundary))
    later = version.revalidated(
        policy=version.policy.revalidated(
            effective_from=boundary,
            schedule=version.policy.schedule.revalidated(quadratic_coefficient=Decimal(".14")),
        )
    )
    inputs["decision_inputs"]["fee_versions"] = [
        v.model_dump(mode="json") for v in (earlier, later)
    ]
    result = reproduce(inputs)
    assert result["decisions"][0]["fee_evidence"]["version"] == earlier.version
    assert result["executions"][0]["fee_evidence"]["version"] == later.version
    assert result["summary"]["fees"] == "0.070000"
    inputs["decision_inputs"]["fee_versions"] = [earlier.model_dump(mode="json")]
    assert reproduce(inputs)["executions"][0]["reason"] == "uncertified_or_outside_fee_interval"
    inputs["decision_inputs"]["fee_versions"] = [version.model_dump(mode="json")]
    inputs["execution_series_fees"] = [
        {"series": "MENTIONS", "fee_type": "quadratic", "fee_multiplier": "2"}
    ]
    assert reproduce(inputs)["executions"][0]["reason"] == "series_metadata_conflict"
    # An execution-time fee increase can erase the intended edge; never reuse decision approval.
    assert later.policy is not None
    punitive = later.revalidated(
        policy=later.policy.revalidated(
            schedule=later.policy.schedule.revalidated(quadratic_coefficient=Decimal("1"))
        )
    )
    inputs["execution_series_fees"] = []
    inputs["decision_inputs"]["fee_versions"] = [
        v.model_dump(mode="json") for v in (earlier, punitive)
    ]
    assert reproduce(inputs)["executions"][0]["reason"] == "execution_risk_rejected"


@pytest.mark.parametrize("gate", ["model", "fee", "protected", "real_with_controlled_fees"])
def test_fail_closed_missing_evidence_and_protected_boundaries(gate: str) -> None:
    inputs = paper_inputs()
    if gate == "model":
        inputs["decision_inputs"]["bundle"]["records"] = []
    elif gate == "fee":
        inputs["decision_inputs"]["fee_versions"] = []
    elif gate == "protected":
        sample = inputs["decision_inputs"]["data"]["samples"][0]
        inputs["decision_inputs"]["data"]["protected_events"] = [sample["event_id"]]
    else:
        inputs["decision_inputs"]["data"]["data_kind"] = "real"
        inputs["decision_inputs"]["bundle"]["model_metadata"]["data_kind"] = "real"
    result = reproduce(inputs)
    assert not result["state"]["ledger"]["fills"]
    assert not result["executions"]


def outcome(inputs: dict[str, Any], result: str = "yes") -> dict[str, Any]:
    ticker = next(iter(inputs["close_times"]))
    settled = datetime.fromisoformat(inputs["close_times"][ticker]) + timedelta(seconds=1)
    available = settled + timedelta(hours=1)
    return {
        "ticker": ticker,
        "result": result,
        "settled_at": settled.isoformat(),
        "available_at": available.isoformat(),
        "receipt": {
            "received_at": available.isoformat(),
            "status": 200,
            "sha256": "sha256:" + "b" * 64,
            "raw_ref": "CONTROLLED.json",
        },
    }


def test_settlement_availability_duplicate_and_conflicting_outcomes() -> None:
    first = reproduce(paper_inputs())
    inputs = paper_inputs(first["state"], seconds=7200)
    observed = outcome(inputs)
    inputs["outcomes"] = [observed, observed]
    inputs["as_of"] = (
        datetime.fromisoformat(observed["available_at"]) + timedelta(minutes=5)
    ).isoformat()
    result = reproduce(inputs)
    assert result["summary"]["settlement_count"] == 1
    assert result["summary"]["cash"] == "1000.960000"
    assert result["summary"]["realized_pnl"] == "0.960000"
    assert not result["summary"]["positions"]
    assert datetime.fromisoformat(
        result["settlements"][0]["settlement"]["settled_at"]
    ) == datetime.fromisoformat(observed["available_at"])
    duplicate = paper_inputs(result["state"], seconds=8000)
    duplicate["outcomes"] = [observed]
    assert reproduce(duplicate)["summary"]["settlement_count"] == 1
    duplicate["outcomes"] = [{**observed, "result": "no"}]
    with pytest.raises(ValueError, match="conflicting"):
        reproduce(duplicate)
    invalid = paper_inputs(first["state"], seconds=7200)
    invalid["outcomes"] = [observed]
    invalid["outcomes"][0]["receipt"]["status"] = 429
    with pytest.raises(ValueError, match="official outcome"):
        reproduce(invalid)


def test_transactional_restart_pause_stale_commit_and_offline_chain(tmp_path: Path) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    inputs = paper_inputs()
    result = {
        "detail": "CONTROLLED synthetic accounting",
        "paper_inputs": inputs,
        "paper": reproduce(inputs),
        "submission_enabled": False,
    }
    claim = store.claim()
    assert claim
    assert store.finish(mid, claim[1], result)
    assert not store.finish(mid, claim[1], result)
    before = store.get(mid, export=True)
    assert before is not None
    assert before["fills"] == []  # observed fills never replaced by simulation
    assert verify_export(before)["paper_cycles"] == 1
    store = TrackingStore(Jobs(tmp_path))
    store.recover()
    assert store.get(mid, export=True) == before
    store.control(mid, "pause")
    store.control(mid, "resume")
    next_claim = store.claim()
    assert next_claim
    with pytest.raises(ValueError, match="stale/corrupt"):
        store.finish(mid, next_claim[1], result)
    assert store.get(mid)["paper_account"] == before["paper_account"]  # type: ignore[index]
    store.control(mid, "pause")
    assert not store.finish(mid, next_claim[1], result)
    restored = store.get(mid, export=True)
    assert restored
    assert verify_export(restored)["verified"]
    corrupted = json.loads(json.dumps(restored))
    corrupted["cycles"][-1]["result"]["paper"]["state"]["ledger"]["cash"] = "9999"
    with pytest.raises(ValueError, match="checksum"):
        verify_export(corrupted)
    # Account corruption is refused on reads and cannot reset the bankroll.
    with store.jobs.connect() as db:
        db.execute("UPDATE shadow_accounts SET digest='bad'")
    with pytest.raises(ValueError, match="checksum"):
        store.get(mid)
    with store.jobs.connect() as db:
        db.execute("DELETE FROM shadow_accounts")
    with pytest.raises(ValueError, match="no bankroll reset"):
        store.get(mid)


def test_actual_positions_enforce_per_event_and_trade_caps() -> None:
    before = None
    for index in range(6):
        inputs = paper_inputs(before, seconds=index * 60)
        spec = inputs["decision_inputs"]["spec"]
        spec["position_sizing"].update(contracts="40", max_contracts="1000")
        book = next(iter(inputs["execution_books"].values()))
        book["asks"][0]["quantity"] = "1000"
        book["sequence"] = index
        inputs["decision_inputs"]["data"]["samples"][0]["book"]["asks"][0]["quantity"] = "1000"
        result = reproduce(inputs)
        before = result["state"]
        if index < 4:
            assert result["executions"][0]["status"] == "filled"
        else:
            assert result["decisions"][0]["status"] == "risk_rejected"
    assert Decimal(result["summary"]["positions"][0]["total_cost"]) == 80
    assert Decimal(result["summary"]["fees"]) == Decimal("2.8")
    inputs = paper_inputs()
    inputs["decision_inputs"]["spec"]["position_sizing"].update(
        contracts="100", max_contracts="1000"
    )
    assert reproduce(inputs)["decisions"][0]["status"] == "risk_rejected"


def test_account_hash_and_time_provenance_cannot_be_reset() -> None:
    first = reproduce(paper_inputs())
    earlier = paper_inputs(first["state"])
    with pytest.raises(ValueError, match="clock"):
        reproduce(earlier)
    earlier["before_hash"] = scientific_hash(None)
    with pytest.raises(ValueError, match="checksum"):
        reproduce(earlier)
    mismatched = paper_inputs(first["state"], seconds=60)
    mismatched["decision_inputs"]["data"]["data_kind"] = "real"
    with pytest.raises(ValueError, match="provenance"):
        reproduce(mismatched)
    assert account_hash(first["state"]) == first["state_hash"]


def test_no_side_clamp_and_official_no_settlement() -> None:
    inputs = paper_inputs()
    spec = inputs["decision_inputs"]["spec"]
    spec["side"] = "no"
    spec["entry_rules"]["all_of"][0]["threshold"] = ".1"
    inputs["decision_inputs"]["bundle"]["records"][0]["probability_yes"] = ".25"
    next(iter(inputs["execution_books"].values()))["bids"][0]["price"] = ".42"
    first = reproduce(inputs)
    fill = first["executions"][0]["fills"][0]
    assert fill["contract"]["side"] == "no"
    assert fill["yes_price"] == "0.4000"
    assert first["summary"]["cash"] == "998.760000"
    settled = paper_inputs(first["state"], seconds=8000)
    settled["outcomes"] = [outcome(settled, "no")]
    assert reproduce(settled)["summary"]["cash"] == "1000.760000"


def test_uncommitted_outbox_is_retained_without_applying_fills(tmp_path: Path) -> None:
    from tests.unit.test_tracking import REPO

    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    claim = store.claim()
    assert claim
    root = tmp_path / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    uncommitted = {"paper": reproduce(paper_inputs())}
    original = json.dumps(uncommitted).encode()
    (root / "result.json").write_bytes(original)
    ShadowRunner(store, REPO).fail(mid, claim[1], "CONTROLLED crash before account commit")
    value = store.get(mid, export=True)
    assert value
    assert value["paper_account"] is None
    assert value["cycles"][0]["status"] == "failed"
    assert (root / "uncommitted-result.json").read_bytes() == original
    assert json.loads((root / "result.json").read_text()) == value["cycles"][0]["result"]
    assert verify_export(value)["paper_cycles"] == 0


def test_total_deployment_across_distinct_events_remains_fee_inclusive() -> None:
    state = None
    for index in range(25):
        inputs = paper_inputs(state, seconds=index * 60)
        old_ticker, book = next(iter(inputs["execution_books"].items()))
        ticker, event = f"MENTIONS-CONTROLLED-{index}", f"CONTROLLED-E{index}"
        sample = inputs["decision_inputs"]["data"]["samples"][0]
        sample.update(ticker=ticker, event_id=event)
        sample["book"]["market_ticker"] = ticker
        sample["book"]["asks"][0]["quantity"] = "1000"
        inputs["decision_inputs"]["bundle"]["records"][0].update(ticker=ticker, event_id=event)
        inputs["decision_inputs"]["spec"]["position_sizing"].update(
            contracts="40", max_contracts="1000"
        )
        book["market_ticker"] = ticker
        book["asks"][0]["quantity"] = "1000"
        inputs["execution_books"] = {ticker: book}
        inputs["event_ids"] = {ticker: event}
        inputs["close_times"] = {ticker: inputs["close_times"][old_ticker]}
        result = reproduce(inputs)
        state = result["state"]
        if index < 24:
            assert result["executions"][0]["status"] == "filled"
        else:
            assert result["decisions"][0]["status"] == "risk_rejected"
            assert not result["executions"]
    assert state is not None
    assert len(state["event_ids"]) == 25
    assert result["summary"]["fill_count"] == 24
    assert Decimal(result["summary"]["fees"]) == Decimal("16.80")
    assert Decimal(result["summary"]["cash"]) == Decimal("503.20")
