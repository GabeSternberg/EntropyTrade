"""Controlled shadow evidence: no fixture is empirical performance or an exchange order."""

import asyncio
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import uuid4

import httpx
import pytest

from entropytrade.agents.fixture import demo_specs
from entropytrade.api.jobs import Jobs
from entropytrade.domain.strategy import CalibrationMethod, ModelKind, StrategySpec
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.experiments.engine import FeePolicy
from entropytrade.tracking.evaluate import evaluate
from entropytrade.tracking.replay import decision_inputs, reproduce
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import collect, outcomes, reservations
from tests.exchange.test_gateway_http import _market_body
from tests.r4_support import nonweather
from tests.unit.test_public_families import WHEN, listing, spot
from tests.unit.test_workbench_http import ControlledProcess, exchange

if TYPE_CHECKING:
    from entropytrade.api.server import WorkbenchServer

REPO = Path(__file__).resolve().parents[3]


def saved(store: TrackingStore, *, family: str = "weather") -> dict[str, Any]:
    spec = demo_specs()[0]
    if family == "bitcoin":
        spec = spec.revalidated(
            market_universe=spec.market_universe.revalidated(
                series_tickers=("KXBTC",), market_tickers=(), event_tickers=()
            )
        )
    job_id = store.jobs.create(
        {
            "idea": "CONTROLLED monitor setup",
            "family": family,
            "mode": "recorded" if family == "weather" else "public",
        }
    )
    store.jobs.update(
        job_id,
        "completed",
        "CONTROLLED",
        status="completed",
        result={
            "data_kind": "real",
            "proposals": [{"candidate_id": "c0", "spec": spec.model_dump(mode="json")}],
        },
    )
    return {"job_id": job_id, "candidate_id": "c0", "interval_seconds": 60}


def monitor(store: TrackingStore, *, family: str = "weather") -> str:
    return store.create(saved(store, family=family))


def ready() -> tuple[StrategySpec, ExperimentData, PredictionBundle, FeePolicy]:
    data, provider, research, config = nonweather()
    spec = StrategySpec.model_validate(research["candidates"][0]["spec"])
    data = data.revalidated(samples=(data.samples[50],))
    assert config.fee_policy is not None
    fee = config.fee_policy.revalidated(certified=True, evidence_hash="sha256:" + "b" * 64)
    return spec, data, provider.bundle, fee


def forbid_shadow_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("blocked evidence must not invoke the strategy or risk evaluation")

    monkeypatch.setattr("entropytrade.tracking.evaluate.compile_strategy", lambda _spec: unexpected)
    monkeypatch.setattr("entropytrade.tracking.evaluate.RiskEngine.evaluate", unexpected)


def test_deterministic_decisions_reserve_once_without_fills_or_target_leakage() -> None:
    spec, data, bundle, fee = ready()
    result = evaluate(spec, data, bundle, fee=fee)
    assert result == evaluate(spec, data, bundle, fee=fee)
    assert result[0]["status"] == "shadow_eligible"
    assert result[0]["intent"]
    assert result[0]["risk"]["approved"]
    changed = data.revalidated(samples=(data.samples[0].revalidated(outcome=None),))
    assert evaluate(spec, changed, bundle, fee=fee) == result
    again = evaluate(spec, data, bundle, fee=fee, reservations=tuple(result))
    assert again[0]["status"] == "no_signal"  # pending max-contract cap survives repeated decisions
    assert again[0]["intent"] is None
    assert "outcome" not in result[0]
    protected = data.revalidated(protected_events=frozenset({data.samples[0].event_id}))
    assert evaluate(spec, protected, bundle, fee=fee) == []


