"""CONTROLLED storage/transaction proofs, never scientific eligibility or live authority."""

import json
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.research.model import ResearchRequest
from entropytrade.tracking.accounting import reproduce
from entropytrade.tracking.readiness_store import READINESS_TABLES, ReadinessStore
from entropytrade.tracking.store import TrackingStore
from tests.paper_support import paper_inputs
from tests.unit.test_tracking import monitor

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
OWNER = {"kind": "human", "actor_id": "authenticated-controlled-owner"}


@pytest.fixture
def stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TrackingStore, ReadinessStore, str]:
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: NOW.isoformat())
    tracking = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(tracking)
    return tracking, ReadinessStore(tracking.jobs, clock=SimulatedClock(NOW)), monitor_id


def publish(
    store: ReadinessStore,
    monitor_id: str,
    *,
    capital: str = "100.00",
    **changes: Any,
) -> dict[str, Any]:
    guard = store.snapshot_guard(monitor_id)
    fingerprint = scientific_hash(
        {
            "monitor_id": monitor_id,
            "spec_hash": guard["spec_hash"],
            "monitor_events_hash": guard["monitor_events_hash"],
        }
    )
    payload = {
        "schema_version": "CONTROLLED-readiness-storage-test-v1",
        "policy_hash": scientific_hash("CONTROLLED; no scientific eligibility assertion"),
        "monitor_id": monitor_id,
        "control_epoch": guard["control_epoch"],
        "source_fingerprint": fingerprint,
        "facts": {"controlled_storage_test": True},
        "capital_envelope": {"max_dollars": capital},
        "risk_limits": {},
        "checks": [],
        "reasons": [],
        "eligible": True,
        "execution_authorized": False,
        "submission_enabled": False,
    }
    return store.publish(
        payload,
        monitor_id=monitor_id,
        source_fingerprint=fingerprint,
        guard=guard,
        **changes,
    )


def approve(store: ReadinessStore, record: dict[str, Any], **changes: Any) -> dict[str, Any]:
    arguments = {
        "decision": "approve",
        "expected_revision": record["revision"],
        "expected_epoch": record["payload"]["control_epoch"],
        "expected_guard": store.snapshot_guard(record["monitor_id"]),
        "actor": OWNER,
        "reason": "CONTROLLED owner review of storage semantics",
    }
    return store.review(record["id"], **(arguments | changes))


def test_unused_legacy_paths_do_not_create_readiness_tables(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    assert store.status()["epoch"] == 0
    assert store.listing() == []
    assert store.get(scientific_hash("missing")) is None
    claim = tracking.claim()
    assert claim is not None
    assert claim[0] == monitor_id
    assert tracking.running(*claim)
    assert tracking.get(monitor_id)["cycles"][0]["control_epoch"] == 0  # type: ignore[index]
    with tracking.jobs.connect() as db:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not names & READINESS_TABLES.keys()


@pytest.mark.parametrize("legacy_short_poll", [False, True])
def test_settlement_claim_waits_for_frozen_expected_time_and_hourly_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, legacy_short_poll: bool
) -> None:
    clock = SimulatedClock(NOW)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    tracking = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(tracking)
    claim = tracking.claim()
    assert claim is not None
    inputs = paper_inputs()
    accounted = reproduce(inputs)
    position = accounted["state"]["ledger"]["positions"][0]
    ticker = position["contract"]["market_ticker"]
    close, expected = NOW + timedelta(hours=1), NOW + timedelta(hours=15)
    # A storage scheduling fixture: the holding comes from the real accountant,
    # while these explicitly controlled venue times assert no scientific eligibility.
    assert tracking.finish(
        *claim,
        {
            "detail": "CONTROLLED settlement schedule storage fixture",
            "paper_inputs": inputs,
            "paper": accounted,
            "contracts": [
                {
                    "ticker": ticker,
                    "market": {
                        "close_time": close.isoformat(),
                        "expected_expiration_time": expected.isoformat(),
                    },
                }
            ],
            "submission_enabled": False,
        },
    )
    tracking.control(monitor_id, "cancel")
    clock.advance_to(close + timedelta(seconds=1))
    assert tracking.claim() is None
    clock.advance_to(expected)
    legacy = monitor(tracking) if legacy_short_poll else None
    if legacy is not None:
        with tracking.jobs.connect() as db:
            db.execute(
                "UPDATE monitors SET next_at=? WHERE id=?",
                ((clock.now() + timedelta(seconds=60)).isoformat(), legacy),
            )
    first = tracking.claim()
    assert first is not None
    assert first[0] == monitor_id
    assert tracking.get(monitor_id)["cycles"][0]["cycle_mode"] == "reconcile_only"  # type: ignore[index]
    if legacy is not None:
        tracking.control(legacy, "cancel")
    # A worker death before any outcome attempt still consumes the hourly budget.
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    clock.advance_to(expected + timedelta(seconds=3599))
    assert reopened.claim() is None
    clock.advance(timedelta(seconds=1))
    retried = reopened.claim()
    assert retried is not None
    assert retried[0] == monitor_id
    assert retried[1] != first[1]
    assert reopened.get(monitor_id)["status"] == "cancelled"  # type: ignore[index]


