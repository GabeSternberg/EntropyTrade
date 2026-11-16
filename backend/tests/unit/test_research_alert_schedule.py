"""CONTROLLED daily research schedules use committed health, never moving poll clocks."""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.research.paper import ResearchPaperService
from entropytrade.tracking.store import TrackingStore
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_support import paper_fixture


@pytest.fixture(scope="module")
def research_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, dict[str, Any]]:
    case = paper_fixture(tmp_path_factory.mktemp("research-alert-source"))
    return case.jobs.root, case.job_id, case.request


def open_case(
    template: tuple[Path, str, dict[str, Any]], destination: Path, clock: SimulatedClock
) -> tuple[TrackingStore, str]:
    source, job_id, request = template
    shutil.copytree(source, destination)
    store = TrackingStore(Jobs(destination))
    service = ResearchPaperService(destination, store, clock=clock, expected_data_kind="synthetic")
    return store, service.create(job_id, request)["id"]


def active_alerts(store: TrackingStore) -> dict[str, dict[str, Any]]:
    return {a["kind"]: a for a in store.alerts() if a["resolved_at"] is None}


def collection(
    store: TrackingStore, mid: str, clock: SimulatedClock, *, feature_failure: bool = False
) -> str:
    claim = store.claim()
    assert claim is not None
    assert claim[0] == mid
    # A successful or failed source collection need not produce a paper intention.
    result = {
        "detail": "CONTROLLED scheduler health observation",
        "submission_enabled": False,
        "capture": {"universe_complete": True, "failures": []},
        "research_features": {
            "failures": [{"source": "PFM", "reason": "CONTROLLED source outage"}]
            if feature_failure
            else []
        },
        "artifacts": [],
    }
    root = store.jobs.root / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    (root / "result.json").write_text(json.dumps(result))
    assert store.finish(mid, claim[1], result)
    assert store.get(mid)["cycles"][0]["finished_at"] == clock.now().isoformat()  # type: ignore[index]
    return claim[1]


def test_initial_research_wait_is_fresh_until_first_trained_point_and_worker_grace(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimulatedClock(MODEL_NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "initial", clock)
    original = store.get(mid)
    assert original is not None
    first = datetime.fromisoformat(original["next_at"])
    clock.advance(timedelta(minutes=20))  # prior 300s-interval implementation falsely alerted here
    assert "stale_collection" not in active_alerts(store)
    clock.advance_to(first + timedelta(seconds=239))
    assert "stale_collection" not in active_alerts(store)
    clock.advance(timedelta(seconds=1))
    evidence = active_alerts(store)["stale_collection"]["evidence"]
    assert evidence["expected_decision_at"] == first.isoformat()
    assert evidence["grace_seconds"] == 240
    assert evidence["last_healthy_collection_at"] is None


def test_healthy_daily_cycle_remains_fresh_until_next_trained_point(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimulatedClock(MODEL_NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "healthy", clock)
    first = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    clock.advance_to(first + timedelta(seconds=30))
    healthy_id = collection(store, mid, clock)
    next_point = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    clock.advance(timedelta(minutes=20))
    assert "stale_collection" not in active_alerts(store)
    clock.advance_to(next_point + timedelta(seconds=240))
    evidence = active_alerts(store)["stale_collection"]["evidence"]
    assert evidence["expected_decision_at"] == next_point.isoformat()
    assert evidence["last_healthy_cycle_id"] == healthy_id


def test_restart_advancing_poll_clock_cannot_hide_a_missed_trained_point(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimulatedClock(MODEL_NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "missed", clock)
    first = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    clock.advance_to(first + timedelta(seconds=241))
    store.recover()
    assert datetime.fromisoformat(store.get(mid)["next_at"]) > clock.now()  # type: ignore[index]
    evidence = active_alerts(store)["stale_collection"]["evidence"]
    assert evidence["expected_decision_at"] == first.isoformat()


def test_feature_source_failures_do_not_advance_last_healthy_baseline(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimulatedClock(MODEL_NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "source-failure", clock)
    first = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    clock.advance_to(first + timedelta(seconds=30))
    healthy_id = collection(store, mid, clock)
    next_point = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    clock.advance_to(next_point + timedelta(seconds=30))
    collection(store, mid, clock, feature_failure=True)
    assert datetime.fromisoformat(store.get(mid)["next_at"]) > clock.now()  # type: ignore[index]
    clock.advance_to(next_point + timedelta(seconds=241))
    evidence = active_alerts(store)["stale_collection"]["evidence"]
    assert evidence["last_healthy_cycle_id"] == healthy_id
    assert evidence["expected_decision_at"] == next_point.isoformat()


def test_invalid_research_binding_opens_explicit_incident_without_interval_fallback(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimulatedClock(MODEL_NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "invalid", clock)
    with store.jobs.connect() as db:
        db.execute("UPDATE monitors SET model_binding='{}' WHERE id=?", (mid,))
    evidence = active_alerts(store)["stale_collection"]["evidence"]
    assert evidence["schedule_status"] == "invalid"
    assert "no interval fallback" in evidence["reason"]
    assert "threshold_seconds" not in evidence


def test_daily_schedule_preserves_local_horizon_across_dst_transition(
    research_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fall 2027 is after the frozen model's availability and within controlled fee scope.
    clock = SimulatedClock(datetime(2027, 11, 6, 20, tzinfo=UTC))
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    store, mid = open_case(research_template, tmp_path / "dst", clock)
    first = datetime.fromisoformat(store.get(mid)["next_at"])  # type: ignore[index]
    assert first == datetime(2027, 11, 6, 22, tzinfo=UTC)
    clock.advance_to(first + timedelta(seconds=30))
    collection(store, mid, clock)
    next_point = datetime(2027, 11, 7, 23, tzinfo=UTC)
    clock.advance_to(next_point + timedelta(seconds=239))
    assert "stale_collection" not in active_alerts(store)
    clock.advance(timedelta(seconds=1))
    assert (
        active_alerts(store)["stale_collection"]["evidence"]["expected_decision_at"]
        == next_point.isoformat()
    )