@pytest.mark.parametrize("boundary", ["dataset", "model", "both"])
def test_offline_replay_inputs_withhold_targets_and_protected_features(boundary: str) -> None:
    spec, data, bundle, fee = ready()
    inputs = decision_inputs(spec, data, bundle, fee=fee)
    assert reproduce(json.loads(json.dumps(inputs))) == evaluate(spec, data, bundle, fee=fee)
    assert all(s["outcome"] is None for s in inputs["data"]["samples"])
    assert not any(p["partition"] == "holdout" for p in inputs["bundle"]["records"])
    event_id = data.samples[0].event_id
    protected = data.revalidated(
        protected_events=frozenset({event_id}) if boundary in {"dataset", "both"} else frozenset()
    )
    protected_bundle = bundle.revalidated(
        model_metadata={"split": {"holdout": [event_id]}} if boundary in {"model", "both"} else {}
    )
    assert evaluate(spec, protected, protected_bundle, fee=fee) == []
    inputs = decision_inputs(spec, protected, protected_bundle, fee=fee)
    assert inputs["data"]["samples"] == []
    assert inputs["bundle"]["records"] == []
    assert reproduce(json.loads(json.dumps(inputs))) == []
    blocked = evaluate(spec, data, bundle, fee=fee, acquisition_complete=False)[0]
    assert blocked["status"] == "blocked"
    assert blocked["reasons"] == ["complete_acquisition"]


@pytest.mark.parametrize(
    ("requested", "actual", "eligible"),
    [
        (CalibrationMethod.NONE, "none", True),
        (CalibrationMethod.NONE, "uncalibrated baseline", True),
        (CalibrationMethod.PLATT, "platt", True),
        (CalibrationMethod.ISOTONIC, "isotonic", True),
        (CalibrationMethod.NONE, "platt", False),
        (CalibrationMethod.NONE, "isotonic", False),
        (CalibrationMethod.PLATT, "none", False),
        (CalibrationMethod.PLATT, "uncalibrated baseline", False),
        (CalibrationMethod.PLATT, "isotonic", False),
        (CalibrationMethod.ISOTONIC, "none", False),
        (CalibrationMethod.ISOTONIC, "uncalibrated baseline", False),
        (CalibrationMethod.ISOTONIC, "platt", False),
        (CalibrationMethod.NONE, "unknown", False),
    ],
)
def test_requested_calibration_controls_intentions_and_survives_offline_replay(
    requested: CalibrationMethod, actual: str, eligible: bool
) -> None:
    spec, data, bundle, fee = ready()
    spec = spec.revalidated(calibration=requested, model_kind=ModelKind.LOGISTIC_REGRESSION)
    record = bundle.records[0].revalidated(
        calibration=actual,
        calibrated_before=data.samples[0].decision_time - timedelta(seconds=1)
        if actual in {"platt", "isotonic"}
        else None,
    )
    bundle = bundle.revalidated(records=(record,))
    rows = evaluate(spec, data, bundle, fee=fee)
    row = rows[0]
    if eligible:
        assert row["status"] == "shadow_eligible"
        assert row["intent"] is not None
        assert row["risk"]["approved"]
    else:
        assert row["status"] == "blocked"
        assert row["intent"] is None
        assert row["risk"] is None
        assert row["reasons"] == ["requested_calibration"]
    inputs = decision_inputs(spec, data, bundle, fee=fee)
    assert reproduce(json.loads(json.dumps(inputs))) == rows


@pytest.mark.parametrize("calibration", ["none", "uncalibrated baseline", "platt", "isotonic"])
@pytest.mark.parametrize("clock", ["missing", "before", "at", "after"])
def test_calibration_requires_known_availability_for_calibrated_predictions(
    calibration: str, clock: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, data, bundle, fee = ready()
    calibrated = calibration in {"platt", "isotonic"}
    spec = spec.revalidated(
        calibration=CalibrationMethod(calibration) if calibrated else CalibrationMethod.NONE,
        model_kind=ModelKind.LOGISTIC_REGRESSION,
    )
    when = data.samples[0].decision_time
    available_at = (
        None
        if clock == "missing"
        else when + timedelta(seconds={"before": -1, "at": 0, "after": 1}[clock])
    )
    record = bundle.records[0].revalidated(calibration=calibration, calibrated_before=available_at)
    bundle = bundle.revalidated(records=(record,))
    blocked = clock == "after" or (calibrated and clock == "missing")
    if blocked:
        forbid_shadow_execution(monkeypatch)
    rows = evaluate(spec, data, bundle, fee=fee)
    row = rows[0]
    if blocked:
        assert row["status"] == "blocked"
        assert row["intent"] is None
        assert row["risk"] is None
        assert row["reasons"] == [
            "point_in_time_prediction" if clock == "after" else "calibration_availability"
        ]
    else:
        assert row["status"] == "shadow_eligible"
        assert row["intent"] is not None
        assert row["risk"]["approved"]
    inputs = json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))
    assert reproduce(inputs) == rows