def test_publish_is_immutable_idempotent_and_survives_restart(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    first = publish(store, monitor_id)
    same = publish(store, monitor_id)
    assert same == first
    assert first["id"] == scientific_hash(first["payload"])
    assert first["status"] == "proposed"
    assert first["revision"] == 0
    assert first["capital_cents"] == 0
    assert first["execution_authorized"] is False
    assert len(first["events"]) == 1
    reopened = ReadinessStore(Jobs(tracking.jobs.root))
    assert reopened.get(first["id"]) == first
    assert reopened.listing(monitor_id) == [first]


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_nonhuman_cannot_review_or_release(
    stores: tuple[TrackingStore, ReadinessStore, str], kind: str
) -> None:
    _, store, monitor_id = stores
    record = publish(store, monitor_id)
    actor = {"kind": kind, "actor_id": "CONTROLLED not authenticated owner"}
    for decision in ("approve", "reject"):
        with pytest.raises(ValueError, match="authenticated human"):
            approve(store, record, actor=actor, decision=decision)
    halted = store.halt("CONTROLLED halt")
    with pytest.raises(ValueError, match="authenticated human"):
        store.release(halted["epoch"], actor=actor, reason="CONTROLLED attempted bypass")


def test_virtual_ceiling_and_one_approval_per_monitor_are_atomic(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, first_id = stores
    second_id = monitor(tracking)
    first = approve(store, publish(store, first_id, capital="600.00"))
    blocked = publish(store, second_id, capital="500.00")
    with pytest.raises(ValueError, match="ceiling exceeded"):
        approve(store, blocked)
    assert store.get(blocked["id"])["status"] == "proposed"  # type: ignore[index]
    replacement = approve(store, publish(store, first_id, capital="550.00"))
    assert replacement["capital_cents"] == 55_000
    prior = store.get(first["id"])
    assert prior is not None
    assert prior["status"] == "superseded"
    assert prior["capital_cents"] == 0
    assert approve(store, publish(store, second_id, capital="450.00"))["capital_cents"] == 45_000
    assert all(row["execution_authorized"] is False for row in store.listing())
    assert tracking.get(first_id)["status"] == "active"  # type: ignore[index]


@pytest.mark.parametrize("capital", ["0", "-1", "1000.01", "0.001", "NaN", "Infinity"])
def test_invalid_frozen_capital_cannot_publish(
    stores: tuple[TrackingStore, ReadinessStore, str], capital: str
) -> None:
    _, store, monitor_id = stores
    with pytest.raises(ValueError, match="capital"):
        publish(store, monitor_id, capital=capital)
    assert store.listing() == []


@pytest.mark.parametrize("change", ["cycle", "account", "binding", "alert"])
def test_review_rechecks_observed_database_guard(
    stores: tuple[TrackingStore, ReadinessStore, str], change: str
) -> None:
    tracking, store, monitor_id = stores
    record = publish(store, monitor_id)
    guard = store.snapshot_guard(monitor_id)
    if change == "cycle":
        assert tracking.claim() is not None
    else:
        with tracking.jobs.connect() as db:
            if change == "account":
                state = {"ledger": Ledger(Decimal(1000), as_of=NOW).dump()}
                db.execute(
                    "INSERT INTO shadow_accounts VALUES (?,?,?)",
                    (monitor_id, json.dumps(state), scientific_hash(state)),
                )
            elif change == "binding":
                db.execute(
                    "UPDATE monitors SET model_binding=? WHERE id=?",
                    (json.dumps({"changed": True}), monitor_id),
                )
            else:
                db.execute(
                    "INSERT INTO shadow_alerts VALUES (?,?,?, ?,NULL,NULL,?)",
                    (str(uuid4()), monitor_id, "unresolved_reconciliation", NOW.isoformat(), "{}"),
                )
    with pytest.raises(ValueError, match="changed before review"):
        approve(store, record, expected_guard=guard)
    assert store.get(record["id"])["status"] == "proposed"  # type: ignore[index]


def test_normal_append_keeps_proposal_but_fresh_review_guard_is_required(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    record = publish(store, monitor_id)
    claim = tracking.claim()
    assert claim is not None
    assert tracking.finish(
        *claim, {"detail": "CONTROLLED no-data completion", "submission_enabled": False}
    )
    assert store.get(record["id"])["status"] == "proposed"  # type: ignore[index]
    assert approve(store, record)["status"] == "approved"


def test_pause_invalidates_review_and_release_never_resumes(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    record = approve(store, publish(store, monitor_id))
    tracking.control(monitor_id, "pause")
    invalid = store.get(record["id"])
    assert invalid is not None
    assert invalid["status"] == "invalidated"
    assert invalid["capital_cents"] == 0
    halted = store.halt("CONTROLLED kill")
    released = store.release(halted["epoch"], actor=OWNER, reason="CONTROLLED release")
    assert released["epoch"] == halted["epoch"] + 1
    assert released["halted"] is False
    assert tracking.get(monitor_id)["status"] == "paused"  # type: ignore[index]


def test_first_halt_interrupts_old_epoch_zero_claim_and_prevents_aba_commit(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    claim = tracking.claim()
    assert claim is not None
    halted = store.halt("CONTROLLED first halt")
    assert halted["epoch"] == 1
    assert not tracking.running(*claim)
    released = store.release(1, actor=OWNER, reason="CONTROLLED release")
    assert released["epoch"] == 2
    tracking.control(monitor_id, "resume")
    assert not tracking.finish(*claim, {"detail": "CONTROLLED late pre-halt output"})
    assert tracking.get(monitor_id)["cycles"][0]["status"] == "interrupted"  # type: ignore[index]


def test_sentinel_latches_even_if_resume_or_release_is_refused(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    sentinel = tracking.jobs.root / "HALT"
    sentinel.write_text("CONTROLLED owner sentinel\n")
    with pytest.raises(ValueError, match="halted"):
        tracking.control(monitor_id, "resume")
    assert store.status()["halted"] is True
    assert store.status()["epoch"] == 1
    with pytest.raises(ValueError, match="HALT sentinel"):
        store.release(1, actor=OWNER, reason="CONTROLLED forbidden release")
    assert sentinel.read_text() == "CONTROLLED owner sentinel\n"
    sentinel.unlink()  # Explicit controlled owner action, never the release implementation.
    assert store.status()["halted"] is True
    store.release(1, actor=OWNER, reason="CONTROLLED release after removal")
    assert tracking.claim() is None


def test_expired_owner_before_commit_rolls_back_review_and_release(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    _, store, monitor_id = stores
    record = publish(store, monitor_id)

    def expired() -> None:
        raise ValueError("CONTROLLED owner session expired while waiting for database")

    with pytest.raises(ValueError, match="session expired"):
        approve(store, record, before_commit=expired)
    assert store.get(record["id"])["status"] == "proposed"  # type: ignore[index]
    halted = store.halt("CONTROLLED kill")
    with pytest.raises(ValueError, match="session expired"):
        store.release(
            halted["epoch"], actor=OWNER, reason="CONTROLLED release", before_commit=expired
        )
    assert store.status()["halted"] is True
    assert store.status()["epoch"] == halted["epoch"]


def test_review_waiting_for_database_rechecks_owner_deadline(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    record = publish(store, monitor_id)
    guard = store.snapshot_guard(monitor_id)
    started, expired = threading.Event(), threading.Event()
    errors: list[str] = []

    def deadline() -> None:
        if expired.is_set():
            raise ValueError("CONTROLLED expired after lock wait")

    def waiting_review() -> None:
        started.set()
        try:
            approve(store, record, expected_guard=guard, before_commit=deadline)
        except ValueError as exc:
            errors.append(str(exc))

    with tracking.jobs.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        worker = threading.Thread(target=waiting_review)
        worker.start()
        assert started.wait(2)
        expired.set()
    worker.join(5)
    assert not worker.is_alive()
    assert errors == ["CONTROLLED expired after lock wait"]
    assert store.get(record["id"])["status"] == "proposed"  # type: ignore[index]


def test_investigation_deduplicates_incident_episode_and_freezes_job_link(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    _, store, monitor_id = stores
    policy = scientific_hash("CONTROLLED policy")
    one = store.investigate(monitor_id, "incident-episode-1", policy)
    assert store.investigate(monitor_id, "incident-episode-1", policy) == one
    job_id = str(uuid4())
    linked = store.investigate(monitor_id, "incident-episode-1", policy, research_job_id=job_id)
    assert linked["id"] == one["id"]
    assert linked["research_job_id"] == job_id
    with pytest.raises(ValueError, match="already linked"):
        store.investigate(monitor_id, "incident-episode-1", policy, research_job_id=str(uuid4()))
    assert store.investigate(monitor_id, "incident-episode-2", policy)["id"] != one["id"]


def test_tampered_review_state_and_control_audit_fail_closed(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    record = publish(store, monitor_id)
    with tracking.jobs.connect() as db:
        db.execute("UPDATE readiness_proposals SET status='approved' WHERE id=?", (record["id"],))
    with pytest.raises(ValueError, match="differs from its audit"):
        store.get(record["id"])
    store.halt("CONTROLLED kill")
    with tracking.jobs.connect() as db:
        db.execute("UPDATE workspace_controls SET halted=0")
    with pytest.raises(ValueError, match="audit/checksum"):
        tracking.claim()


def test_pause_resume_changes_material_identity_without_global_epoch_reset(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    old = publish(store, monitor_id)
    tracking.control(monitor_id, "pause")
    tracking.control(monitor_id, "resume")
    assert store.status()["epoch"] == 0
    fresh = publish(store, monitor_id)
    assert fresh["id"] != old["id"]
    assert fresh["source_fingerprint"] != old["source_fingerprint"]
    assert approve(store, fresh)["status"] == "approved"
    with pytest.raises(ValueError, match="changed before review"):
        approve(store, old)


def test_first_investigation_request_is_frozen_before_job_link(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    _, store, monitor_id = stores
    request = ResearchRequest(
        objective="CONTROLLED investigate a persistent source incident",
        family="weather",
        paper_preference="never",
    ).model_dump(mode="json")
    policy_hash = scientific_hash("CONTROLLED incident policy")
    outbox = store.investigate(monitor_id, "durable-episode", policy_hash, request=request)
    assert outbox["research_job_id"] is None
    assert json.loads(outbox["request_json"]) == request
    linked = store.investigate(
        monitor_id,
        "durable-episode",
        policy_hash,
        request=request,
        research_job_id=str(uuid4()),
    )
    assert linked["request"] == request
    with pytest.raises(ValueError, match="request is immutable"):
        store.investigate(
            monitor_id,
            "durable-episode",
            policy_hash,
            request=request | {"objective": "CONTROLLED changed request"},
        )


def test_readiness_writes_refuse_canonical_collector_ancestry(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path / "chain" / "restored")
    TrackingStore(jobs)
    store = ReadinessStore(jobs)
    with pytest.raises(ValueError, match="canonical collector"):
        store.halt("CONTROLLED prohibited readiness mutation")
    with jobs.connect() as db:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not names & READINESS_TABLES.keys()


def test_halt_can_protect_empty_workspace_before_first_monitor(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    store = ReadinessStore(jobs)
    assert store.halt("CONTROLLED preemptive safety reduction")["halted"] is True
    tracking = TrackingStore(jobs)
    with pytest.raises(ValueError, match="workspace is halted"):
        monitor(tracking)


def test_review_cas_matches_fresh_server_source_fingerprint(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    _, store, monitor_id = stores
    record = publish(store, monitor_id)
    with pytest.raises(ValueError, match="changed before review"):
        approve(
            store, record, expected_source_fingerprint=scientific_hash("CONTROLLED changed source")
        )
    assert store.get(record["id"])["status"] == "proposed"  # type: ignore[index]
    assert (
        approve(store, record, expected_source_fingerprint=record["source_fingerprint"])["status"]
        == "approved"
    )


def test_halt_arriving_during_final_review_guard_latches_without_approval(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores
    record = publish(store, monitor_id)

    def arrives() -> None:
        (tracking.jobs.root / "HALT").write_text("CONTROLLED concurrent safety signal")

    with pytest.raises(ValueError, match="control changed before"):
        approve(store, record, before_commit=arrives)
    assert store.status()["halted"] is True
    assert store.status()["epoch"] == 1
    assert store.get(record["id"])["status"] == "invalidated"  # type: ignore[index]


def test_halt_arriving_during_final_release_guard_is_never_cleared(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, _ = stores
    halted = store.halt("CONTROLLED initial halt")

    def arrives() -> None:
        (tracking.jobs.root / "HALT").write_text("CONTROLLED renewed safety signal")

    with pytest.raises(ValueError, match="appeared before"):
        store.release(
            halted["epoch"], actor=OWNER, reason="CONTROLLED release", before_commit=arrives
        )
    assert store.status()["halted"] is True
    assert store.status()["epoch"] == halted["epoch"]


def test_halt_arriving_during_account_verification_prevents_commit(
    stores: tuple[TrackingStore, ReadinessStore, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracking, store, monitor_id = stores
    claim = tracking.claim()
    assert claim is not None
    inputs = paper_inputs()
    result = {
        "detail": "CONTROLLED simulated accounting outbox",
        "paper_inputs": inputs,
        "paper": reproduce(inputs),
        "submission_enabled": False,
    }

    def arriving_reproduce(value: dict[str, Any]) -> dict[str, Any]:
        (tracking.jobs.root / "HALT").write_text("CONTROLLED concurrent safety signal")
        return reproduce(value)

    monkeypatch.setattr("entropytrade.tracking.store.reproduce", arriving_reproduce)
    assert tracking.finish(*claim, result) is False
    assert store.status()["halted"] is True
    current = tracking.get(monitor_id)
    assert current is not None
    assert current["paper_account"] is None
    assert current["cycles"][0]["status"] == "interrupted"


def test_expired_owner_cannot_save_or_rollback_but_system_can_reduce(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    _, store, monitor_id = stores

    def expired() -> None:
        raise ValueError("CONTROLLED expired owner deadline")

    with pytest.raises(ValueError, match="expired owner"):
        publish(store, monitor_id, before_commit=expired)
    assert store.listing() == []
    record = approve(store, publish(store, monitor_id))
    with pytest.raises(ValueError, match="expired owner"):
        store.invalidate(
            record["id"], "CONTROLLED rollback", actor=OWNER, revoke=True, before_commit=expired
        )
    assert store.get(record["id"])["status"] == "approved"  # type: ignore[index]
    assert (
        store.invalidate(record["id"], "CONTROLLED deterministic reduction", revoke=True)["status"]
        == "revoked"
    )


def test_halt_arriving_during_save_latches_without_publishing(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, store, monitor_id = stores

    def arrives() -> None:
        (tracking.jobs.root / "HALT").write_text("CONTROLLED concurrent safety signal")

    with pytest.raises(ValueError, match="publication commit"):
        publish(store, monitor_id, before_commit=arrives)
    assert store.status()["halted"] is True
    assert store.listing() == []


def test_reconciliation_schema_cannot_bypass_claim_mode_with_paper_marker(
    stores: tuple[TrackingStore, ReadinessStore, str],
) -> None:
    tracking, _, monitor_id = stores
    claim = tracking.claim()
    assert claim is not None
    inputs = paper_inputs()
    result = {
        "schema": "shadow-reconciliation-cycle-v1",
        "cycle_mode": "paper",
        "detail": "CONTROLLED conflicting markers",
        "paper_inputs": inputs,
        "paper": reproduce(inputs),
        "submission_enabled": False,
    }
    with pytest.raises(ValueError, match="mode/schema differs"):
        tracking.finish(*claim, result)
    assert tracking.get(monitor_id)["paper_account"] is None  # type: ignore[index]
