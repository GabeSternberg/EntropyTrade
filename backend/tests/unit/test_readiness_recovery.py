"""CONTROLLED readiness audit recovery. No record here authorizes real-money execution."""

import json
import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot, validate_database
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.research.investigations import enqueue_investigation
from entropytrade.research.readiness import ResearchReadinessService
from entropytrade.research.service import ResearchService
from entropytrade.tracking.readiness_store import READINESS_TABLES, ReadinessStore
from entropytrade.tracking.store import TrackingStore
from tests.research_paper_forward_support import controlled_forward_environment
from tests.unit.test_paper_reconciliation import drained as drained
from tests.unit.test_tracking import REPO, monitor

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
HUMAN = {"kind": "human", "actor_id": "CONTROLLED-owner"}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED readiness recovery application identity: " + name)
    return tmp_path


def prepared(repo: Path) -> tuple[TrackingStore, ReadinessStore, str, str]:
    tracking = TrackingStore(Jobs(repo / "data/cache/readiness"))
    monitor_id = monitor(tracking)
    readiness = ReadinessStore(tracking.jobs, clock=SimulatedClock(NOW))
    guard = readiness.snapshot_guard(monitor_id)
    fingerprint = scientific_hash({"CONTROLLED-storage-boundary": monitor_id})
    proposal = {
        "schema": "CONTROLLED-readiness-storage-fixture",
        "monitor_id": monitor_id,
        "source_fingerprint": fingerprint,
        "control_epoch": 0,
        "eligible": True,
        "capital_envelope": {"max_dollars": "125.00"},
        "execution_authorized": False,
        "submission_enabled": False,
    }
    record = readiness.publish(
        proposal, monitor_id=monitor_id, source_fingerprint=fingerprint, guard=guard
    )
    readiness.review(
        record["id"],
        decision="approve",
        expected_revision=0,
        expected_epoch=0,
        expected_guard=readiness.snapshot_guard(monitor_id),
        actor=HUMAN,
        reason="CONTROLLED future-readiness storage test; real execution remains disabled",
    )
    return tracking, readiness, monitor_id, str(record["id"])


def rows(workspace: Path) -> dict[str, list[dict[str, Any]]]:
    with closing(sqlite3.connect(workspace / "jobs.sqlite")) as db:
        db.row_factory = sqlite3.Row
        return {
            table: [dict(r) for r in db.execute(f"SELECT * FROM {table}")]  # noqa: S608
            for table in READINESS_TABLES
        }


def test_readiness_halt_review_investigation_and_sentinel_survive_restore(repo: Path) -> None:
    tracking, readiness, monitor_id, proposal_id = prepared(repo)
    workspace = tracking.jobs.root
    claim = tracking.claim()
    assert claim is not None
    readiness.halt("CONTROLLED emergency stop")
    (workspace / "HALT").write_bytes(b"CONTROLLED owner stop sentinel\n")
    investigation = readiness.investigate(
        monitor_id,
        "CONTROLLED-stalled-collection",
        scientific_hash({"policy": "CONTROLLED"}),
    )
    before = rows(workspace)
    source_bytes = (workspace / "jobs.sqlite").read_bytes()
    assert validate_database(workspace)["monitors"] == 1
    assert (workspace / "jobs.sqlite").read_bytes() == source_bytes
    archive = repo / "data/recovery/readiness.zip"
    snapshot(repo, workspace, archive)
    destination = repo / "data/cache/restored"
    restore(repo, archive, destination)
    assert rows(destination) == before
    assert (destination / "HALT").read_bytes() == b"CONTROLLED owner stop sentinel\n"
    current = ReadinessStore(Jobs(destination))
    assert current.status()["halted"] is True
    record = current.get(proposal_id)
    assert record is not None
    assert record["status"] == "invalidated"
    assert record["capital_cents"] == 0
    assert record["execution_authorized"] is False
    with closing(sqlite3.connect(destination / "jobs.sqlite")) as db:
        assert (
            db.execute(
                "SELECT research_job_id FROM readiness_investigations WHERE id=?",
                (investigation["id"],),
            ).fetchone()[0]
            is None
        )


def test_release_history_and_approved_virtual_envelope_remain_read_only(repo: Path) -> None:
    tracking, readiness, _, proposal_id = prepared(repo)
    halted = readiness.halt("CONTROLLED review invalidation")
    readiness.release(halted["epoch"], actor=HUMAN, reason="CONTROLLED explicit owner release")
    before = rows(tracking.jobs.root)
    assert validate_database(tracking.jobs.root)["monitors"] == 1
    assert rows(tracking.jobs.root) == before
    assert readiness.get(proposal_id)["status"] == "invalidated"  # type: ignore[index]
    assert readiness.status()["halted"] is False