@pytest.mark.parametrize("data_kind", ["real", "synthetic"])
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"data_kind": None},
        {"data_kind": "real"},
        {"data_kind": "synthetic"},
        {"data_kind": "unknown"},
        {"data_kind": True},
    ],
)
def test_model_dataset_provenance_gates_intentions_and_survives_replay(
    data_kind: Literal["real", "synthetic"],
    metadata: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both paths are CONTROLLED software inputs, including the path labeled real.
    spec, data, bundle, fee = ready()
    data = data.revalidated(data_kind=data_kind)
    bundle = bundle.revalidated(
        model_metadata={
            **{k: v for k, v in bundle.model_metadata.items() if k != "data_kind"},
            **metadata,
        }
    )
    if metadata.get("data_kind") != data_kind:
        forbid_shadow_execution(monkeypatch)
    rows = evaluate(spec, data, bundle, fee=fee)
    row = rows[0]
    if metadata.get("data_kind") == data_kind:
        assert row["status"] == "shadow_eligible"
        assert row["intent"] is not None
        assert row["risk"]["approved"]
    else:
        assert row["status"] == "blocked"
        assert row["reasons"] == ["model_dataset_provenance"]
        assert row["intent"] is None
        assert row["risk"] is None
    inputs = json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))
    assert inputs["data"]["data_kind"] == data_kind
    assert ("data_kind" in inputs["bundle"]["model_metadata"]) == ("data_kind" in metadata)
    if "data_kind" in metadata:
        assert inputs["bundle"]["model_metadata"]["data_kind"] == metadata["data_kind"]
    assert reproduce(inputs) == rows


@pytest.mark.parametrize("case", ["matching", "missing_calibration", "mismatched_provenance"])
def test_corrected_prediction_gates_preserve_protected_exclusions_on_replay(case: str) -> None:
    spec, _, _, fee = ready()
    spec = spec.revalidated(
        calibration=CalibrationMethod.PLATT, model_kind=ModelKind.LOGISTIC_REGRESSION
    )
    data, provider, _, _ = nonweather()
    dataset_holdout, model_holdout, permitted = data.samples[50:53]
    data = data.revalidated(
        samples=(dataset_holdout, model_holdout, permitted),
        protected_events=frozenset({dataset_holdout.event_id}),
    )
    bundle = provider.bundle.revalidated(
        records=tuple(
            r.revalidated(
                calibration="platt",
                calibrated_before=None if case == "missing_calibration" else r.decision_time,
            )
            for r in provider.bundle.records
        ),
        model_metadata={
            "data_kind": "real" if case == "mismatched_provenance" else data.data_kind,
            "split": {"holdout": [model_holdout.event_id]},
        },
    )
    rows = evaluate(spec, data, bundle, fee=fee)
    assert [row["event_id"] for row in rows] == [permitted.event_id]
    if case == "matching":
        assert rows[0]["status"] == "shadow_eligible"
        assert rows[0]["risk"]["approved"]
    else:
        assert rows[0]["status"] == "blocked"
        assert rows[0]["intent"] is None
        assert rows[0]["risk"] is None
    inputs = json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))
    assert set(inputs["data"]["protected_events"]) == {
        dataset_holdout.event_id,
        model_holdout.event_id,
    }
    assert [s["event_id"] for s in inputs["data"]["samples"]] == [permitted.event_id]
    assert all(
        s["outcome"] is None and s["outcome_available_at"] is None
        for s in inputs["data"]["samples"]
    )
    assert [p["event_id"] for p in inputs["bundle"]["records"]] == [permitted.event_id]
    assert "split" not in inputs["bundle"]["model_metadata"]
    assert reproduce(inputs) == rows


