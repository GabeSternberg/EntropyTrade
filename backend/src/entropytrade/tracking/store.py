"""Transactional monitor controls, append-only cycles and frozen contract evidence."""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from entropytrade.api.jobs import Jobs, identifier, timestamp
from entropytrade.features.registry import scientific_hash


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
            """)

    def create(self, value: object) -> str:
        from entropytrade.domain.strategy import StrategySpec
        from entropytrade.strategies.interpret import compile_strategy

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
        if job["result"]["data_kind"] != "real":
            raise ValueError("synthetic candidates cannot monitor real markets")
        proposals = job["result"].get("proposals", [])
        proposal = next((p for p in proposals if p["candidate_id"] == value["candidate_id"]), None)
        if not proposal or not proposal.get("spec"):
            raise ValueError("select a typed candidate specification")
        spec = StrategySpec.model_validate(proposal["spec"])
        compile_strategy(spec)
        if spec.exit_mode != "hold_to_settlement":
            raise ValueError("shadow reservations currently require hold-to-settlement exits")
        monitor_id, now = str(uuid4()), timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM monitors WHERE status='active'").fetchone()[0] >= 4:
                raise ValueError("four active monitors maximum; pause one first")
            if db.execute("SELECT count(*) FROM monitors").fetchone()[0] >= 100:
                raise ValueError("workspace monitor budget reached (100)")
            db.execute(
                "INSERT INTO monitors VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, 0)",
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
                ),
            )
            db.execute(
                "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                (monitor_id, now, "created; shadow only, no validation approval implied"),
            )
        return monitor_id

    def history(self) -> list[dict[str, Any]]:
        with self.jobs.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id, job_id, candidate_id, family, spec_hash, status, interval_seconds, "
                    "next_at, failures FROM monitors ORDER BY created_at DESC"
                )
            ]

    def running(self, monitor_id: str, cycle_id: str) -> bool:
        with self.jobs.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM monitors m JOIN shadow_cycles c ON c.monitor_id=m.id "
                    "WHERE m.id=? AND c.id=? AND m.status='active' AND c.status='running'",
                    (identifier(monitor_id), identifier(cycle_id)),
                ).fetchone()
                is not None
            )

    def get(self, monitor_id: str, *, export: bool = False) -> dict[str, Any] | None:
        with self.jobs.connect() as db:
            row = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                return None
            monitor = dict(row)
            monitor["spec"] = json.loads(monitor["spec"])
            monitor["cycle_count"] = db.execute(
                "SELECT count(*) FROM shadow_cycles WHERE monitor_id=?", (monitor_id,)
            ).fetchone()[0]
            monitor["cycles"] = [
                {
                    **dict(c),
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
        monitor["submission_enabled"] = False
        monitor["fills"] = []
        monitor["performance"] = None
        return monitor

    def control(self, monitor_id: str, action: str) -> None:
        if action not in {"pause", "resume"}:
            raise ValueError("unknown monitor action")
        now = timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                raise ValueError("monitor not found")
            if action == "resume":
                if row[0] != "paused":
                    raise ValueError("only paused monitors can resume")
                if (
                    db.execute("SELECT count(*) FROM monitors WHERE status='active'").fetchone()[0]
                    >= 4
                ):
                    raise ValueError("four active monitors maximum")
            db.execute(
                "UPDATE monitors SET status=?, next_at=?, failures=0 WHERE id=?",
                ("paused" if action == "pause" else "active", now, monitor_id),
            )
            if action == "pause":
                db.execute(
                    "UPDATE shadow_cycles SET status='interrupted', finished_at=?, "
                    "detail='Paused by user; partial receipts retained' "
                    "WHERE monitor_id=? AND status='running'",
                    (now, monitor_id),
                )
            db.execute(
                "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                (monitor_id, now, action),
            )

    def claim(self) -> tuple[str, str] | None:
        now = timestamp()
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM monitors WHERE status='active' AND next_at<=? AND NOT EXISTS "
                "(SELECT 1 FROM shadow_cycles WHERE monitor_id=monitors.id AND status='running') "
                "ORDER BY next_at, id LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                return None
            monitor_id = str(row[0])
            sequence = db.execute(
                "SELECT count(*)+1 FROM shadow_cycles WHERE monitor_id=?", (monitor_id,)
            ).fetchone()[0]
            if sequence > 1000:
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
            return monitor_id, cycle_id

    def finish(
        self, monitor_id: str, cycle_id: str, result: dict[str, Any], *, failed: bool = False
    ) -> bool:
        now = timestamp()
        encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            monitor = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            cycle = db.execute(
                "SELECT status FROM shadow_cycles WHERE id=? AND monitor_id=?",
                (identifier(cycle_id), monitor_id),
            ).fetchone()
            if not monitor or monitor["status"] != "active" or not cycle or cycle[0] != "running":
                return False
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
            next_at = (datetime.fromisoformat(now) + timedelta(seconds=delay)).isoformat()
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
            if failures >= 5:
                db.execute(
                    "INSERT INTO shadow_events(monitor_id, at, action) VALUES (?, ?, ?)",
                    (monitor_id, now, "paused after five consecutive acquisition/worker failures"),
                )
            return True

    def recover(self) -> None:
        with self.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            interrupted = db.execute(
                "SELECT DISTINCT monitor_id FROM shadow_cycles WHERE status='running'"
            ).fetchall()
            now = timestamp()
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
