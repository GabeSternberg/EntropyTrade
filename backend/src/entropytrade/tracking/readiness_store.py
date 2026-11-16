"""Workspace safety and data-only readiness reviews in the existing Jobs database.

Schema creation is explicit and lazy. Unused legacy/collector workspaces retain their
original tables. Authentication belongs to the server; callers hold its owner lock
before entering these transactions, and this module never calls back into auth.
"""

import json
import sqlite3
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs, identifier
from entropytrade.domain.enums import ActorKind
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.features.registry import scientific_hash
from entropytrade.research.store import reject_collector_chain

READINESS_TABLES = {
    "workspace_controls": "singleton halted epoch reason updated_at actor event_hash",
    "workspace_control_events": "sequence at action epoch payload previous_hash digest",
    "shadow_cycle_controls": "cycle_id epoch mode snapshot digest",
    "readiness_proposals": (
        "id monitor_id proposal source_fingerprint guard status revision capital_cents "
        "created_at updated_at"
    ),
    "readiness_events": (
        "sequence proposal_id at action actor reason payload previous_hash digest"
    ),
    "readiness_investigations": (
        "id monitor_id incident_key policy_hash research_job_id created_at request_json"
    ),
}
SCHEMA = """
CREATE TABLE workspace_controls (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1), halted INTEGER NOT NULL,
    epoch INTEGER NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL,
    actor TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TABLE workspace_control_events (
    sequence INTEGER PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL,
    epoch INTEGER NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL,
    digest TEXT NOT NULL);
CREATE TABLE shadow_cycle_controls (
    cycle_id TEXT PRIMARY KEY, epoch INTEGER NOT NULL, mode TEXT NOT NULL,
    snapshot TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE readiness_proposals (
    id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, proposal TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL, guard TEXT NOT NULL, status TEXT NOT NULL,
    revision INTEGER NOT NULL, capital_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX one_approved_readiness_per_monitor ON readiness_proposals(monitor_id)
    WHERE status='approved';
CREATE TABLE readiness_events (
    sequence INTEGER PRIMARY KEY, proposal_id TEXT NOT NULL, at TEXT NOT NULL,
    action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, payload TEXT NOT NULL,
    previous_hash TEXT NOT NULL, digest TEXT NOT NULL);
CREATE TABLE readiness_investigations (
    id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, incident_key TEXT NOT NULL,
    policy_hash TEXT NOT NULL, research_job_id TEXT, created_at TEXT NOT NULL, request_json TEXT,
    UNIQUE(monitor_id, incident_key, policy_hash));
"""
EMPTY_HASH = scientific_hash(None)
SYSTEM_ACTOR = {"kind": "system", "actor_id": "local_safety_control"}
MAX_CAPITAL_CENTS = 100_000


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _actor(value: dict[str, Any] | None = None, *, human: bool = False) -> dict[str, Any]:
    actor = Actor.model_validate(value if value is not None else SYSTEM_ACTOR)
    if human and actor.kind is not ActorKind.HUMAN:
        raise ValueError("readiness review requires an authenticated human owner")
    return actor.model_dump(mode="json")


def enabled(db: sqlite3.Connection) -> bool:
    present = {
        row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    } & READINESS_TABLES.keys()
    if present and present != READINESS_TABLES.keys():
        raise ValueError("incomplete workspace readiness schema")
    return bool(present)


def _ensure(db: sqlite3.Connection, root: Path, now: str) -> None:
    reject_collector_chain(root)
    if enabled(db):
        return
    # executescript commits an existing transaction; execute each DDL statement instead.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            db.execute(statement)
    db.execute(
        "INSERT INTO workspace_controls VALUES (1, 0, 0, ?, ?, ?, ?)",
        ("Workspace readiness controls initialized", now, _json(SYSTEM_ACTOR), EMPTY_HASH),
    )


def initialize(db: sqlite3.Connection, root: Path, now: str) -> None:
    """Enable E only for an explicit readiness action or a real settlement drain."""
    _ensure(db, root, now)


def guard_write(db: sqlite3.Connection, root: Path) -> None:
    if enabled(db):
        reject_collector_chain(root)


