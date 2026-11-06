"""Controlled operator failures/restarts; no synthetic event is empirical market evidence."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot, validate_database
from entropytrade.domain.time import SimulatedClock
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from tests.integration.shadow_history_fixture import seed_authentic
from tests.unit.test_public_families import WHEN
from tests.unit.test_tracking import REPO, monitor
from tests.unit.test_workbench_http import ControlledProcess, exchange

if TYPE_CHECKING:
    from entropytrade.api.server import WorkbenchServer


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> SimulatedClock:
    value = SimulatedClock(WHEN)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: value.now().isoformat())
    return value


def due(store: TrackingStore, mid: str, clock: SimulatedClock) -> tuple[str, str]:
    value = store.get(mid)
    assert value
    from datetime import datetime

    clock.advance_to(max(clock.now(), datetime.fromisoformat(value["next_at"])))
    claim = store.claim()
    assert claim
    assert claim[0] == mid
    return claim


def fail(store: TrackingStore, mid: str, clock: SimulatedClock) -> None:
    ShadowRunner(store, REPO).fail(*due(store, mid, clock), "CONTROLLED worker timeout")


def complete(store: TrackingStore, mid: str, clock: SimulatedClock, **extra: Any) -> None:
    claim = due(store, mid, clock)
    result = {
        "detail": "CONTROLLED healthy collection; model/fee eligibility remains independent",
        "submission_enabled": False,
        "capture": {"universe_complete": True, "failures": []},
        "decisions": [],
        "artifacts": [],
        **extra,
    }
    root = store.jobs.root / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    (root / "result.json").write_text(json.dumps(result))
    assert store.finish(*claim, result)


def by_kind(store: TrackingStore) -> dict[str, dict[str, Any]]:
    return {a["kind"]: a for a in store.alerts() if a["resolved_at"] is None}


def test_stale_collection_without_worker_deduplicates_ack_and_requires_fresh_commit(
    tmp_path: Path,
    clock: SimulatedClock,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    original = store.get(mid)
    clock.advance(timedelta(seconds=419))
    assert store.alerts() == []
    clock.advance(timedelta(seconds=1))
    stale = by_kind(store)["stale_collection"]
    assert stale["evidence"]["last_healthy_collection_at"] is None
    assert stale["opened_at"] == clock.now().isoformat()
    store.acknowledge(mid, stale["id"])
    acknowledged = store.alerts()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: store.acknowledge(mid, stale["id"]), range(8)))
    assert store.alerts() == acknowledged
    store.control(mid, "pause")
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    assert reopened.alerts() == acknowledged
    reopened.control(mid, "resume")
    assert by_kind(reopened)["stale_collection"]["id"] == stale["id"]
    complete(reopened, mid, clock)
    resolved = reopened.alerts()[0]
    assert resolved["resolved_at"] == clock.now().isoformat()
    assert [e["action"] for e in resolved["events"]] == ["opened", "acknowledged", "resolved"]
    assert reopened.get(mid)["paper_account"] == original["paper_account"]  # type: ignore[index]
    clock.advance(timedelta(seconds=420))
    again = by_kind(reopened)["stale_collection"]
    assert again["id"] != stale["id"]
    assert again["acknowledged_at"] is None


def test_repeated_worker_failures_auto_pause_restart_and_ack_do_not_reset_incident(
    tmp_path: Path,
    clock: SimulatedClock,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    for _ in range(2):
        fail(store, mid, clock)
    assert "repeated_failures" not in by_kind(store)
    fail(store, mid, clock)
    alert = by_kind(store)["repeated_failures"]
    assert len(alert["evidence"]["cycle_ids"]) == 3
    store.acknowledge(mid, alert["id"])
    for _ in range(2):
        fail(store, mid, clock)
    assert store.get(mid)["status"] == "paused"  # type: ignore[index]
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    reopened.control(mid, "resume")
    current = by_kind(reopened)["repeated_failures"]
    assert current["id"] == alert["id"]
    assert current["acknowledged_at"]
    assert len(current["evidence"]["cycle_ids"]) == 5
    # Simulate death after an outbox write. Restart cannot commit it or clear an incident.
    claim = due(reopened, mid, clock)
    root = tmp_path / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    (root / "partial.json").write_text('{"CONTROLLED":"uncommitted"}')
    reopened.recover()
    assert not reopened.finish(*claim, {"detail": "late", "submission_enabled": False})
    assert by_kind(reopened)["repeated_failures"]["id"] == alert["id"]
    assert (root / "partial.json").read_bytes() == b'{"CONTROLLED":"uncommitted"}'
    complete(reopened, mid, clock)
    assert "repeated_failures" not in by_kind(reopened)
    value = reopened.get(mid, export=True)
    assert value
    assert not value["submission_enabled"]
    assert value["fills"] == []
    assert value["paper_account"] is None
    assert value["performance"] is None


def test_unresolved_reconciliation_uses_close_grace_not_inferred_outcome(
    tmp_path: Path,
    clock: SimulatedClock,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    close = clock.now()
    contract = {"ticker": "CONTROLLED", "market": {"close_time": close.isoformat()}}
    complete(store, mid, clock, contracts=[contract])
    store.control(mid, "pause")
    clock.advance(timedelta(seconds=3599))
    assert "unresolved_reconciliation" not in by_kind(store)
    clock.advance(timedelta(seconds=1))
    pending = by_kind(store)["unresolved_reconciliation"]
    store.acknowledge(mid, pending["id"])
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    assert reopened.get(mid)["contracts"][0]["outcome"] is None  # type: ignore[index]
    assert by_kind(reopened)["unresolved_reconciliation"]["id"] == pending["id"]
    reopened.control(mid, "resume")
    complete(reopened, mid, clock)
    assert "unresolved_reconciliation" in by_kind(reopened)
    # The existing worker owns receipt validation; the store only commits its supplied result.
    received = clock.now().isoformat()
    complete(
        reopened,
        mid,
        clock,
        outcomes=[
            {
                "ticker": "CONTROLLED",
                "result": "no",
                "available_at": received,
                "settled_at": close.isoformat(),
                "basis": "CONTROLLED official-result fixture",
            }
        ],
    )
    assert "unresolved_reconciliation" not in by_kind(reopened)
    assert reopened.get(mid)["contracts"][0]["outcome"]["available_at"] == received  # type: ignore[index]


def test_unresolved_reconciliation_waits_for_published_expected_settlement(
    tmp_path: Path,
    clock: SimulatedClock,
) -> None:
    """Weather markets close at local midnight but settle after the next-morning report."""
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    close = clock.now()
    expected = close + timedelta(hours=14)  # retained KXHIGHPHIL: close 05:00Z, expected 19:00Z
    contracts = [
        {
            "ticker": "CONTROLLED-EXPECTED",
            "market": {
                "close_time": close.isoformat(),
                "expected_expiration_time": expected.isoformat(),
                "latest_expiration_time": (close + timedelta(days=7)).isoformat(),
            },
        },
        {
            # An expected time before close is not a settlement promise; close governs.
            "ticker": "CONTROLLED-INCONSISTENT",
            "market": {
                "close_time": (close + timedelta(hours=10)).isoformat(),
                "expected_expiration_time": close.isoformat(),
            },
        },
    ]
    complete(store, mid, clock, contracts=contracts)
    store.control(mid, "pause")
    clock.advance(timedelta(hours=2))
    assert "unresolved_reconciliation" not in by_kind(store)  # the former close+1h false alarm
    clock.advance(timedelta(hours=9))
    alert = by_kind(store)["unresolved_reconciliation"]
    (inconsistent,) = alert["evidence"]["contracts"]
    assert inconsistent["ticker"] == "CONTROLLED-INCONSISTENT"
    assert inconsistent["basis"] == "close_time"
    clock.advance_to(expected + timedelta(seconds=3599))
    assert len(by_kind(store)["unresolved_reconciliation"]["evidence"]["contracts"]) == 1
    clock.advance(timedelta(seconds=1))
    current = by_kind(store)["unresolved_reconciliation"]
    assert current["id"] == alert["id"]
    late = {c["ticker"]: c for c in current["evidence"]["contracts"]}["CONTROLLED-EXPECTED"]
    assert late["basis"] == "expected_expiration_time"
    assert late["expected_settlement_at"] == expected.isoformat()
    assert late["close_time"] == close.isoformat()
    assert current["evidence"]["grace_seconds"] == 3600
    assert current["acknowledged_at"] is None


def test_alert_api_security_scope_idempotency_and_export(
    tmp_path: Path, clock: SimulatedClock
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    clock.advance(timedelta(hours=1))
    server = cast(
        "WorkbenchServer", SimpleNamespace(tracking=store, server_port=43128, token=str(uuid4()))
    )
    assert exchange(server, "/api/alerts", headers={"Host": "evil"})[0] == 403
    catalog = json.loads(exchange(server, "/api/alerts")[2])
    assert catalog["submission_enabled"] is False
    alert = catalog["alerts"][0]
    route = f"/api/monitors/{mid}/acknowledge"
    assert exchange(server, route, method="POST", body={"alert_id": alert["id"]})[0] == 403
    token = {"X-EntropyTrade-CSRF": server.token}
    other = monitor(store)
    assert (
        exchange(
            server,
            f"/api/monitors/{other}/acknowledge",
            method="POST",
            body={"alert_id": alert["id"]},
            headers=token,
        )[0]
        == 400
    )
    for payload in (
        {},
        {"alert_id": 1},
        {"alert_id": "../bad"},
        {"alert_id": alert["id"], "live": True},
    ):
        assert exchange(server, route, method="POST", body=payload, headers=token)[0] == 400
    for _ in range(2):
        assert (
            exchange(server, route, method="POST", body={"alert_id": alert["id"]}, headers=token)[0]
            == 200
        )
    exported = json.loads(exchange(server, f"/api/monitors/{mid}/export")[2])
    assert exported["alerts"][0]["acknowledged_at"]
    assert exported["alerts"][0]["resolved_at"] is None


def test_partial_collection_escalates_but_model_and_fee_refusals_are_not_worker_failures(
    tmp_path: Path,
    clock: SimulatedClock,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    for _ in range(3):
        complete(store, mid, clock, capture={"universe_complete": False, "failures": []})
    assert "repeated_failures" in by_kind(store)
    complete(store, mid, clock, capture=None)
    assert "repeated_failures" in by_kind(store)
    complete(
        store,
        mid,
        clock,
        model_refusals={"model": "no frozen fitted model"},
        decisions=[{"status": "blocked", "intent": None, "reasons": ["missing_fee_evidence"]}],
    )
    assert not by_kind(store)
    assert store.get(mid)["paper_account"] is None  # type: ignore[index]


def test_pre_alert_workspace_migrates_without_changing_existing_evidence(tmp_path: Path) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    store.control(mid, "pause")
    original = store.get(mid, export=True)
    with store.jobs.connect() as db:
        db.execute("DROP TABLE shadow_alert_events")
        db.execute("DROP TABLE shadow_alerts")
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    assert reopened.get(mid, export=True) == original


@pytest.mark.parametrize("busy", [False, True])
def test_background_checks_detect_staleness_without_browser_even_while_worker_is_busy(
    tmp_path: Path,
    clock: SimulatedClock,
    monkeypatch: pytest.MonkeyPatch,
    busy: bool,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    mid = monitor(store)
    runner = ShadowRunner(store, REPO, timeout=0)
    clock.advance(timedelta(seconds=420))
    if busy:
        claim = store.claim()
        assert claim

        class Process(ControlledProcess):
            def kill(self) -> None:
                # Detection must precede termination/finish, not rely on finish's refresh.
                current = store.get(mid)
                assert current
                assert any(a["kind"] == "stale_collection" for a in current["alerts"])
                super().kill()

        monkeypatch.setattr(
            "entropytrade.tracking.runner.subprocess.Popen", lambda *_a, **_k: Process()
        )
        runner.execute(*claim)
    else:

        def idle() -> None:
            runner.stop.set()

        monkeypatch.setattr(store, "claim", idle)
        runner.run()
    current = store.get(mid)
    assert current
    assert any(a["kind"] == "stale_collection" for a in current["alerts"])


def test_authentic_receipts_stay_blocked_while_operator_alerts_survive_restart(
    tmp_path: Path,
) -> None:
    receipt = seed_authentic(tmp_path / "authentic")
    store = TrackingStore(Jobs(tmp_path / "authentic"))
    value = store.get(receipt["monitor_id"], export=True)
    assert value
    before = {p: p.read_bytes() for p in (store.jobs.root / "shadow").rglob("*") if p.is_file()}
    assert all(d["intent"] is None for c in value["cycles"] for d in c["result"]["decisions"])
    assert any(
        not d["gates"]["point_in_time_prediction"]
        for c in value["cycles"]
        for d in c["result"]["decisions"]
    )
    pending = by_kind(store)["unresolved_reconciliation"]
    store.acknowledge(value["id"], pending["id"])
    exported = store.get(value["id"], export=True)
    reopened = TrackingStore(Jobs(store.jobs.root))
    reopened.recover()
    assert reopened.get(value["id"], export=True) == exported
    assert all(p.read_bytes() == body for p, body in before.items())


@pytest.mark.parametrize("corrupt", [False, True])
def test_snapshot_restore_preserves_ack_lifecycle_and_refuses_corruption(
    tmp_path: Path,
    clock: SimulatedClock,
    corrupt: bool,
) -> None:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED application identity")
    store = TrackingStore(Jobs(tmp_path / "data/cache/source"))
    mid = monitor(store)
    for _ in range(3):
        fail(store, mid, clock)
    for alert in store.alerts():
        store.acknowledge(mid, alert["id"])
    store.control(mid, "pause")
    if corrupt:
        with store.jobs.connect() as db:
            db.execute("UPDATE shadow_alerts SET acknowledged_at=NULL")
        with pytest.raises(ValueError, match="alert"):
            snapshot(tmp_path, store.jobs.root, tmp_path / "refused.zip")
        assert not (tmp_path / "refused.zip").exists()
        return
    expected = store.get(mid, export=True)
    archive = tmp_path / "saved.zip"
    snapshot(tmp_path, store.jobs.root, archive)
    destination = tmp_path / "data/cache/restored"
    restore(tmp_path, archive, destination)
    reopened = TrackingStore(Jobs(destination))
    reopened.recover()
    assert reopened.get(mid, export=True) == expected
    assert validate_database(destination)["monitors"] == 1
