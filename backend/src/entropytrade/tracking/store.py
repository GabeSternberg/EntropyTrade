"""Transactional monitor controls, append-only cycles and frozen contract evidence."""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from entropytrade.api.jobs import COURSE_MODE, Jobs, identifier, timestamp
from entropytrade.domain.strategy import StrategySpec
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.tracking import alerts
from entropytrade.tracking import readiness_store as readiness
from entropytrade.tracking.accounting import account_hash, reproduce, summary
from entropytrade.tracking.models import freeze_binding

HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
SOURCE_SCHEMA = "autonomous-paper-source-v1"
RECONCILIATION_RETRY_SECONDS = 3600
RECONCILIATION_WORKER_SECONDS = 240


def research_deployment_key(source: dict[str, Any]) -> str:
    """A material model, strategy or eligibility change creates a new deployment."""
    return scientific_hash(
        {
            key: source[key]
            for key in ("research_job_id", "experiment_id", "spec_hash", "binding_hash")
        }
        | {"proposal_hash": source["eligibility"]["proposal_hash"]}
    )


def validate_research_source(monitor: dict[str, Any]) -> dict[str, Any]:
    """Check immutable origin bindings without reading files or running a model."""
    source = monitor["source_ref"]
    if isinstance(source, str):
        source = json.loads(source)
    binding = monitor["model_binding"]
    if isinstance(binding, str):
        binding = json.loads(binding)
    if (
        monitor.get("source_kind") != "autonomous_research"
        or not isinstance(source, dict)
        or source.get("schema") != SOURCE_SCHEMA
        or scientific_hash({k: v for k, v in source.items() if k != "source_hash"})
        != source.get("source_hash")
        or source.get("research_job_id") != monitor["research_job_id"]
        or source.get("research_job_id") != monitor["job_id"]
        or source.get("experiment_id") != monitor["experiment_id"]
        or source.get("hypothesis_id") != monitor["candidate_id"]
        or source.get("spec_hash") != monitor["spec_hash"]
        or not isinstance(binding, dict)
        or source.get("binding_hash") != binding.get("binding_hash")
    ):
        raise ValueError("research paper source reference/hash mismatch")
    serialized_spec = monitor["spec"]
    actual_spec = (
        StrategySpec.model_validate_json(serialized_spec)
        if isinstance(serialized_spec, str)
        else StrategySpec.model_validate(serialized_spec)
    )
    if actual_spec.spec_hash() != monitor["spec_hash"]:
        raise ValueError("research paper immutable strategy hash mismatch")
    eligibility = source.get("eligibility")
    if (
        not isinstance(eligibility, dict)
        or eligibility.get("schema") != "research-paper-eligibility-v1"
        or eligibility.get("eligible") is not True
        or not isinstance(eligibility.get("proposal_hash"), str)
        or HASH.fullmatch(eligibility["proposal_hash"]) is None
        or research_deployment_key(source) != monitor["deployment_key"]
    ):
        raise ValueError("research paper eligibility/deployment key mismatch")
    from entropytrade.research.paper import validate_paper_policy

    validate_paper_policy(eligibility)
    return dict(source)


def _research_next(monitor: dict[str, Any], now: str) -> str:
    from entropytrade.research.paper_models import (
        next_research_decision,
        verify_research_binding,
    )

    spec = StrategySpec.model_validate_json(monitor["spec"])
    binding = json.loads(monitor["model_binding"])
    verify_research_binding(spec, binding, data_kind=binding["snapshot"]["data_kind"])
    current = datetime.fromisoformat(now)
    future = next_research_decision(binding, current)
    if future.utcoffset() is None or future <= current:
        raise ValueError("research paper schedule must advance to a future trained decision")
    return future.isoformat()