def control_state(db: sqlite3.Connection) -> dict[str, Any]:
    if not enabled(db):
        return {
            "halted": False,
            "epoch": 0,
            "reason": "Controls not initialized",
            "updated_at": None,
            "actor": SYSTEM_ACTOR,
            "event_hash": EMPTY_HASH,
            "execution_authorized": False,
        }
    row = db.execute("SELECT * FROM workspace_controls WHERE singleton=1").fetchone()
    if row is None:
        raise ValueError("workspace control singleton is missing")
    state = {
        "halted": bool(row["halted"]),
        "epoch": row["epoch"],
        "reason": row["reason"],
        "updated_at": row["updated_at"],
        "actor": json.loads(row["actor"]),
        "event_hash": row["event_hash"],
        "execution_authorized": False,
    }
    if type(row["epoch"]) is not int or row["epoch"] < 0 or row["halted"] not in {0, 1}:
        raise ValueError("invalid workspace control state")
    events = db.execute("SELECT * FROM workspace_control_events ORDER BY sequence").fetchall()
    previous = EMPTY_HASH
    for expected_epoch, saved in enumerate(events, 1):
        event = {**dict(saved), "payload": json.loads(saved["payload"])}
        digest = event.pop("digest")
        if (
            event["sequence"] != expected_epoch
            or event["epoch"] != expected_epoch
            or event["previous_hash"] != previous
            or scientific_hash(event) != digest
        ):
            raise ValueError("workspace control audit/checksum mismatch")
        _actor(event["payload"]["actor"], human=event["action"] == "released")
        previous = digest
    if not events:
        if state["epoch"] != 0 or state["halted"] or state["event_hash"] != EMPTY_HASH:
            raise ValueError("workspace controls have no matching audit")
    else:
        latest = events[-1]
        event = {**dict(latest), "payload": json.loads(latest["payload"])}
        digest = event.pop("digest")
        if (
            scientific_hash(event) != digest
            or digest != state["event_hash"]
            or event["epoch"] != state["epoch"]
            or event["payload"] != {k: v for k, v in state.items() if k != "event_hash"}
        ):
            raise ValueError("workspace control audit/checksum mismatch")
    return state


def _proposal_event(
    db: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    action: str,
    actor: dict[str, Any],
    reason: str,
    now: str,
    observed_guard: dict[str, Any] | None = None,
) -> None:
    previous = db.execute(
        "SELECT digest FROM readiness_events WHERE proposal_id=? ORDER BY sequence DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    sequence = db.execute("SELECT coalesce(max(sequence),0)+1 FROM readiness_events").fetchone()[0]
    event = {
        "sequence": sequence,
        "proposal_id": row["id"],
        "at": now,
        "action": action,
        "actor": actor,
        "reason": reason,
        "payload": {
            "status": row["status"],
            "revision": row["revision"],
            "capital_cents": row["capital_cents"],
            "source_fingerprint": row["source_fingerprint"],
            "guard": json.loads(row["guard"]),
        },
        "previous_hash": previous[0] if previous else EMPTY_HASH,
    }
    if observed_guard is not None:
        event["payload"]["observed_guard"] = observed_guard
    db.execute(
        "INSERT INTO readiness_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sequence,
            row["id"],
            now,
            action,
            _json(actor),
            reason,
            _json(event["payload"]),
            event["previous_hash"],
            scientific_hash(event),
        ),
    )


def _transition(
    db: sqlite3.Connection,
    proposal_id: str,
    status: str,
    *,
    actor: dict[str, Any],
    reason: str,
    now: str,
    capital_cents: int = 0,
    observed_guard: dict[str, Any] | None = None,
) -> None:
    db.execute(
        "UPDATE readiness_proposals SET status=?, revision=revision+1, capital_cents=?, "
        "updated_at=? WHERE id=?",
        (status, capital_cents, now, proposal_id),
    )
    row = db.execute("SELECT * FROM readiness_proposals WHERE id=?", (proposal_id,)).fetchone()
    if row is None:
        raise ValueError("readiness proposal disappeared during transition")
    _proposal_event(
        db, row, action=status, actor=actor, reason=reason, now=now, observed_guard=observed_guard
    )