def test_dataset_and_model_holdouts_exclude_samples_predictions_and_decisions_from_replay() -> None:
    spec, _, _, fee = ready()
    data, provider, _, _ = nonweather()
    dataset_holdout, model_holdout, permitted = data.samples[50:53]
    data = data.revalidated(
        samples=(dataset_holdout, model_holdout, permitted),
        protected_events=frozenset({dataset_holdout.event_id}),
    )
    # The model protects an event missing from the dataset's boundary, even though its
    # prediction is marked validation. Neither boundary may override the other.
    bundle = provider.bundle.revalidated(
        model_metadata={
            **provider.bundle.model_metadata,
            "split": {"holdout": [model_holdout.event_id]},
        }
    )
    rows = evaluate(spec, data, bundle, fee=fee)
    assert [r["event_id"] for r in rows] == [permitted.event_id]
    assert rows[0]["status"] == "shadow_eligible"
    inputs = json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))
    assert set(inputs["data"]["protected_events"]) == {
        dataset_holdout.event_id,
        model_holdout.event_id,
    }
    assert [s["event_id"] for s in inputs["data"]["samples"]] == [permitted.event_id]
    assert all(s["outcome"] is None for s in inputs["data"]["samples"])
    assert [p["event_id"] for p in inputs["bundle"]["records"]] == [permitted.event_id]
    assert "split" not in inputs["bundle"]["model_metadata"]
    assert reproduce(inputs) == rows


@pytest.mark.parametrize(
    "case",
    [
        "fees",
        "future_fee",
        "expired_fee",
        "features",
        "sources",
        "rules",
        "model",
        "future_fit",
        "future_calibration",
        "holdout",
        "feature_hash",
        "feature_version",
        "strategy_version",
        "ambiguous",
    ],
)
def test_fail_closed_information_gates(case: str) -> None:
    spec, data, bundle, fee = ready()
    sample, record = data.samples[0], bundle.records[0]
    supplied_fee: FeePolicy | None = fee
    if case == "fees":
        supplied_fee = None
    elif case == "future_fee":
        supplied_fee = fee.revalidated(available_at=sample.decision_time + timedelta(seconds=1))
    elif case == "expired_fee":
        supplied_fee = fee.revalidated(effective_to=sample.decision_time)
    elif case in {"features", "sources", "rules"}:
        changes: dict[str, dict[str, Any]] = {
            "features": {"eligible": False},
            "sources": {"sources": ()},
            "rules": {"rules_known": False},
        }
        data = data.revalidated(samples=(sample.revalidated(**changes[case]),))
    else:
        if case == "future_fit":
            record = record.revalidated(fitted_before=sample.decision_time + timedelta(seconds=1))
        if case == "future_calibration":
            record = record.revalidated(
                calibrated_before=sample.decision_time + timedelta(seconds=1)
            )
        if case == "feature_version":
            record = record.revalidated(feature_version="sha256:" + "e" * 64)
        if case == "strategy_version":
            data = data.revalidated(samples=(sample.revalidated(versions={"mention_count": "2"}),))
        if case == "holdout":
            record = record.revalidated(partition="holdout")
        if case == "feature_hash":
            record = record.revalidated(feature_hash="sha256:" + "d" * 64)
        bundle = bundle.revalidated(
            records=()
            if case == "model"
            else (record, record)
            if case == "ambiguous"
            else (record,)
        )
    row = evaluate(spec, data, bundle, fee=supplied_fee)[0]
    assert row["status"] == "blocked"
    assert row["reasons"]
    assert row["intent"] is None


