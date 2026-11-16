"""CONTROLLED settlement drains use real collection/accounting, never new trading inputs."""

import copy
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking import alerts, history, worker
from entropytrade.tracking.accounting import reproduce
from entropytrade.tracking.prospective import report
from entropytrade.tracking.readiness_store import ReadinessStore
from entropytrade.tracking.reconciliation import verify_reconciliation
from entropytrade.tracking.replay import verify
from entropytrade.tracking.store import TrackingStore
from entropytrade.weather.history import build_snapshot
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
    outcome_transport_for_monitor,
)
from tests.research_paper_support import paper_fixture
from tests.unit.test_tracking import REPO, monitor


@pytest.fixture(scope="module")
def drained(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    fixture = paper_fixture(tmp_path_factory.mktemp("paper-reconciliation") / "workspace")
    clock = SimulatedClock(MODEL_NOW + timedelta(minutes=1))
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        created = fixture.service.create(fixture.job_id, fixture.request)
        first = commit_controlled_cycle(
            fixture, MODEL_NOW.replace(hour=23, minute=0, second=5), clock=clock
        )
        original = fixture.tracking.get(created["id"], export=True)
        assert original is not None
        assert original["paper_summary"]["fill_count"] > 0
        before = original["paper_account"]
        first_cycle = original["cycles"][0]
        first_root = fixture.jobs.root / "shadow" / created["id"] / first_cycle["id"]
        original_bytes = {
            p.relative_to(first_root).as_posix(): p.read_bytes()
            for p in first_root.rglob("*")
            if p.is_file()
        }
        original_anchor = history.anchor(fixture.jobs)
        safety = ReadinessStore(fixture.jobs, clock=clock)
        safety.halt("CONTROLLED halt with existing simulated exposure")
        closed = max(
            datetime.fromisoformat(c["market"]["market"]["close_time"])
            for c in original["contracts"]
        )
        clock.advance_to(closed + timedelta(seconds=5))
        claim = fixture.tracking.claim()
        assert claim is not None
        current = fixture.tracking.get(created["id"], export=True)
        assert current is not None
        assert current["cycles"][0]["cycle_mode"] == "reconcile_only"
        actual_collect = worker.collect

        async def collect(
            snapshot: dict[str, Any],
            repo: Path,
            root: Path,
            *,
            fee_versions: tuple[FeeVersion, ...] = (),
        ) -> dict[str, Any]:
            assert not fee_versions
            return await actual_collect(
                snapshot,
                repo,
                root,
                clock=clock,
                outcome_transport=outcome_transport_for_monitor(snapshot, clock),
            )

        def forbidden(*_args: Any, **_kwargs: Any) -> Any:
            pytest.fail("settlement drain reached a forecast, fee, model or order-data path")

        with (
            patch.object(worker, "collect", side_effect=collect),
            patch.object(worker, "capture_public", side_effect=forbidden),
            patch.object(worker, "capture_execution", side_effect=forbidden),
            patch.object(worker, "acquire_research_features", side_effect=forbidden),
            patch.object(worker, "score", side_effect=forbidden),
            patch("entropytrade.tracking.worker.FeeEvidenceStore.snapshot", side_effect=forbidden),
            patch(
                "entropytrade.tracking.store.validate_research_source",
                side_effect=ValueError("CONTROLLED current model/risk policy drift"),
            ),
            patch("entropytrade.ml.models.WeatherModel.load", side_effect=forbidden),
        ):
            worker.execute(fixture.tracking, REPO, *claim)
        after = fixture.tracking.get(created["id"], export=True)
        assert after is not None
        cycle = after["cycles"][0]
        root = fixture.jobs.root / "shadow" / created["id"] / claim[1]
        return {
            "fixture": fixture,
            "clock": clock,
            "before": before,
            "first": first,
            "first_root": first_root,
            "first_bytes": original_bytes,
            "first_anchor": original_anchor,
            "monitor": after,
            "cycle": cycle,
            "root": root,
        }


def test_halted_existing_account_settles_without_new_models_books_orders_or_fills(
    drained: dict[str, Any],
) -> None:
    after, before, cycle = drained["monitor"], drained["before"], drained["cycle"]
    assert cycle["status"] == "completed", cycle
    result = cycle["result"]
    assert after["status"] == "paused"
    assert result["cycle_mode"] == "reconcile_only"
    assert result["control_snapshot"]["halted"]
    assert result["data_kind"] == before["data_kind"] == "synthetic"
    assert not result["decisions"]
    assert not result["contracts"]
    assert result["capture"] is result["execution"] is result["model_binding"] is None
    assert not result["paper"]["executions"]
    assert len(result["paper"]["settlements"]) == 1
    ledger = after["paper_account"]["ledger"]
    for key in ("starting_cash", "fills", "orders", "collateral", "fees_paid"):
        assert ledger[key] == before["ledger"][key]
    assert not ledger["positions"]
    assert datetime.fromisoformat(
        ledger["settlements"][-1]["settled_at"]
    ) == datetime.fromisoformat(result["outcomes"][0]["available_at"])
    assert not (drained["root"] / "public").exists()
    assert verify(drained["root"])["decision_count"] == 0
    assert history.verified_inputs(drained["root"])["data"]["samples"] == []
    assert drained["first_bytes"] == {
        p.relative_to(drained["first_root"]).as_posix(): p.read_bytes()
        for p in drained["first_root"].rglob("*")
        if p.is_file()
    }


def test_drain_is_outcome_only_history_and_matures_original_forecast(
    drained: dict[str, Any], tmp_path: Path
) -> None:
    fixture, after, clock = drained["fixture"], drained["monitor"], drained["clock"]
    entries = history.entries(fixture.jobs)
    assert sum(bool(e.get("outcome_only")) for e in entries) == 1
    captures, outcomes, _ = history.selected_inputs(fixture.jobs, None, None)
    assert len(captures) == 1
    assert len(outcomes) == 2
    assert history.anchor(fixture.jobs) == drained["first_anchor"]
    with controlled_forward_environment(clock):
        value = report(fixture.jobs, after["id"], as_of=clock.now())
    assert not value["cycle_failures"]
    assert value["counts"]["contracts"] == 1
    assert value["counts"]["poll_observations"] == 1
    assert value["observations"][0]["status"] == "matched"
    assert value["observations"][0]["cycle_id"] != drained["cycle"]["id"]
    assert (
        value["observations"][0]["outcome"]["available_at"]
        == drained["cycle"]["result"]["outcomes"][0]["available_at"]
    )
    assert not value["historical_validation"]
    assert value["performance"] is None
    # The real history consumer must not publish this declared synthetic paper fixture
    # as an authentic retained-weather snapshot. Unlike the projection above, it runs
    # without the test-only classification decoder and retains its source-kind refusal.
    with pytest.raises(ValueError, match="shadow source version mismatch"):
        build_snapshot(
            tmp_path / "weather-history",
            captures,
            outcome_roots=outcomes,
            frozen_anchor=drained["first_anchor"],
        )
    assert not (tmp_path / "weather-history").exists()


def test_historical_reconciliation_uses_frozen_controls_not_current_halt_file(
    drained: dict[str, Any],
) -> None:
    fixture = drained["fixture"]
    sentinel = fixture.jobs.root / "HALT"
    sentinel.write_text("CONTROLLED newer operator state")
    try:
        inputs = verify_reconciliation(drained["root"], drained["cycle"]["result"])
        assert inputs["data"]["samples"] == []
    finally:
        sentinel.unlink()


def test_disagreeing_mode_and_schema_cannot_fall_back_to_ordinary_replay(
    drained: dict[str, Any], tmp_path: Path
) -> None:
    root = tmp_path / drained["root"].name
    shutil.copytree(drained["root"], root)
    result = copy.deepcopy(drained["cycle"]["result"])
    result["cycle_mode"] = "paper"
    (root / "result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="reconciliation"):
        verify(root)


@pytest.mark.parametrize(
    "fault", ["samples", "predictions", "bankroll_reset", "orders", "epoch", "kind"]
)
def test_settlement_mode_tag_cannot_authorize_new_economic_inputs(
    drained: dict[str, Any], tmp_path: Path, fault: str
) -> None:
    root = tmp_path / drained["root"].name
    shutil.copytree(drained["root"], root)
    result = copy.deepcopy(drained["cycle"]["result"])
    if fault == "samples":
        result["paper_inputs"]["decision_inputs"]["data"]["samples"] = drained["first"][
            "paper_inputs"
        ]["decision_inputs"]["data"]["samples"]
    elif fault == "predictions":
        result["paper_inputs"]["decision_inputs"]["bundle"] = drained["first"]["paper_inputs"][
            "decision_inputs"
        ]["bundle"]
    elif fault == "bankroll_reset":
        result["paper_inputs"]["before"] = None
    elif fault == "orders":
        result["paper"]["state"]["ledger"]["orders"].append(
            copy.deepcopy(result["paper"]["state"]["ledger"]["orders"][0])
        )
    elif fault == "epoch":
        result["control_epoch"] += 1
    else:
        result["data_kind"] = "real"
    with pytest.raises(ValueError, match=r"reconciliation|settlement"):
        verify_reconciliation(root, result)


def test_halt_then_release_rejects_inflight_paper_outbox_without_reactivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    safety = ReadinessStore(store.jobs)
    claim = store.claim()
    assert claim is not None

    async def in_flight(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        halted = safety.halt("CONTROLLED halt during a worker")
        safety.release(
            halted["epoch"],
            actor={"kind": "human", "actor_id": "CONTROLLED_OWNER"},
            reason="CONTROLLED release without strategy resume",
        )
        return {
            "detail": "CONTROLLED old computation",
            "capture": {"failures": []},
            "outcome_failures": [],
        }

    monkeypatch.setattr(worker, "collect", in_flight)
    worker.execute(store, REPO, *claim)
    after = store.get(mid, export=True)
    assert after is not None
    assert after["status"] == "paused"
    assert after["cycles"][0]["status"] == "interrupted"
    assert after["paper_account"] is None
    root = store.jobs.root / "shadow" / mid / claim[1]
    assert not (root / "result.json").exists()
    retained = json.loads((root / "uncommitted-result.json").read_text())
    assert retained["control_epoch"] == 0
    assert not store.finish(*claim, retained)
    assert store.claim() is None
    assert scientific_hash(retained) != scientific_hash(after["cycles"][0].get("result"))


def test_cancelled_pre_e_account_drains_even_when_current_model_metadata_is_unreadable(
    tmp_path: Path,
) -> None:
    fixture = paper_fixture(tmp_path / "workspace")
    clock = SimulatedClock(MODEL_NOW + timedelta(minutes=1))
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        created = fixture.service.create(fixture.job_id, fixture.request)
        first = commit_controlled_cycle(
            fixture, MODEL_NOW.replace(hour=23, minute=0, second=5), clock=clock
        )
        current = fixture.tracking.get(created["id"], export=True)
        assert current is not None
        with fixture.jobs.connect() as db:
            assert (
                db.execute("SELECT 1 FROM sqlite_master WHERE name='workspace_controls'").fetchone()
                is None
            )
        fixture.tracking.control(created["id"], "cancel")
        # A damaged current scoring binding cannot prevent settlement of an old,
        # already committed position. No decoder is allowed to upgrade this value.
        with fixture.jobs.connect() as db:
            db.execute(
                "UPDATE monitors SET model_binding='CONTROLLED unreadable model' WHERE id=?",
                (created["id"],),
            )
        close = max(datetime.fromisoformat(c["market"]["close_time"]) for c in first["contracts"])
        clock.advance_to(close + timedelta(seconds=5))
        claim = fixture.tracking.claim()
        assert claim is not None
        actual_collect = worker.collect

        async def collect(
            snapshot: dict[str, Any],
            repo: Path,
            root: Path,
            *,
            fee_versions: tuple[FeeVersion, ...] = (),
        ) -> dict[str, Any]:
            assert snapshot["status"] == "cancelled"
            assert snapshot["model_binding"] is None
            return await actual_collect(
                snapshot,
                repo,
                root,
                clock=clock,
                outcome_transport=outcome_transport_for_monitor(snapshot, clock),
            )

        def forbidden(*_args: Any, **_kwargs: Any) -> Any:
            pytest.fail("cancelled drain attempted new market/model acquisition")

        with (
            patch.object(worker, "collect", side_effect=collect),
            patch.object(worker, "capture_public", side_effect=forbidden),
            patch.object(worker, "capture_execution", side_effect=forbidden),
            patch.object(worker, "score", side_effect=forbidden),
            patch("entropytrade.tracking.worker.FeeEvidenceStore.snapshot", side_effect=forbidden),
        ):
            worker.execute(fixture.tracking, REPO, *claim)
        with fixture.jobs.connect() as db:
            cycle = db.execute(
                "SELECT status,result FROM shadow_cycles WHERE id=?", (claim[1],)
            ).fetchone()
            account = json.loads(
                db.execute(
                    "SELECT state FROM shadow_accounts WHERE monitor_id=?", (created["id"],)
                ).fetchone()[0]
            )
            status = db.execute(
                "SELECT status FROM monitors WHERE id=?", (created["id"],)
            ).fetchone()[0]
        assert cycle["status"] == "completed"
        result = json.loads(cycle["result"])
        assert result["cycle_mode"] == "reconcile_only"
        assert not result["control_snapshot"]["halted"]
        assert not result["paper"]["executions"]
        assert not account["ledger"]["positions"]
        assert len(account["ledger"]["fills"]) == len(first["paper"]["state"]["ledger"]["fills"])
        assert status == "cancelled"


def test_due_settlement_preserves_trained_paper_capacity_until_halt(tmp_path: Path) -> None:
    fixture = paper_fixture(tmp_path / "workspace")
    clock = SimulatedClock(MODEL_NOW + timedelta(minutes=1))
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        created = fixture.service.create(fixture.job_id, fixture.request)
        first = commit_controlled_cycle(
            fixture, MODEL_NOW.replace(hour=23, minute=0, second=5), clock=clock
        )
        before = first["paper"]["state"]
        assert before["ledger"]["positions"]
        fixture.tracking.control(created["id"], "pause")
        # Resume is an explicit operator action at a later trained date. Its next
        # decision and the older unsettled holding are both actual persisted facts.
        due = MODEL_NOW.replace(hour=23, minute=0, second=0) + timedelta(days=3)
        clock.advance_to(due - timedelta(minutes=2))
        fixture.tracking.control(created["id"], "resume")
        fixture.tracking = TrackingStore(Jobs(fixture.jobs.root))
        current = fixture.tracking.get(created["id"], export=True)
        assert current is not None
        assert datetime.fromisoformat(current["next_at"]) == due
        assert current["paper_account"] == before
        assert current["contracts"][0]["outcome"] is None
        expected, _ = alerts.settlement_expected(current["contracts"][0]["market"]["market"])
        assert expected < clock.now()
        assert fixture.tracking.claim() is None
        assert len(fixture.tracking.get(created["id"], export=True)["cycles"]) == 1  # type: ignore[index]

        clock.advance_to(due)
        paper_claim = fixture.tracking.claim()
        assert paper_claim is not None
        paper = fixture.tracking.get_for_cycle(*paper_claim)
        assert paper is not None
        assert paper["cycles"][0]["cycle_mode"] == "paper"
        assert paper["cycles"][0]["started_at"] == due.isoformat()
        safety = ReadinessStore(fixture.jobs, clock=clock)
        safety.halt("CONTROLLED halt at a trained point with an old unsettled holding")
        drain_claim = fixture.tracking.claim()
        assert drain_claim is not None
        assert drain_claim[1] != paper_claim[1]
        actual_collect = worker.collect

        async def collect(
            snapshot: dict[str, Any],
            repo: Path,
            root: Path,
            *,
            fee_versions: tuple[FeeVersion, ...] = (),
        ) -> dict[str, Any]:
            assert snapshot["cycles"][0]["cycle_mode"] == "reconcile_only"
            assert snapshot["status"] == "paused"
            assert not fee_versions
            return await actual_collect(
                snapshot,
                repo,
                root,
                clock=clock,
                outcome_transport=outcome_transport_for_monitor(snapshot, clock),
            )

        def forbidden(*_args: Any, **_kwargs: Any) -> Any:
            pytest.fail("capacity-reserved halted drain acquired new trading evidence")

        with (
            patch.object(worker, "collect", side_effect=collect),
            patch.object(worker, "capture_public", side_effect=forbidden),
            patch.object(worker, "capture_execution", side_effect=forbidden),
            patch.object(worker, "acquire_research_features", side_effect=forbidden),
            patch.object(worker, "score", side_effect=forbidden),
            patch("entropytrade.tracking.worker.FeeEvidenceStore.snapshot", side_effect=forbidden),
            patch("entropytrade.ml.models.WeatherModel.load", side_effect=forbidden),
        ):
            worker.execute(fixture.tracking, REPO, *drain_claim)
        after = fixture.tracking.get(created["id"], export=True)
        assert after is not None
        assert after["status"] == "paused"
        drain, interrupted, original = after["cycles"]
        assert drain["status"] == "completed"
        assert interrupted["id"] == paper_claim[1]
        assert interrupted["status"] == "interrupted"
        assert original["result"] == json.loads(json.dumps(first))
        result = drain["result"]
        assert not result["decisions"]
        assert not result["paper"]["executions"]
        assert result["control_snapshot"]["halted"]
        assert not after["paper_account"]["ledger"]["positions"]
        assert after["paper_account"]["ledger"]["fills"] == before["ledger"]["fills"]
        outcome = result["outcomes"][0]
        assert datetime.fromisoformat(outcome["available_at"]) > due
        assert outcome["available_at"] == outcome["receipt"]["received_at"]
        assert datetime.fromisoformat(
            after["paper_account"]["ledger"]["settlements"][0]["settled_at"]
        ) == datetime.fromisoformat(outcome["available_at"])
        root = fixture.jobs.root / "shadow" / created["id"] / drain_claim[1]
        assert verify(root)["decision_count"] == 0
        with controlled_forward_environment(clock):
            prospective = report(fixture.jobs, created["id"], as_of=clock.now())
        observation = prospective["observations"][0]
        assert prospective["counts"]["poll_observations"] == 1
        assert observation["cycle_id"] == original["id"]
        assert observation["outcome"]["available_at"] == outcome["available_at"]


def _rewrite_outcome_evidence(root: Path, result: dict[str, Any]) -> None:
    """Keep all declared hashes coherent so negative cases exercise semantic proof."""
    summary_path = root / "outcomes/summary.json"
    summary = json.loads(summary_path.read_text())
    receipt = summary["outcome_receipts"][0]
    receipt["sha256"] = file_hash(root / receipt["raw_ref"])
    for value in (summary["outcomes"][0], result["paper_inputs"]["outcomes"][0]):
        value["receipt"] = copy.deepcopy(receipt)
        value["available_at"] = receipt["received_at"]
    summary_path.write_text(json.dumps(summary))
    result.update(summary)
    result["paper_inputs"]["decision_inputs"] = json.loads(
        (root / "decision-inputs.json").read_text()
    )
    # Accounting remains the actual deterministic accountant; no fabricated metrics.
    result["paper"] = reproduce(result["paper_inputs"])
    (root / "paper-inputs.json").write_text(json.dumps(result["paper_inputs"]))
    for artifact in result["artifacts"]:
        path = root / artifact["path"]
        artifact.update(sha256=file_hash(path), bytes=path.stat().st_size)


def test_zero_payout_official_no_settles_the_same_existing_position(
    drained: dict[str, Any], tmp_path: Path
) -> None:
    root = tmp_path / drained["root"].name
    shutil.copytree(drained["root"], root)
    result = copy.deepcopy(drained["cycle"]["result"])
    summary_path = root / "outcomes/summary.json"
    summary = json.loads(summary_path.read_text())
    receipt = summary["outcome_receipts"][0]
    raw_path = root / receipt["raw_ref"]
    body = json.loads(raw_path.read_text())
    body["market"].update(result="no", settlement_value_dollars="0.0000")
    raw_path.write_text(json.dumps(body))
    summary["outcomes"][0]["result"] = "no"
    result["paper_inputs"]["outcomes"][0]["result"] = "no"
    summary_path.write_text(json.dumps(summary))
    _rewrite_outcome_evidence(root, result)
    verify_reconciliation(root, result)
    assert result["paper"]["settlements"][0]["settlement"]["result"] == "no"
    assert result["paper"]["summary"]["cash"] == result["paper_inputs"]["before"]["ledger"]["cash"]
    assert not result["paper"]["state"]["ledger"]["positions"]


@pytest.mark.parametrize(
    "fault", ["terms", "provisional", "wrong_value", "wrong_path", "old_receipt", "future_receipt"]
)
def test_fresh_official_binary_receipt_is_required_even_with_consistent_hashes(
    drained: dict[str, Any], tmp_path: Path, fault: str
) -> None:
    root = tmp_path / drained["root"].name
    shutil.copytree(drained["root"], root)
    result = copy.deepcopy(drained["cycle"]["result"])
    summary_path = root / "outcomes/summary.json"
    summary = json.loads(summary_path.read_text())
    receipt = summary["outcome_receipts"][0]
    path = root / receipt["raw_ref"]
    body = json.loads(path.read_text())
    if fault == "terms":
        body["market"]["rules_primary"] += " CONTROLLED changed payout terms"
    elif fault == "provisional":
        body["market"]["is_provisional"] = True
    elif fault == "wrong_value":
        body["market"]["settlement_value_dollars"] = "0.5000"
    elif fault == "wrong_path":
        receipt["path"] = "/trade-api/v2/markets/UNRELATED"
    elif fault == "old_receipt":
        receipt["received_at"] = result["cycle_started_at"]
        receipt["received_at"] = (
            datetime.fromisoformat(receipt["received_at"]) - timedelta(seconds=1)
        ).isoformat()
    else:
        receipt["received_at"] = (
            datetime.fromisoformat(result["paper_inputs"]["as_of"]) + timedelta(seconds=1)
        ).isoformat()
        # Move only the raw receipt. A forged future receipt must not extend the
        # frozen accountant's cycle cutoff to make itself admissible.
    path.write_text(json.dumps(body))
    summary_path.write_text(json.dumps(summary))
    if fault == "future_receipt":
        # The accountant independently rejects the future availability before raw proof.
        result["outcome_receipts"] = summary["outcome_receipts"]
        result["outcomes"][0]["receipt"] = copy.deepcopy(receipt)
        result["outcomes"][0]["available_at"] = receipt["received_at"]
        result["paper_inputs"]["outcomes"] = copy.deepcopy(result["outcomes"])
    else:
        _rewrite_outcome_evidence(root, result)
    with pytest.raises(ValueError, match=r"reconciliation|paper official"):
        verify_reconciliation(root, result)