def test_unused_old_workspace_has_no_readiness_migration_after_roundtrip(repo: Path) -> None:
    tracking = TrackingStore(Jobs(repo / "data/cache/legacy"))
    monitor(tracking)
    workspace = tracking.jobs.root
    assert ReadinessStore(tracking.jobs).listing() == []
    with tracking.jobs.connect() as db:
        before = list(db.iterdump())
        assert (
            not {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            & READINESS_TABLES.keys()
        )
    archive = repo / "data/recovery/legacy.zip"
    snapshot(repo, workspace, archive)
    destination = repo / "data/cache/legacy-restored"
    restore(repo, archive, destination)
    with closing(sqlite3.connect(destination / "jobs.sqlite")) as db:
        assert list(db.iterdump()) == before


@pytest.mark.parametrize(
    "damage",
    [
        "partial_schema",
        "control_epoch",
        "control_audit",
        "proposal",
        "review_actor",
        "review_state",
        "cycle_control",
        "investigation",
    ],
)
def test_readiness_schema_and_audit_corruption_refuse_read_only(repo: Path, damage: str) -> None:
    tracking, readiness, monitor_id, proposal_id = prepared(repo)
    workspace = tracking.jobs.root
    if damage in {"control_epoch", "control_audit"}:
        readiness.halt("CONTROLLED event chain")
    if damage == "cycle_control":
        assert tracking.claim() is not None
    if damage == "investigation":
        readiness.investigate(
            monitor_id, "CONTROLLED-incident", scientific_hash({"CONTROLLED": "policy"})
        )
    with tracking.jobs.connect() as db:
        if damage == "partial_schema":
            db.execute("DROP TABLE readiness_events")
        elif damage == "control_epoch":
            db.execute("UPDATE workspace_controls SET epoch=epoch+1")
        elif damage == "control_audit":
            db.execute(
                "UPDATE workspace_control_events SET previous_hash=?",
                (scientific_hash("tampered"),),
            )
        elif damage == "proposal":
            db.execute("UPDATE readiness_proposals SET proposal='{}' WHERE id=?", (proposal_id,))
        elif damage == "review_actor":
            db.execute(
                "UPDATE readiness_events SET actor=? WHERE action='approved'",
                (json.dumps({"kind": "agent", "actor_id": "untrusted"}),),
            )
        elif damage == "review_state":
            db.execute(
                "UPDATE readiness_proposals SET capital_cents=capital_cents+1 WHERE id=?",
                (proposal_id,),
            )
        elif damage == "cycle_control":
            db.execute("UPDATE shadow_cycle_controls SET snapshot='{}'")
        else:
            db.execute("UPDATE readiness_investigations SET incident_key='changed'")
    with tracking.jobs.connect() as db:
        before = list(db.iterdump())
    with pytest.raises(ValueError, match=r"readiness|control|capital|proposal|investigation"):
        validate_database(workspace)
    with tracking.jobs.connect() as db:
        assert list(db.iterdump()) == before


def test_halted_settlement_drain_roundtrips_with_frozen_control_and_account(
    repo: Path, drained: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Genuine C fit -> controlled forward fill -> HALT -> official outcome-only drain.
    # This fixture uses simulated dates and wire responses; it is not empirical P&L.
    workspace = repo / "data/cache/drained"
    shutil.copytree(drained["fixture"].jobs.root, workspace)
    with controlled_forward_environment(drained["clock"]):
        readiness = ResearchReadinessService(
            workspace,
            TrackingStore(Jobs(workspace)),
            clock=drained["clock"],
            expected_data_kind="synthetic",
        )
        created = readiness.create(
            drained["monitor"]["id"], {"capital_dollars": "100.00", "max_loss_dollars": "10.00"}
        )
    facts = created["proposal"]["payload"]["facts"]
    assert any(check["name"] == "source_integrity" and check["passed"] for check in facts["checks"])
    current_monitor = readiness.tracking.get(drained["monitor"]["id"], export=True)
    assert current_monitor is not None
    outbox = enqueue_investigation(
        ResearchService(workspace, REPO, clock=drained["clock"]),
        readiness.store,
        current_monitor,
        "CONTROLLED-after-settlement",
        policy_hash=scientific_hash({"CONTROLLED": "policy"}),
        objective="Inspect retained simulation evidence without acquiring data",
    )
    assert outbox["research_job_id"]

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("backup/restore attempted to refit or rescore frozen readiness evidence")

    monkeypatch.setattr("entropytrade.research.readiness_evidence.proper_score_facts", forbidden)
    before = rows(workspace)
    assert validate_database(workspace)["cycles"] == 2
    archive = repo / "data/recovery/drained.zip"
    snapshot(repo, workspace, archive)
    destination = repo / "data/cache/drained-restored"
    restore(repo, archive, destination)
    assert rows(destination) == before
    current = TrackingStore(Jobs(destination)).get(drained["monitor"]["id"], export=True)
    assert current is not None
    assert current["paper_account"] == drained["monitor"]["paper_account"]
    result = current["cycles"][0]["result"]
    assert result["cycle_mode"] == "reconcile_only"
    assert result["control_snapshot"]["halted"] is True
    assert result["paper"]["settlements"]
    assert not result["paper"]["executions"]
    with closing(sqlite3.connect(destination / "research/research.sqlite")) as db:
        request = json.loads(
            db.execute(
                "SELECT request FROM research_jobs WHERE id=?", (outbox["research_job_id"],)
            ).fetchone()[0]
        )
    assert request["provider"]["provider"] == "local_templates"
    assert request["budget"]["ai_usd"] == "0"
    assert request["acquisition"] == "none"
    assert request["paper_preference"] == "never"


def test_failed_worker_backup_retains_control_without_creating_accounting(repo: Path) -> None:
    tracking, _, monitor_id, _ = prepared(repo)
    claim = tracking.claim()
    assert claim is not None
    assert tracking.finish(
        monitor_id,
        claim[1],
        {
            "detail": "CONTROLLED worker exit",
            "failure": "WorkerExit",
            "submission_enabled": False,
            "artifacts": [],
        },
        failed=True,
    )
    archive = repo / "data/recovery/failed-worker.zip"
    snapshot(repo, tracking.jobs.root, archive)
    destination = repo / "data/cache/failed-restored"
    restore(repo, archive, destination)
    result = TrackingStore(Jobs(destination)).get(monitor_id)
    assert result is not None
    assert result["cycles"][0]["status"] == "failed"
    assert result["paper_account"] is None


def test_reconciliation_schema_cannot_fall_back_to_paper_when_mode_is_rehashed(
    repo: Path, drained: dict[str, Any]
) -> None:
    workspace = repo / "data/cache/conflicting-drain-marker"
    shutil.copytree(drained["fixture"].jobs.root, workspace)
    assert validate_database(workspace)["cycles"] == 2
    monitor_id = drained["monitor"]["id"]
    cycle_id = drained["cycle"]["id"]
    control = {
        "schema": "shadow-cycle-control-v1",
        "control_epoch": 0,
        "cycle_mode": "paper",
        "halted": False,
        "event_hash": scientific_hash(None),
        "execution_authorized": False,
    }
    with closing(sqlite3.connect(workspace / "jobs.sqlite")) as db, db:
        result = json.loads(
            db.execute("SELECT result FROM shadow_cycles WHERE id=?", (cycle_id,)).fetchone()[0]
        )
        assert result["schema"] == "shadow-reconciliation-cycle-v1"
        result.update(cycle_mode="paper", control_epoch=0, control_snapshot=control)
        db.execute(
            "UPDATE shadow_cycle_controls SET epoch=0,mode='paper',snapshot=?,digest=? "
            "WHERE cycle_id=?",
            (json.dumps(control), scientific_hash(control), cycle_id),
        )
        db.execute(
            "UPDATE shadow_cycles SET result=?,digest=? WHERE id=?",
            (json.dumps(result), scientific_hash(result), cycle_id),
        )
    (workspace / "shadow" / monitor_id / cycle_id / "result.json").write_text(json.dumps(result))
    # All ordinary row/content hashes now agree. The schema marker must still select
    # settlement-only proof, whose strict verifier rejects the conflicting paper mode.
    with pytest.raises(ValueError, match=r"reconciliation|control|settlement"):
        validate_database(workspace)


def test_production_policy_refusal_preserves_partial_facts_through_restore(
    repo: Path, drained: dict[str, Any]
) -> None:
    workspace = repo / "data/cache/production-refusal"
    shutil.copytree(drained["fixture"].jobs.root, workspace)
    tracking = TrackingStore(Jobs(workspace))
    safety = ReadinessStore(tracking.jobs, clock=drained["clock"])
    safety.release(safety.status()["epoch"], actor=HUMAN, reason="CONTROLLED explicit release")
    tracking.control(drained["monitor"]["id"], "resume")
    production = ResearchReadinessService(workspace, tracking, clock=drained["clock"])
    created = production.create(
        drained["monitor"]["id"], {"capital_dollars": "100.00", "max_loss_dollars": "10.00"}
    )
    original = created["proposal"]["payload"]
    assert original["eligible"] is False
    facts = original["facts"]
    assert facts["source_refs"]["data_kind"] == "synthetic"
    assert "model_hash" not in facts["source_refs"]
    assert any(
        check["name"] == "authentic_provenance" and not check["passed"] for check in facts["checks"]
    )
    archive = repo / "data/recovery/production-refusal.zip"
    snapshot(repo, workspace, archive)
    destination = repo / "data/cache/production-refusal-restored"
    restore(repo, archive, destination)
    restored = ResearchReadinessService(
        destination, TrackingStore(Jobs(destination)), clock=drained["clock"]
    )
    record = restored.store.get(created["id"])
    assert record is not None
    assert record["payload"] == original
    assert record["status"] == "proposed"
    assert record["capital_cents"] == 0
    with pytest.raises(ValueError, match=r"readiness|eligib|evidence"):
        restored.prepare_review(
            created["id"],
            {
                "decision": "approve",
                "expected_revision": 0,
                "note": "CONTROLLED refusal must remain blocked",
            },
        )