@pytest.mark.parametrize(
    "case", ["stale", "per_event", "total", "spread", "trade_size", "fee_boundary"]
)
def test_existing_risk_boundaries_use_reserved_exposure(case: str) -> None:
    spec, data, bundle, fee = ready()
    sample = data.samples[0]
    assert sample.book is not None
    book = sample.book
    held: tuple[dict[str, Any], ...] = ()
    if case == "stale":
        sample = sample.revalidated(
            book=sample.book.revalidated(received_at=sample.decision_time - timedelta(seconds=61))
        )
    elif case == "spread":
        sample = sample.revalidated(
            book=book.revalidated(bids=(book.bids[0].revalidated(price=Decimal(".3")),))
        )
    elif case in {"trade_size", "fee_boundary"}:
        quantity = Decimal("50") if case == "fee_boundary" else Decimal("100")
        spec = spec.revalidated(
            position_sizing=spec.position_sizing.revalidated(
                contracts=quantity, max_contracts=quantity
            )
        )
        sample = sample.revalidated(
            book=book.revalidated(asks=(book.asks[0].revalidated(quantity=Decimal("100")),))
        )
    else:
        first = evaluate(spec, data, bundle, fee=fee)[0]
        intent = {
            **first["intent"],
            "quantity": "1000.00",
            "contract": {**first["intent"]["contract"], "market_ticker": "OTHER"},
        }
        held = (
            {"intent": intent, "event_id": sample.event_id if case == "per_event" else "OTHER"},
        )
    data = data.revalidated(samples=(sample,))
    row = evaluate(spec, data, bundle, fee=fee, reservations=held)[0]
    assert row["status"] == "risk_rejected"
    assert row["risk"] is not None
    assert row["reasons"]
    if case == "fee_boundary":
        assert row["risk"]["approved"]  # Exactly $25 before fees must still be refused.
        assert row["reasons"] == ["fee_inclusive_shadow_collateral"]


def test_store_freezes_spec_recovery_idempotency_controls_and_late_completion(
    tmp_path: Path,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)
    frozen = store.get(monitor_id)
    assert frozen is not None
    assert store.claim() is not None
    assert store.claim() is None
    running = store.get(monitor_id)
    assert running is not None
    cycle_id = running["cycles"][0]["id"]
    store.control(monitor_id, "pause")
    assert not store.finish(monitor_id, cycle_id, {"detail": "late"})
    assert store.claim() is None
    store.control(monitor_id, "resume")
    second = store.claim()
    assert second is not None
    restarted = TrackingStore(Jobs(tmp_path))
    restarted.recover()
    assert not restarted.finish(*second, {"detail": "late after restart"})
    third = restarted.claim()
    assert third is not None
    assert restarted.finish(*third, {"detail": "committed", "decisions": []})
    assert not restarted.finish(*third, {"detail": "duplicate"})
    done = restarted.get(monitor_id)
    assert done is not None
    assert done["cycles"][0]["result"] == {"detail": "committed", "decisions": []}
    assert done["spec_hash"] == frozen["spec_hash"]
    assert done["cycles"][1]["status"] == "interrupted"
    assert not done["submission_enabled"]
    assert done["fills"] == []
    assert done["performance"] is None
    assert restarted.claim() is None


def test_failure_backoff_auto_pause_and_explicit_resume(tmp_path: Path) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)
    for index in range(5):
        with store.jobs.connect() as db:
            db.execute("UPDATE monitors SET next_at='2000-01-01' WHERE id=?", (monitor_id,))
        claim = store.claim()
        assert claim is not None
        assert store.finish(*claim, {"detail": "controlled failure"}, failed=True)
        result = store.get(monitor_id)
        assert result is not None
        assert result["failures"] == index + 1
        assert store.claim() is None
    assert result is not None
    assert result["status"] == "paused"
    store.control(monitor_id, "resume")
    assert store.claim() is not None