class TrackingStore:
    def __init__(self, jobs: Jobs) -> None:
        self.jobs = jobs
        with jobs.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS monitors (
                    id TEXT PRIMARY KEY, job_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                    family TEXT NOT NULL, spec TEXT NOT NULL, spec_hash TEXT NOT NULL,
                    status TEXT NOT NULL, interval_seconds INTEGER NOT NULL,
                    next_at TEXT NOT NULL, created_at TEXT NOT NULL, failures INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS shadow_cycles (
                    id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
                    detail TEXT NOT NULL, result TEXT, digest TEXT,
                    UNIQUE(monitor_id, sequence));
                CREATE UNIQUE INDEX IF NOT EXISTS one_shadow_cycle
                    ON shadow_cycles(monitor_id) WHERE status='running';
                CREATE TABLE IF NOT EXISTS shadow_events (
                    sequence INTEGER PRIMARY KEY, monitor_id TEXT NOT NULL,
                    at TEXT NOT NULL, action TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS shadow_contracts (
                    monitor_id TEXT NOT NULL, ticker TEXT NOT NULL, market TEXT NOT NULL,
                    last_attempt TEXT NOT NULL, outcome TEXT,
                    PRIMARY KEY(monitor_id, ticker));
                CREATE TABLE IF NOT EXISTS shadow_accounts (
                    monitor_id TEXT PRIMARY KEY, state TEXT NOT NULL, digest TEXT NOT NULL);
            """)
            if "model_binding" not in {r[1] for r in db.execute("PRAGMA table_info(monitors)")}:
                db.execute("ALTER TABLE monitors ADD COLUMN model_binding TEXT")
            columns = {r[1] for r in db.execute("PRAGMA table_info(monitors)")}
            for name, definition in (
                ("source_kind", "TEXT NOT NULL DEFAULT 'legacy'"),
                ("research_job_id", "TEXT"),
                ("experiment_id", "TEXT"),
                ("deployment_key", "TEXT"),
                ("source_ref", "TEXT"),
            ):
                if name not in columns:
                    db.execute(f"ALTER TABLE monitors ADD COLUMN {name} {definition}")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_research_paper_deployment "
                "ON monitors(deployment_key) WHERE deployment_key IS NOT NULL"
            )
            db.executescript(alerts.SCHEMA)

    def _latch_sentinel(self) -> None:
        sentinel = self.jobs.root / "HALT"
        if sentinel.exists() or sentinel.is_symlink():
            with self.jobs.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                readiness.observe_halt(db, self.jobs.root, timestamp())

    def alerts(self) -> list[dict[str, Any]]:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            alerts.refresh(db, timestamp())
            return alerts.history(db)

    def acknowledge(self, monitor_id: str, alert_id: str) -> None:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = timestamp()
            alerts.refresh(db, now)
            alerts.acknowledge(db, monitor_id, alert_id, now)

    def create(self, value: object) -> str:
        from entropytrade.strategies.interpret import compile_strategy

        self._latch_sentinel()
        if not isinstance(value, dict) or set(value) != {
            "job_id",
            "candidate_id",
            "interval_seconds",
        }:
            raise ValueError("provide job_id, candidate_id and interval_seconds only")
        interval = value["interval_seconds"]
        if type(interval) is not int or not 60 <= interval <= 3600:
            raise ValueError("poll interval must be 60-3600 seconds")
        if not isinstance(value["job_id"], str) or not isinstance(value["candidate_id"], str):
            raise ValueError("job and candidate IDs must be strings")
        job = self.jobs.get(identifier(value["job_id"]))
        if not job or job["status"] != "completed" or not job["result"]:
            raise ValueError("select a completed research run")
        if job["request"]["mode"] == COURSE_MODE:
            raise ValueError("course research runs cannot start shadow monitors")
        if job["result"]["data_kind"] != "real":
            raise ValueError("synthetic candidates cannot monitor real markets")
        proposals = job["result"].get("proposals", [])
        proposal = next((p for p in proposals if p["candidate_id"] == value["candidate_id"]), None)
        if not proposal or not proposal.get("spec"):
            raise ValueError("select a typed candidate specification")
        spec = StrategySpec.model_validate(proposal["spec"])
        spec, binding = freeze_binding(job, proposal["candidate_id"], spec, self.jobs.root)
        compile_strategy(spec)
        if spec.exit_mode != "hold_to_settlement":
            raise ValueError("shadow reservations currently require hold-to-settlement exits")
        monitor_id, now = str(uuid4()), timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, now)
            readiness.guard_write(db, self.jobs.root)
            if state["halted"]:
                db.commit()
                raise ValueError("workspace is halted; new paper monitors cannot start")
            if db.execute("SELECT count(*) FROM monitors WHERE status='active'").fetchone()[0] >= 4:
                raise ValueError("four active monitors maximum; pause one first")
            if db.execute("SELECT count(*) FROM monitors").fetchone()[0] >= 100:
                raise ValueError("workspace monitor budget reached (100)")
            db.execute(
                "INSERT INTO monitors (id, job_id, candidate_id, family, spec, spec_hash, status, "
                "interval_seconds, next_at, created_at, failures, model_binding) "
                "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, 0, ?)",
                (
                    monitor_id,
                    job["id"],
                    proposal["candidate_id"],
                    job["request"]["family"],
                    spec.model_dump_json(),
                    spec.spec_hash(),
                    interval,
                    now,
                    now,
                    json.dumps(binding, sort_keys=True),
                ),
            )
            db.execute(
                "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                (monitor_id, now, "created; shadow only, no validation approval implied"),
            )
        return monitor_id

    def create_research(
        self,
        *,
        research_job_id: str,
        experiment_id: str,
        hypothesis_id: str,
        spec: StrategySpec,
        binding: dict[str, Any],
        eligibility: dict[str, Any],
        interval_seconds: int = 300,
    ) -> str:
        """Persist a server-verified research promotion; never accepts browser model data.

        The research promotion service owns scientific eligibility and authorization.
        This boundary freezes its exact proof and validates the data-only model binding.
        Repeating a proposal returns its existing monitor, including terminal deployments.
        """
        from entropytrade.research.paper_models import verify_research_binding
        from entropytrade.research.store import reject_collector_chain
        from entropytrade.strategies.interpret import compile_strategy

        reject_collector_chain(self.jobs.root)
        self._latch_sentinel()
        job_id = identifier(research_job_id)
        if HASH.fullmatch(experiment_id) is None or not hypothesis_id:
            raise ValueError("research paper deployment requires immutable experiment references")
        if type(interval_seconds) is not int or not 60 <= interval_seconds <= 3600:
            raise ValueError("poll interval must be 60-3600 seconds")
        if (
            eligibility.get("schema") != "research-paper-eligibility-v1"
            or eligibility.get("eligible") is not True
            or not isinstance(eligibility.get("proposal_hash"), str)
            or HASH.fullmatch(eligibility["proposal_hash"]) is None
        ):
            raise ValueError("a verified eligible research paper proposal is required")
        verify_research_binding(spec, binding, data_kind=eligibility.get("data_kind", "real"))
        if binding.get("experiment_id") != experiment_id:
            raise ValueError("model binding differs from the proposed research experiment")
        compile_strategy(spec)
        if spec.exit_mode != "hold_to_settlement":
            raise ValueError("paper deployments currently require hold-to-settlement exits")
        source = {
            "schema": SOURCE_SCHEMA,
            "research_job_id": job_id,
            "experiment_id": experiment_id,
            "hypothesis_id": hypothesis_id,
            "spec_hash": spec.spec_hash(),
            "binding_hash": binding["binding_hash"],
            "eligibility": eligibility,
        }
        source["source_hash"] = scientific_hash(source)
        deployment_key = research_deployment_key(source)
        encoded_source = json.dumps(source, sort_keys=True, allow_nan=False)
        encoded_binding = json.dumps(binding, sort_keys=True, allow_nan=False)
        monitor_id, now = str(uuid4()), timestamp()
        next_at = _research_next(
            {"spec": spec.model_dump_json(), "model_binding": encoded_binding}, now
        )
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, now)
            existing = db.execute(
                "SELECT * FROM monitors WHERE deployment_key=?", (deployment_key,)
            ).fetchone()
            if existing is not None:
                validate_research_source(dict(existing))
                return str(existing["id"])
            if state["halted"]:
                db.commit()
                raise ValueError("workspace is halted; new paper monitors cannot start")
            if db.execute("SELECT count(*) FROM monitors WHERE status='active'").fetchone()[0] >= 4:
                raise ValueError("four active monitors maximum; pause one first")
            if db.execute("SELECT count(*) FROM monitors").fetchone()[0] >= 100:
                raise ValueError("workspace monitor budget reached (100)")
            db.execute(
                "INSERT INTO monitors (id, job_id, candidate_id, family, spec, spec_hash, status, "
                "interval_seconds, next_at, created_at, failures, model_binding, source_kind, "
                "research_job_id, experiment_id, deployment_key, source_ref) "
                "VALUES (?, ?, ?, 'weather', ?, ?, 'active', ?, ?, ?, 0, ?, "
                "'autonomous_research', ?, ?, ?, ?)",
                (
                    monitor_id,
                    job_id,
                    hypothesis_id,
                    spec.model_dump_json(),
                    spec.spec_hash(),
                    interval_seconds,
                    next_at,
                    now,
                    encoded_binding,
                    job_id,
                    experiment_id,
                    deployment_key,
                    encoded_source,
                ),
            )
            db.execute(
                "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                (monitor_id, now, "research paper deployment created from frozen eligible proof"),
            )
        return monitor_id

    def history(self) -> list[dict[str, Any]]:
        with self.jobs.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id, job_id, candidate_id, family, spec_hash, status, interval_seconds, "
                    "next_at, failures, source_kind, research_job_id, experiment_id, "
                    "deployment_key "
                    "FROM monitors ORDER BY created_at DESC"
                )
            ]

    def running(self, monitor_id: str, cycle_id: str) -> bool:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, timestamp())
            row = db.execute(
                "SELECT m.status FROM monitors m JOIN shadow_cycles c ON c.monitor_id=m.id "
                "WHERE m.id=? AND c.id=? AND c.status='running'",
                (identifier(monitor_id), identifier(cycle_id)),
            ).fetchone()
            control = readiness.cycle_control(db, cycle_id)
            return bool(
                row
                and control["control_epoch"] == state["epoch"]
                and (
                    control["cycle_mode"] == "reconcile_only"
                    or (row[0] == "active" and not state["halted"])
                )
            )

    def get_for_cycle(self, monitor_id: str, cycle_id: str) -> dict[str, Any] | None:
        with self.jobs.connect() as db:
            control = readiness.cycle_control(db, identifier(cycle_id))
        return self.get(
            monitor_id,
            export=True,
            reconciliation_cycle_id=cycle_id if control["cycle_mode"] == "reconcile_only" else None,
        )

    def get(
        self,
        monitor_id: str,
        *,
        export: bool = False,
        reconciliation_cycle_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self.jobs.connect() as db:
            draining_read = reconciliation_cycle_id is not None
            if reconciliation_cycle_id is not None:
                db.execute("BEGIN IMMEDIATE")
                state = readiness.observe_halt(db, self.jobs.root, timestamp())
                claim = db.execute(
                    "SELECT status FROM shadow_cycles WHERE id=? AND monitor_id=?",
                    (identifier(reconciliation_cycle_id), identifier(monitor_id)),
                ).fetchone()
                control = readiness.cycle_control(db, reconciliation_cycle_id)
                if (
                    not claim
                    or claim[0] != "running"
                    or control["cycle_mode"] != "reconcile_only"
                    or control["control_epoch"] != state["epoch"]
                ):
                    raise ValueError(
                        "settlement-only read requires a current running reconciliation claim"
                    )
            row = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                return None
            monitor = dict(row)
            monitor["spec"] = json.loads(monitor["spec"])
            monitor["model_binding"] = (
                None
                if draining_read
                else (json.loads(monitor["model_binding"]) if monitor["model_binding"] else None)
            )
            if draining_read:
                if StrategySpec.model_validate(monitor["spec"]).spec_hash() != monitor["spec_hash"]:
                    raise ValueError("settlement-only immutable strategy checksum mismatch")
                monitor["source_verification"] = (
                    "model/current policy not required for settlement-only claim"
                )
            elif monitor["source_kind"] == "autonomous_research":
                monitor["source_ref"] = validate_research_source(monitor)
            elif monitor["source_kind"] != "legacy" or any(
                monitor[name] is not None
                for name in ("research_job_id", "experiment_id", "deployment_key", "source_ref")
            ):
                raise ValueError("invalid monitor origin")
            monitor["cycle_count"] = db.execute(
                "SELECT count(*) FROM shadow_cycles WHERE monitor_id=?", (monitor_id,)
            ).fetchone()[0]
            monitor["cycles"] = [
                {
                    **dict(c),
                    "cycle_mode": readiness.cycle_control(db, c["id"])["cycle_mode"],
                    "control_epoch": readiness.cycle_control(db, c["id"])["control_epoch"],
                    "control_snapshot": readiness.cycle_control(db, c["id"]),
                    "result": json.loads(c["result"]) if c["result"] else None,
                    "artifact_root": f"shadow/{monitor_id}/{c['id']}",
                }
                for c in db.execute(
                    "SELECT * FROM shadow_cycles WHERE monitor_id=? ORDER BY sequence DESC LIMIT ?",
                    (monitor_id, 1000 if export else 20),
                )
            ]
            monitor["contracts"] = [
                {
                    **dict(c),
                    "market": json.loads(c["market"]),
                    "outcome": json.loads(c["outcome"]) if c["outcome"] else None,
                }
                for c in db.execute(
                    "SELECT ticker, market, last_attempt, outcome FROM shadow_contracts "
                    "WHERE monitor_id=? ORDER BY ticker",
                    (monitor_id,),
                )
            ]
            monitor["events"] = [
                dict(e)
                for e in db.execute(
                    "SELECT at, action FROM shadow_events WHERE monitor_id=? ORDER BY sequence",
                    (monitor_id,),
                )
            ]
            account = db.execute(
                "SELECT state, digest FROM shadow_accounts WHERE monitor_id=?", (monitor_id,)
            ).fetchone()
            monitor["paper_account"] = json.loads(account[0]) if account else None
            if account and account_hash(monitor["paper_account"]) != account[1]:
                raise ValueError("paper account checksum mismatch")
            latest = db.execute(
                "SELECT json_extract(result, '$.paper.state_hash') FROM shadow_cycles "
                "WHERE monitor_id=? AND json_extract(result, '$.paper.state_hash') IS NOT NULL "
                "ORDER BY sequence DESC LIMIT 1",
                (monitor_id,),
            ).fetchone()
            if latest and latest[0] != account_hash(monitor["paper_account"]):
                raise ValueError("paper account differs from committed cycle; no bankroll reset")
            monitor["paper_summary"] = summary(monitor["paper_account"])
            if monitor["paper_account"] is not None:
                ledger = Ledger.load(monitor["paper_account"]["ledger"])
                monitor["paper_summary"].update(
                    drawdown_at_cost=str(ledger.drawdown()),
                    peak_equity_at_cost=str(ledger.peak_equity),
                )
            monitor["alerts"] = alerts.history(db, monitor_id)
        monitor["submission_enabled"] = False
        monitor["fills"] = []
        monitor["performance"] = None
        return monitor

    def control(self, monitor_id: str, action: str) -> None:
        self._latch_sentinel()
        if action not in {"pause", "resume", "suspend", "cancel"}:
            raise ValueError("unknown monitor action")
        now = timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, now)
            readiness.guard_write(db, self.jobs.root)
            row = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                raise ValueError("monitor not found")
            current = row["status"]
            if current == "cancelled":
                if action == "cancel":
                    return
                raise ValueError("cancelled paper deployments cannot be reactivated")
            if current == "suspended":
                if action == "suspend":
                    return
                if action != "cancel":
                    raise ValueError("suspended paper deployments require a new validated proposal")
            if action == "resume":
                if state["halted"]:
                    db.commit()
                    raise ValueError(
                        "workspace is halted; release does not automatically resume monitors"
                    )
                if current != "paused":
                    raise ValueError("only paused monitors can resume")
                if (
                    db.execute("SELECT count(*) FROM monitors WHERE status='active'").fetchone()[0]
                    >= 4
                ):
                    raise ValueError("four active monitors maximum")
            target = {
                "pause": "paused",
                "resume": "active",
                "suspend": "suspended",
                "cancel": "cancelled",
            }[action]
            if action == "resume" and row["source_kind"] == "autonomous_research":
                validate_research_source(dict(row))
            next_at = (
                _research_next(dict(row), now)
                if action == "resume" and row["source_kind"] == "autonomous_research"
                else now
            )
            db.execute(
                "UPDATE monitors SET status=?, next_at=?, failures=0 WHERE id=?",
                (target, next_at, monitor_id),
            )
            if action != "resume":
                readiness.invalidate_monitor(db, monitor_id, f"Monitor {target}", now)
                db.execute(
                    "UPDATE shadow_cycles SET status='interrupted', finished_at=?, "
                    "detail=? "
                    "WHERE monitor_id=? AND status='running'",
                    (now, f"{target.capitalize()} by user; partial receipts retained", monitor_id),
                )
            db.execute(
                "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                (monitor_id, now, action),
            )

    def claim(self) -> tuple[str, str] | None:
        now = timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, now)
            readiness.guard_write(db, self.jobs.root)
            row = (
                None
                if state["halted"]
                else db.execute(
                    "SELECT * FROM monitors WHERE status='active' AND next_at<=? AND NOT EXISTS "
                    "(SELECT 1 FROM shadow_cycles WHERE monitor_id=monitors.id "
                    "AND status='running') "
                    "ORDER BY next_at, id LIMIT 1",
                    (now,),
                ).fetchone()
            )
            mode = "paper"
            if row is None:
                if (
                    not state["halted"]
                    and db.execute(
                        "SELECT 1 FROM monitors WHERE status='active' "
                        "AND source_kind='autonomous_research' AND next_at<=? LIMIT 1",
                        (
                            (
                                datetime.fromisoformat(now)
                                + timedelta(seconds=RECONCILIATION_WORKER_SECONDS)
                            ).isoformat(),
                        ),
                    ).fetchone()
                ):
                    # A drain can consume the bounded worker's entire budget. Preserve
                    # its capacity for a trained decision instead of missing that minute.
                    # Legacy polling intervals do not impose that narrow decision window.
                    return None
                row = self._reconciliation_due(db, now)
                mode = "reconcile_only"
                if row is None:
                    return None
            monitor_id = str(row[0])
            if mode == "paper" and row["source_kind"] == "autonomous_research":
                from entropytrade.research.paper_models import paper_window

                try:
                    validate_research_source(dict(row))
                    binding = json.loads(row["model_binding"])
                    next_at = _research_next(dict(row), now)
                    valid_window = paper_window(binding, datetime.fromisoformat(now)) is not None
                except (ValueError, KeyError, TypeError):
                    db.execute("UPDATE monitors SET status='suspended' WHERE id=?", (monitor_id,))
                    readiness.invalidate_monitor(
                        db, monitor_id, "Frozen research proof invalid", now
                    )
                    db.execute(
                        "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                        (monitor_id, now, "suspended: frozen research scheduling proof is invalid"),
                    )
                    return None
                if not valid_window:
                    db.execute("UPDATE monitors SET next_at=? WHERE id=?", (next_at, monitor_id))
                    db.execute(
                        "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                        (monitor_id, now, "missed trained decision window; no backdated cycle"),
                    )
                    return None
            sequence = db.execute(
                "SELECT count(*)+1 FROM shadow_cycles WHERE monitor_id=?", (monitor_id,)
            ).fetchone()[0]
            if sequence > 1000:
                if mode == "reconcile_only":
                    return None
                db.execute("UPDATE monitors SET status='paused' WHERE id=?", (monitor_id,))
                db.execute(
                    "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                    (monitor_id, now, "paused: 1000-cycle workspace budget reached"),
                )
                return None
            cycle_id = str(uuid4())
            db.execute(
                "INSERT INTO shadow_cycles VALUES (?, ?, ?, 'running', ?, NULL, ?, NULL, NULL)",
                (cycle_id, monitor_id, sequence, now, "Collecting read-only evidence"),
            )
            readiness.freeze_cycle(db, cycle_id, mode)
            return monitor_id, cycle_id

    def _reconciliation_due(self, db: sqlite3.Connection, now: str) -> sqlite3.Row | None:
        """A settlement drain needs existing positions and frozen, closed contracts."""
        moment = datetime.fromisoformat(now)
        for row in db.execute(
            "SELECT m.*,a.state AS account_state,a.digest AS account_digest FROM monitors m "
            "JOIN shadow_accounts a ON a.monitor_id=m.id WHERE NOT EXISTS "
            "(SELECT 1 FROM shadow_cycles c WHERE c.monitor_id=m.id AND c.status='running') "
            "ORDER BY m.id"
        ).fetchall():
            if readiness.enabled(db):
                latest = db.execute(
                    "SELECT c.started_at FROM shadow_cycles c JOIN shadow_cycle_controls e "
                    "ON e.cycle_id=c.id WHERE c.monitor_id=? AND e.mode='reconcile_only' "
                    "ORDER BY c.sequence DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if latest and moment < datetime.fromisoformat(latest[0]) + timedelta(
                    seconds=RECONCILIATION_RETRY_SECONDS
                ):
                    continue
            account = json.loads(row["account_state"])
            if account_hash(account) != row["account_digest"]:
                raise ValueError("paper account checksum mismatch before reconciliation claim")
            positions = {
                p.contract.market_ticker
                for p in Ledger.load(account["ledger"]).positions
                if p.quantity > 0
            }
            for contract in db.execute(
                "SELECT * FROM shadow_contracts WHERE monitor_id=? AND outcome IS NULL "
                "ORDER BY ticker",
                (row["id"],),
            ):
                market = json.loads(contract["market"])["market"]
                expected, _ = alerts.settlement_expected(market)
                attempted = contract["last_attempt"]
                if (
                    contract["ticker"] in positions
                    and expected <= moment
                    and (
                        not attempted
                        or moment
                        >= datetime.fromisoformat(attempted)
                        + timedelta(seconds=RECONCILIATION_RETRY_SECONDS)
                    )
                ):
                    readiness.initialize(db, self.jobs.root, now)
                    matching: sqlite3.Row = row
                    return matching
        return None

    def finish(
        self, monitor_id: str, cycle_id: str, result: dict[str, Any], *, failed: bool = False
    ) -> bool:
        now = timestamp()
        encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = readiness.observe_halt(db, self.jobs.root, now)
            readiness.guard_write(db, self.jobs.root)
            monitor = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            cycle = db.execute(
                "SELECT status,started_at FROM shadow_cycles WHERE id=? AND monitor_id=?",
                (identifier(cycle_id), monitor_id),
            ).fetchone()
            control = readiness.cycle_control(db, cycle_id)
            draining = control["cycle_mode"] == "reconcile_only"
            if (
                not monitor
                or not cycle
                or cycle[0] != "running"
                or control["control_epoch"] != state["epoch"]
                or (not draining and (monitor["status"] != "active" or state["halted"]))
            ):
                return False
            if (
                draining
                and "paper" not in result
                and any(
                    result.get(key)
                    for key in ("contracts", "decisions", "outcomes", "outcome_attempts")
                )
            ):
                raise ValueError("a failed reconciliation cannot change economic evidence")
            if draining and "paper" not in result and not failed:
                raise ValueError("a completed reconciliation requires reproduced accounting")
            if "paper" in result:
                from entropytrade.tracking.reconciliation import is_reconciliation

                if is_reconciliation(result) != draining:
                    raise ValueError("paper result mode/schema differs from its trusted claim")
            if (
                readiness.enabled(db)
                and "paper" in result
                and any(
                    result.get(key) != expected
                    for key, expected in (
                        ("control_epoch", control["control_epoch"]),
                        ("cycle_mode", control["cycle_mode"]),
                        ("control_snapshot", control),
                    )
                )
            ):
                raise ValueError("paper result differs from its frozen cycle controls")
            research_next = None
            if not draining and monitor["source_kind"] == "autonomous_research":
                try:
                    validate_research_source(dict(monitor))
                    research_next = _research_next(dict(monitor), now)
                except (ValueError, KeyError, TypeError):
                    # Invalidated origin/model metadata cannot commit a late simulated
                    # account transition or stop the shared monitoring runner.
                    db.execute("UPDATE monitors SET status='suspended' WHERE id=?", (monitor_id,))
                    readiness.invalidate_monitor(
                        db, monitor_id, "Frozen research proof invalid", now
                    )
                    db.execute(
                        "UPDATE shadow_cycles SET status='interrupted', finished_at=?, "
                        "detail='Frozen research proof failed before account commit' WHERE id=?",
                        (now, cycle_id),
                    )
                    db.execute(
                        "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                        (
                            monitor_id,
                            now,
                            "suspended: research proof changed before account commit",
                        ),
                    )
                    return False
            if "paper" in result:
                account = db.execute(
                    "SELECT state, digest FROM shadow_accounts WHERE monitor_id=?", (monitor_id,)
                ).fetchone()
                previous = json.loads(account[0]) if account else None
                latest = db.execute(
                    "SELECT json_extract(result, '$.paper.state_hash') FROM shadow_cycles "
                    "WHERE monitor_id=? AND json_extract(result, '$.paper.state_hash') IS NOT NULL "
                    "ORDER BY sequence DESC LIMIT 1",
                    (monitor_id,),
                ).fetchone()
                if latest and latest[0] != account_hash(previous):
                    raise ValueError(
                        "paper account differs from committed cycle; no bankroll reset"
                    )
                if (account and account_hash(previous) != account[1]) or (
                    result["paper_inputs"]["before"] != previous
                    or result["paper_inputs"]["before_hash"] != account_hash(previous)
                ):
                    raise ValueError("stale/corrupt paper account; cycle cannot commit")
                if reproduce(result["paper_inputs"]) != result["paper"]:
                    raise ValueError("paper result differs from frozen inputs")
                if draining:
                    self._verify_reconciliation(
                        db, monitor_id, cycle_id, cycle["started_at"], control, previous, result
                    )
                # The sentinel can arrive while verifying a large immutable outbox.
                # Observe it again before any account write, retaining its epoch latch.
                latest_control = readiness.observe_halt(db, self.jobs.root, timestamp())
                if latest_control["epoch"] != control["control_epoch"] or (
                    not draining and latest_control["halted"]
                ):
                    return False
                state = result["paper"]["state"]
                db.execute(
                    "INSERT INTO shadow_accounts VALUES (?, ?, ?) "
                    "ON CONFLICT(monitor_id) DO UPDATE SET state=excluded.state, "
                    "digest=excluded.digest",
                    (monitor_id, json.dumps(state, sort_keys=True), account_hash(state)),
                )
            for contract in result.get("contracts", []):
                db.execute(
                    "INSERT OR IGNORE INTO shadow_contracts VALUES (?, ?, ?, '', NULL)",
                    (monitor_id, contract["ticker"], json.dumps(contract)),
                )
            for attempt in result.get("outcome_attempts", []):
                db.execute(
                    "UPDATE shadow_contracts SET last_attempt=? WHERE monitor_id=? AND ticker=?",
                    (attempt["at"], monitor_id, attempt["ticker"]),
                )
            for outcome in result.get("outcomes", []):
                db.execute(
                    "UPDATE shadow_contracts SET outcome=? WHERE monitor_id=? "
                    "AND ticker=? AND outcome IS NULL",
                    (json.dumps(outcome), monitor_id, outcome["ticker"]),
                )
            failures = monitor["failures"] + 1 if failed else 0
            delay = min(3600, monitor["interval_seconds"] * 2 ** min(failures, 4))
            next_at = (
                research_next
                if research_next is not None
                else (datetime.fromisoformat(now) + timedelta(seconds=delay)).isoformat()
            )
            if not draining:
                db.execute(
                    "UPDATE monitors SET next_at=?, failures=?, status=? WHERE id=?",
                    (next_at, failures, "paused" if failures >= 5 else "active", monitor_id),
                )
            db.execute(
                "UPDATE shadow_cycles SET status=?, finished_at=?, detail=?, result=?, digest=? "
                "WHERE id=?",
                (
                    "failed" if failed else "completed",
                    now,
                    result["detail"],
                    encoded,
                    scientific_hash(result),
                    cycle_id,
                ),
            )
            if failures >= 5 and not draining:
                readiness.invalidate_monitor(db, monitor_id, "Repeated worker failures", now)
                db.execute(
                    "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                    (monitor_id, now, "paused after five consecutive acquisition/worker failures"),
                )
            alerts.refresh(db, now)
            return True

    def _verify_reconciliation(
        self,
        db: sqlite3.Connection,
        monitor_id: str,
        cycle_id: str,
        started_at: str,
        control: dict[str, Any],
        previous: dict[str, Any] | None,
        result: dict[str, Any],
    ) -> None:
        if result.get("cycle_id") != cycle_id:
            raise ValueError("reconciliation result differs from its claimed cycle identity")
        if previous is None or result.get("contracts") or result.get("decisions"):
            raise ValueError("reconciliation cannot create positions, contracts or decisions")
        after = result["paper"]["state"]
        if any(after["ledger"][key] != previous["ledger"][key] for key in ("orders", "fills")):
            raise ValueError("reconciliation cannot introduce orders or fills")
        # Shared artifact/source verifier is supplied by the settlement worker module.
        from entropytrade.tracking.reconciliation import verify_reconciliation

        contracts = [
            {
                **dict(row),
                "market": json.loads(row["market"]),
                "outcome": json.loads(row["outcome"]) if row["outcome"] else None,
            }
            for row in db.execute(
                "SELECT ticker,market,last_attempt,outcome FROM shadow_contracts "
                "WHERE monitor_id=? ORDER BY ticker",
                (monitor_id,),
            )
        ]
        verify_reconciliation(
            self.jobs.root / "shadow" / monitor_id / cycle_id,
            result,
            expected_before=previous,
            expected_control={
                "control_epoch": control["control_epoch"],
                "cycle_mode": "reconcile_only",
                "control_snapshot": control,
                "started_at": started_at,
            },
            expected_contracts=contracts,
        )

    def recover(self) -> None:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            interrupted = db.execute(
                "SELECT DISTINCT monitor_id FROM shadow_cycles WHERE status='running'"
            ).fetchall()
            now = timestamp()
            readiness.observe_halt(db, self.jobs.root, now)
            readiness.guard_write(db, self.jobs.root)
            db.execute(
                "UPDATE shadow_cycles SET status='interrupted', finished_at=?, "
                "detail='Server stopped; partial receipts retained; fresh cycle will resume' "
                "WHERE status='running'",
                (now,),
            )
            for row in interrupted:
                db.execute(
                    "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                    (row[0], now, "interrupted worker recovered; next poll uses fresh receipts"),
                )
            for monitor in db.execute(
                "SELECT * FROM monitors WHERE source_kind='autonomous_research' AND status='active'"
            ).fetchall():
                try:
                    validate_research_source(dict(monitor))
                    next_at = _research_next(dict(monitor), now)
                except (ValueError, KeyError, TypeError):
                    readiness.invalidate_monitor(
                        db, monitor["id"], "Frozen research proof invalid", now
                    )
                    db.execute(
                        "UPDATE monitors SET status='suspended' WHERE id=?", (monitor["id"],)
                    )
                    db.execute(
                        "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                        (
                            monitor["id"],
                            now,
                            "suspended: frozen research schedule failed restart verification",
                        ),
                    )
                else:
                    db.execute("UPDATE monitors SET next_at=? WHERE id=?", (next_at, monitor["id"]))
            alerts.refresh(db, now)