def invalidate_monitor(db: sqlite3.Connection, monitor_id: str, reason: str, now: str) -> None:
    if not enabled(db):
        return
    for row in db.execute(
        "SELECT id FROM readiness_proposals WHERE monitor_id=? "
        "AND status IN ('proposed','approved')",
        (monitor_id,),
    ).fetchall():
        _transition(db, row[0], "invalidated", actor=SYSTEM_ACTOR, reason=reason, now=now)


def _set_control(
    db: sqlite3.Connection,
    *,
    halted: bool,
    reason: str,
    actor: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    before = control_state(db)
    epoch = before["epoch"] + 1
    sequence = db.execute(
        "SELECT coalesce(max(sequence),0)+1 FROM workspace_control_events"
    ).fetchone()[0]
    payload = {
        "halted": halted,
        "epoch": epoch,
        "reason": reason,
        "updated_at": now,
        "actor": actor,
        "execution_authorized": False,
    }
    event = {
        "sequence": sequence,
        "at": now,
        "action": "halted" if halted else "released",
        "epoch": epoch,
        "payload": payload,
        "previous_hash": before["event_hash"],
    }
    digest = scientific_hash(event)
    db.execute(
        "INSERT INTO workspace_control_events VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sequence, now, event["action"], epoch, _json(payload), before["event_hash"], digest),
    )
    db.execute(
        "UPDATE workspace_controls SET halted=?,epoch=?,reason=?,updated_at=?,actor=?,"
        "event_hash=? WHERE singleton=1",
        (int(halted), epoch, reason, now, _json(actor), digest),
    )
    # A release does not reactivate a strategy. Both transitions invalidate old claims.
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "shadow_cycles" in tables:
        db.execute(
            "UPDATE shadow_cycles SET status='interrupted',finished_at=?,detail=? "
            "WHERE status='running'",
            (now, "Workspace control epoch changed; uncommitted receipts retained"),
        )
    if halted and "monitors" in tables:
        for monitor in db.execute("SELECT id FROM monitors WHERE status='active'").fetchall():
            db.execute("UPDATE monitors SET status='paused' WHERE id=?", (monitor[0],))
            db.execute(
                "INSERT INTO shadow_events(monitor_id,at,action) VALUES (?,?,?)",
                (monitor[0], now, "workspace halt; fresh explicit resume required"),
            )
    for row in db.execute(
        "SELECT id FROM readiness_proposals WHERE status IN ('proposed','approved')"
    ).fetchall():
        _transition(
            db,
            row[0],
            "invalidated",
            actor=actor,
            reason="Workspace control epoch changed",
            now=now,
        )
    return control_state(db)


def observe_halt(db: sqlite3.Connection, root: Path, now: str) -> dict[str, Any]:
    """Latch an observed sentinel transactionally; never remove the owner's file."""
    sentinel = root / "HALT"
    present = sentinel.exists() or sentinel.is_symlink()
    state = control_state(db)
    if present and not state["halted"]:
        _ensure(db, root, now)
        state = _set_control(
            db, halted=True, reason="Workspace HALT sentinel observed", actor=SYSTEM_ACTOR, now=now
        )
    return {**state, "halt_file_present": present}


def cycle_control(db: sqlite3.Connection, cycle_id: str) -> dict[str, Any]:
    row = (
        db.execute(
            "SELECT * FROM shadow_cycle_controls WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone()
        if enabled(db)
        else None
    )
    if row is None:
        return {
            "schema": "shadow-cycle-control-v1",
            "control_epoch": 0,
            "cycle_mode": "paper",
            "halted": False,
            "event_hash": EMPTY_HASH,
            "execution_authorized": False,
        }
    snapshot = json.loads(row["snapshot"])
    if (
        scientific_hash(snapshot) != row["digest"]
        or snapshot["control_epoch"] != row["epoch"]
        or snapshot["cycle_mode"] != row["mode"]
    ):
        raise ValueError("cycle control checksum mismatch")
    return dict(snapshot)


def freeze_cycle(db: sqlite3.Connection, cycle_id: str, mode: str) -> None:
    if mode not in {"paper", "reconcile_only"}:
        raise ValueError("unknown cycle control mode")
    if not enabled(db):
        return
    state = control_state(db)
    snapshot = {
        "schema": "shadow-cycle-control-v1",
        "control_epoch": state["epoch"],
        "cycle_mode": mode,
        "halted": state["halted"],
        "event_hash": state["event_hash"],
        "execution_authorized": False,
    }
    db.execute(
        "INSERT INTO shadow_cycle_controls VALUES (?, ?, ?, ?, ?)",
        (cycle_id, state["epoch"], mode, _json(snapshot), scientific_hash(snapshot)),
    )


def snapshot_guard(db: sqlite3.Connection, monitor_id: str) -> dict[str, Any]:
    monitor = db.execute("SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)).fetchone()
    if monitor is None:
        raise ValueError("monitor not found")
    if StrategySpec.model_validate_json(monitor["spec"]).spec_hash() != monitor["spec_hash"]:
        raise ValueError("readiness monitor strategy checksum mismatch")
    binding = json.loads(monitor["model_binding"]) if monitor["model_binding"] else None
    source = json.loads(monitor["source_ref"]) if monitor["source_ref"] else None
    account = db.execute(
        "SELECT state,digest FROM shadow_accounts WHERE monitor_id=?", (monitor_id,)
    ).fetchone()
    if account is not None and scientific_hash(json.loads(account["state"])) != account["digest"]:
        raise ValueError("readiness paper account checksum mismatch")
    head = db.execute(
        "SELECT id,sequence,status,digest,result FROM shadow_cycles WHERE monitor_id=? "
        "ORDER BY sequence DESC LIMIT 1",
        (monitor_id,),
    ).fetchone()
    if (
        head is not None
        and head["result"] is not None
        and scientific_hash(json.loads(head["result"])) != head["digest"]
    ):
        raise ValueError("readiness cycle head checksum mismatch")
    incidents = [
        {
            "id": row["id"],
            "kind": row["kind"],
            "acknowledged_at": row["acknowledged_at"],
            "evidence_hash": scientific_hash(json.loads(row["evidence"])),
        }
        for row in db.execute(
            "SELECT * FROM shadow_alerts WHERE monitor_id=? AND resolved_at IS NULL ORDER BY id",
            (monitor_id,),
        )
    ]
    return {
        "schema": "readiness-db-guard-v1",
        "monitor_id": monitor_id,
        "monitor_status": monitor["status"],
        "spec_hash": monitor["spec_hash"],
        "binding_hash": scientific_hash(binding),
        "source_hash": scientific_hash(source),
        "deployment_key": monitor["deployment_key"],
        "monitor_events_hash": scientific_hash(
            [
                dict(row)
                for row in db.execute(
                    "SELECT at,action FROM shadow_events WHERE monitor_id=? ORDER BY sequence",
                    (monitor_id,),
                )
            ]
        ),
        "account_hash": account["digest"] if account else EMPTY_HASH,
        "cycle_head": {key: head[key] for key in ("id", "sequence", "status", "digest")}
        if head
        else None,
        "alerts": incidents,
        "control_epoch": control_state(db)["epoch"],
    }


def _capital(payload: dict[str, Any]) -> int:
    try:
        raw = payload["capital_envelope"]["max_dollars"]
        if not isinstance(raw, str):
            raise ValueError("capital must be an exact decimal string")
        amount = Decimal(raw)
        if not amount.is_finite() or not 0 < amount <= 1000:
            raise ValueError("readiness capital must be within virtual $1000 ceiling")
        cents = amount * 100
        if (
            not amount.is_finite()
            or cents != cents.to_integral_value()
            or not 0 < cents <= MAX_CAPITAL_CENTS
        ):
            raise ValueError(
                "readiness capital must be positive cents within virtual $1000 ceiling"
            )
        return int(cents)
    except (InvalidOperation, KeyError, TypeError) as exc:
        raise ValueError("invalid frozen readiness capital envelope") from exc


class ReadinessStore:
    def __init__(self, jobs: Jobs, *, clock: Clock | None = None) -> None:
        self.jobs = jobs
        self.clock = clock or SystemClock()

    def _now(self) -> str:
        return self.clock.now().isoformat()

    def status(self) -> dict[str, Any]:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = observe_halt(db, self.jobs.root, self._now())
            events = (
                [
                    {**dict(row), "payload": json.loads(row["payload"])}
                    for row in db.execute(
                        "SELECT * FROM workspace_control_events ORDER BY sequence"
                    )
                ]
                if enabled(db)
                else []
            )
            return {**state, "events": events, "capital_ceiling_dollars": "1000.00"}

    def halt(self, reason: str, *, actor: dict[str, Any] | None = None) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("halt reason is required")
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._now()
            _ensure(db, self.jobs.root, now)
            return _set_control(db, halted=True, reason=reason, actor=_actor(actor), now=now)

    def release(
        self,
        expected_epoch: int,
        *,
        actor: dict[str, Any],
        reason: str,
        before_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        principal = _actor(actor, human=True)
        # An observed HALT latch survives even when this requested release is refused.
        self.status()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._now()
            _ensure(db, self.jobs.root, now)
            state = observe_halt(db, self.jobs.root, now)
            if state["halt_file_present"]:
                # A sentinel can appear after status() or while waiting for this lock.
                # Its safety latch is a separate permitted reduction, even when the
                # requested release is refused and the context rolls back afterward.
                db.commit()
                raise ValueError("remove the HALT sentinel before an authenticated release")
            if (
                type(expected_epoch) is not int
                or state["epoch"] != expected_epoch
                or not state["halted"]
            ):
                raise ValueError("workspace control epoch changed or workspace is not halted")
            if before_commit is not None:
                before_commit()
            if observe_halt(db, self.jobs.root, self._now())["halt_file_present"]:
                db.commit()
                raise ValueError("HALT sentinel appeared before authenticated release commit")
            return _set_control(db, halted=False, reason=reason, actor=principal, now=now)

    def snapshot_guard(self, monitor_id: str) -> dict[str, Any]:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            observe_halt(db, self.jobs.root, self._now())
            return snapshot_guard(db, monitor_id)

    def _record(self, db: sqlite3.Connection, proposal_id: str) -> dict[str, Any]:
        row = db.execute("SELECT * FROM readiness_proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise ValueError("readiness proposal not found")
        result = dict(row)
        result["payload"] = json.loads(result.pop("proposal"))
        result["guard"] = json.loads(result["guard"])
        if scientific_hash(result["payload"]) != proposal_id:
            raise ValueError("immutable readiness proposal checksum mismatch")
        result["events"] = [
            {**dict(e), "actor": json.loads(e["actor"]), "payload": json.loads(e["payload"])}
            for e in db.execute(
                "SELECT * FROM readiness_events WHERE proposal_id=? ORDER BY sequence",
                (proposal_id,),
            )
        ]
        previous = EMPTY_HASH
        for event in result["events"]:
            if (
                event["previous_hash"] != previous
                or scientific_hash({key: value for key, value in event.items() if key != "digest"})
                != event["digest"]
            ):
                raise ValueError("readiness audit checksum mismatch")
            _actor(event["actor"], human=event["action"] in {"approved", "rejected"})
            previous = event["digest"]
        current = {
            "status": result["status"],
            "revision": result["revision"],
            "capital_cents": result["capital_cents"],
            "source_fingerprint": result["source_fingerprint"],
            "guard": result["guard"],
        }
        if not result["events"] or any(
            result["events"][-1]["payload"].get(key) != value for key, value in current.items()
        ):
            raise ValueError("readiness review state differs from its audit")
        result["execution_authorized"] = False
        return result

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        with self.jobs.connect() as db:
            if (
                not enabled(db)
                or db.execute(
                    "SELECT 1 FROM readiness_proposals WHERE id=?",
                    (proposal_id,),
                ).fetchone()
                is None
            ):
                return None
            return self._record(db, proposal_id)

    def listing(self, monitor_id: str | None = None) -> list[dict[str, Any]]:
        with self.jobs.connect() as db:
            if not enabled(db):
                return []
            query, args = (
                "SELECT id FROM readiness_proposals",
                () if monitor_id is None else (identifier(monitor_id),),
            )
            if monitor_id is not None:
                query += " WHERE monitor_id=?"
            return [
                self._record(db, row[0])
                for row in db.execute(query + " ORDER BY created_at,id", args).fetchall()
            ]

    def publish(
        self,
        proposal: dict[str, Any],
        *,
        monitor_id: str,
        source_fingerprint: str,
        guard: dict[str, Any],
        before_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        if (
            proposal.get("monitor_id") != monitor_id
            or proposal.get("source_fingerprint") != source_fingerprint
            or proposal.get("execution_authorized") is not False
            or proposal.get("submission_enabled") is not False
            or "proposal_hash" in proposal
        ):
            raise ValueError("readiness proposal requires frozen data-only source references")
        _capital(proposal)
        encoded, proposal_id = _json(proposal), scientific_hash(proposal)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._now()
            _ensure(db, self.jobs.root, now)
            state = observe_halt(db, self.jobs.root, now)
            if (
                snapshot_guard(db, monitor_id) != guard
                or proposal.get("control_epoch") != state["epoch"]
            ):
                if state["halt_file_present"]:
                    db.commit()  # Preserve only the safety latch when publication loses its CAS.
                raise ValueError("readiness source changed during publication")
            if db.execute(
                "SELECT 1 FROM readiness_proposals WHERE id=?", (proposal_id,)
            ).fetchone():
                if before_commit is not None:
                    before_commit()
                return self._record(db, proposal_id)
            if before_commit is not None:
                before_commit()
            latest = observe_halt(db, self.jobs.root, self._now())
            if latest["epoch"] != state["epoch"]:
                db.commit()  # Only the observed safety reduction, never this new proposal.
                raise ValueError("workspace control changed before readiness publication commit")
            db.execute(
                "INSERT INTO readiness_proposals VALUES (?,?,?,?,?,'proposed',0,0,?,?)",
                (proposal_id, monitor_id, encoded, source_fingerprint, _json(guard), now, now),
            )
            row = db.execute(
                "SELECT * FROM readiness_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
            if row is None:
                raise ValueError("readiness proposal disappeared during publication")
            _proposal_event(
                db,
                row,
                action="published",
                actor=SYSTEM_ACTOR,
                reason="Immutable data-only proposal",
                now=now,
            )
            return self._record(db, proposal_id)

    def review(
        self,
        proposal_id: str,
        *,
        decision: str,
        expected_revision: int,
        expected_epoch: int,
        expected_guard: dict[str, Any],
        actor: dict[str, Any],
        reason: str,
        before_commit: Callable[[], None] | None = None,
        expected_source_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        principal = _actor(actor, human=True)
        if decision not in {"approve", "reject"}:
            raise ValueError("unknown readiness review decision")
        reject_collector_chain(self.jobs.root)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._now()
            state = observe_halt(db, self.jobs.root, now)
            record = self._record(db, proposal_id)
            current = snapshot_guard(db, record["monitor_id"])
            frozen = record["guard"]
            refs = (
                "monitor_id",
                "monitor_status",
                "spec_hash",
                "binding_hash",
                "source_hash",
                "deployment_key",
                "monitor_events_hash",
            )
            if (
                record["status"] != "proposed"
                or (
                    expected_source_fingerprint is not None
                    and (
                        record["source_fingerprint"] != expected_source_fingerprint
                        or record["payload"]["source_fingerprint"] != expected_source_fingerprint
                    )
                )
                or type(expected_revision) is not int
                or record["revision"] != expected_revision
                or type(expected_epoch) is not int
                or state["epoch"] != expected_epoch
                or record["payload"]["control_epoch"] != expected_epoch
                or current != expected_guard
                or any(current[key] != frozen[key] for key in refs)
            ):
                if state["halt_file_present"]:
                    db.commit()  # A refused owner review cannot undo an observed HALT.
                raise ValueError("readiness proposal/control/source changed before review commit")
            capital = 0

            def commit_guard() -> None:
                if before_commit is not None:
                    before_commit()
                latest = observe_halt(db, self.jobs.root, self._now())
                if latest["epoch"] != expected_epoch or (
                    decision == "approve" and latest["halted"]
                ):
                    db.commit()  # Preserve a newly observed safety reduction, never approval.
                    raise ValueError("workspace control changed before readiness review commit")

            if decision == "approve":
                if (
                    state["halted"]
                    or current["monitor_status"] != "active"
                    or current["alerts"]
                    or record["payload"].get("eligible") is not True
                ):
                    raise ValueError("halted, inactive or degraded evidence cannot be approved")
                capital = _capital(record["payload"])
                allocated = db.execute(
                    "SELECT coalesce(sum(capital_cents),0) FROM readiness_proposals "
                    "WHERE status='approved' AND monitor_id<>?",
                    (record["monitor_id"],),
                ).fetchone()[0]
                if allocated + capital > MAX_CAPITAL_CENTS:
                    raise ValueError("workspace virtual readiness capital ceiling exceeded")
                commit_guard()
                for row in db.execute(
                    "SELECT id FROM readiness_proposals WHERE status='approved' AND monitor_id=?",
                    (record["monitor_id"],),
                ).fetchall():
                    _transition(
                        db,
                        row[0],
                        "superseded",
                        actor=principal,
                        reason="New immutable proposal approved",
                        now=now,
                    )
            else:
                commit_guard()
            _transition(
                db,
                proposal_id,
                "approved" if decision == "approve" else "rejected",
                actor=principal,
                reason=reason,
                now=now,
                capital_cents=capital,
                observed_guard=current,
            )
            return self._record(db, proposal_id)

    def invalidate(
        self,
        proposal_id: str,
        reason: str,
        *,
        actor: dict[str, Any] | None = None,
        revoke: bool = False,
        before_commit: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        reject_collector_chain(self.jobs.root)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            record = self._record(db, proposal_id)
            if before_commit is not None:
                before_commit()
            observe_halt(db, self.jobs.root, self._now())
            record = self._record(db, proposal_id)
            if record["status"] in {"proposed", "approved"}:
                _transition(
                    db,
                    proposal_id,
                    "revoked" if revoke else "invalidated",
                    actor=_actor(actor),
                    reason=reason,
                    now=self._now(),
                )
            return self._record(db, proposal_id)

    def investigate(
        self,
        monitor_id: str,
        incident_key: str,
        policy_hash: str,
        *,
        research_job_id: str | None = None,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = {
            "monitor_id": identifier(monitor_id),
            "incident_key": incident_key,
            "policy_hash": policy_hash,
        }
        investigation_id = scientific_hash(key)
        if not incident_key or not policy_hash:
            raise ValueError("investigation requires an incident episode and policy")
        if research_job_id is not None:
            identifier(research_job_id)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            _ensure(db, self.jobs.root, self._now())
            if db.execute("SELECT 1 FROM monitors WHERE id=?", (monitor_id,)).fetchone() is None:
                raise ValueError("investigation monitor not found")
            db.execute(
                "INSERT OR IGNORE INTO readiness_investigations VALUES (?,?,?,?,?,?,?)",
                (
                    investigation_id,
                    monitor_id,
                    incident_key,
                    policy_hash,
                    research_job_id,
                    self._now(),
                    _json(request) if request is not None else None,
                ),
            )
            row = db.execute(
                "SELECT * FROM readiness_investigations WHERE id=?", (investigation_id,)
            ).fetchone()
            if row is None:
                raise ValueError("readiness investigation disappeared during publication")
            if request is not None:
                encoded_request = _json(request)
                if row["request_json"] not in {None, encoded_request}:
                    raise ValueError("incident investigation request is immutable")
                if row["request_json"] is None:
                    db.execute(
                        "UPDATE readiness_investigations SET request_json=? WHERE id=?",
                        (encoded_request, investigation_id),
                    )
            if research_job_id is not None and row["research_job_id"] not in {
                None,
                research_job_id,
            }:
                raise ValueError("incident investigation already linked to a research job")
            if research_job_id is not None and row["research_job_id"] is None:
                db.execute(
                    "UPDATE readiness_investigations SET research_job_id=? WHERE id=?",
                    (research_job_id, investigation_id),
                )
            result = dict(
                db.execute(
                    "SELECT * FROM readiness_investigations WHERE id=?", (investigation_id,)
                ).fetchone()
            )
            result["request"] = (
                json.loads(result["request_json"]) if result["request_json"] else None
            )
            return result