@pytest.mark.parametrize(
    "change",
    [
        {"interval_seconds": 1},
        {"interval_seconds": True},
        {"candidate_id": "missing"},
        {"live": True},
    ],
)
def test_monitor_request_is_bounded(tmp_path: Path, change: dict[str, Any]) -> None:
    store = TrackingStore(Jobs(tmp_path))
    with pytest.raises(ValueError, match=r"poll interval|select a typed|provide job_id"):
        store.create({**saved(store), **change})


def test_synthetic_and_unsupported_candidates_cannot_start_and_active_cap_holds(
    tmp_path: Path,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    request = saved(store)
    with store.jobs.connect() as db:
        row = db.execute("SELECT result FROM jobs WHERE id=?", (request["job_id"],)).fetchone()
        result = json.loads(row[0])
        result["data_kind"] = "synthetic"
        db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(result), request["job_id"]))
    with pytest.raises(ValueError, match="synthetic"):
        store.create(request)
    for _ in range(4):
        monitor(store)
    with pytest.raises(ValueError, match="four active"):
        monitor(store)


def contract() -> dict[str, Any]:
    market = market_from_body(
        _market_body(), captured_at=WHEN - timedelta(days=5), series="KXHIGHPHIL"
    )
    return {
        "ticker": market.ticker,
        "market": {
            "ticker": market.ticker,
            "market": market.model_dump(mode="json", exclude_computed_fields=True),
        },
        "last_attempt": "",
        "outcome": None,
    }


@pytest.mark.parametrize(
    "case", ["final", "provisional", "changed", "future", "wrong_payout", "outage", "archive"]
)
def test_official_outcome_receipts_never_rewrite_clocks_or_terms(tmp_path: Path, case: str) -> None:
    requests: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        assert request.method == "GET"
        assert not any("authorization" in h or "kalshi-access" in h for h in request.headers)
        if case == "outage":
            raise httpx.ConnectError("CONTROLLED outage")
        if case == "archive" and "/historical/" not in request.url.path:
            return httpx.Response(404, json={})
        body = _market_body()
        body.update(
            status="finalized",
            result="yes",
            settlement_value_dollars="1.0000",
            settlement_ts="2026-10-03T06:00:00Z",
        )
        if case == "provisional":
            body["is_provisional"] = True
        if case == "changed":
            body["floor_strike"] = 88
        if case == "future":
            body["settlement_ts"] = "2026-10-26T06:00:00Z"
        if case == "wrong_payout":
            body["settlement_value_dollars"] = "0.0000"
        return httpx.Response(200, json={"market": body})

    result = asyncio.run(
        outcomes(
            tmp_path / "outcomes",
            [contract()],
            transport=httpx.MockTransport(wire),
            clock=SimulatedClock(WHEN),
        )
    )
    assert len(result["outcomes"]) == (1 if case in {"final", "archive"} else 0)
    if result["outcomes"]:
        assert result["outcomes"][0]["available_at"] == WHEN.isoformat()
    assert len(requests) == (2 if case == "archive" else 1)
    for receipt in result["outcome_receipts"]:
        assert (tmp_path / receipt["raw_ref"]).is_file()


def test_controlled_continuous_capture_records_real_adapter_refusals_and_versions(
    tmp_path: Path,
) -> None:
    store = TrackingStore(Jobs(tmp_path / "workspace"))
    monitor_id = monitor(store, family="bitcoin")
    snapshot = store.get(monitor_id, export=True)
    assert snapshot is not None
    root = tmp_path / "cycle"
    root.mkdir()
    result = asyncio.run(
        collect(
            snapshot,
            REPO,
            root,
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(spot),
            clock=SimulatedClock(WHEN),
        )
    )
    assert len(result["decisions"]) == len(result["contracts"]) == len(result["quotes"]) == 2
    assert result["capture"]["receipts"]
    assert result["model_refusals"]
    assert all(r["status"] == "blocked" and r["intent"] is None for r in result["decisions"])
    assert all(r["prediction"] is None for r in result["decisions"])
    claim = store.claim()
    assert claim is not None
    assert store.finish(*claim, result)
    reopened = TrackingStore(Jobs(tmp_path / "workspace")).get(monitor_id, export=True)
    assert reopened is not None
    assert len(reopened["contracts"]) == 2
    assert reservations(reopened) == ()


@pytest.mark.parametrize("condition", ["timeout", "shutdown", "pause", "crash"])
def test_shadow_worker_termination_never_publishes_late_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)
    claim = store.claim()
    assert claim is not None
    root = store.jobs.root / "shadow" / monitor_id / claim[1]
    root.mkdir(parents=True)
    (root / "partial.json").write_text('{"evidence":"CONTROLLED worker termination"}')
    process = ControlledProcess(1 if condition == "crash" else None)
    launches: list[dict[str, Any]] = []

    def launch(_command: list[str], **kwargs: Any) -> ControlledProcess:
        launches.append(kwargs)
        return process

    monkeypatch.setattr("entropytrade.tracking.runner.subprocess.Popen", launch)
    runner = ShadowRunner(store, REPO, timeout=0)
    if condition == "shutdown":
        runner.stop.set()
    if condition == "pause":
        store.control(monitor_id, "pause")
    runner.execute(*claim)
    assert process.killed == (condition != "crash")
    snapshot = store.get(monitor_id)
    assert snapshot is not None
    assert snapshot["cycles"][0]["status"] == (
        "interrupted" if condition in {"pause", "shutdown"} else "failed"
    )
    assert not any("KEY" in k or "TOKEN" in k or k == "HOME" for k in launches[0]["env"])
    assert "shell" not in launches[0]
    if condition in {"timeout", "crash"}:
        assert snapshot["cycles"][0]["result"]["failure"]
        assert snapshot["cycles"][0]["result"]["artifacts"][0]["path"] == "partial.json"


def test_reservations_include_old_cycles_and_release_only_after_received_outcome() -> None:
    spec, data, bundle, fee = ready()
    rows = evaluate(spec, data, bundle, fee=fee)
    snapshot = {"contracts": [], "cycles": [{"status": "completed", "result": {"decisions": rows}}]}
    assert reservations(snapshot) == tuple(rows)
    snapshot["contracts"] = [{"ticker": rows[0]["ticker"], "outcome": {"result": "yes"}}]
    assert reservations(snapshot) == ()


def test_monitor_http_controls_exports_and_security_share_workbench_boundary(
    tmp_path: Path,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    request = saved(store)
    server = cast(
        "WorkbenchServer",
        SimpleNamespace(
            jobs=store.jobs, tracking=store, repo=REPO, server_port=43128, token=str(uuid4())
        ),
    )
    token = {"X-EntropyTrade-CSRF": server.token}
    assert exchange(server, "/api/monitors", method="POST", body=request)[0] == 403
    assert exchange(server, "/api/monitors", headers={"Host": "attacker.invalid"})[0] == 403
    status, _, body = exchange(server, "/api/monitors", method="POST", body=request, headers=token)
    assert status == 202
    monitor_id = json.loads(body)["id"]
    assert json.loads(exchange(server, "/api/monitors")[2])[0]["id"] == monitor_id
    for action in ("pause", "resume", "pause"):
        assert (
            exchange(
                server,
                f"/api/monitors/{monitor_id}/{action}",
                method="POST",
                body={},
                headers=token,
            )[0]
            == 200
        )
    download = exchange(server, f"/api/monitors/{monitor_id}/export")[2]
    assert download == exchange(server, f"/api/monitors/{monitor_id}/export")[2]
    assert json.loads(download)["status"] == "paused"
    assert not json.loads(download)["submission_enabled"]
    for path in (f"/api/monitors/{monitor_id}/orders", "/api/monitors/../../AGENTS.md"):
        assert exchange(server, path)[0] == 404
    assert (
        exchange(
            server, "/api/monitors", method="POST", body={**request, "live": True}, headers=token
        )[0]
        == 400
    )
