"""Durable, bounded local jobs. This control plane needs only the standard library."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted"})


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def identifier(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("invalid job ID")
    return value


def validate_request(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"idea", "family", "mode"}:
        raise ValueError("provide only idea, family and mode")
    if any(not isinstance(v, str) for v in value.values()):
        raise ValueError("request values must be strings")
    idea, family, mode = value["idea"].strip(), value["family"], value["mode"]
    if not 1 <= len(idea) <= 6000:
        raise ValueError("idea must contain 1-6000 characters")
    if family not in {"weather", "bitcoin"} or mode not in {"recorded", "public", "synthetic"}:
        raise ValueError("unknown family or data mode")
    if family == "bitcoin" and mode != "public":
        raise ValueError("Bitcoin currently supports public forward capture only")
    return {"idea": idea, "family": family, "mode": mode}


class Jobs:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "jobs.sqlite"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    detail TEXT NOT NULL, result TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY, job_id TEXT NOT NULL,
                    at TEXT NOT NULL, stage TEXT NOT NULL, detail TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, request: object) -> str:
        clean = validate_request(request)
        job_id, now = str(uuid4()), timestamp()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchone()[0]
            if count >= 8:
                raise ValueError("local queue is full (eight jobs)")
            db.execute(
                "INSERT INTO jobs VALUES (?, ?, 'queued', ?, ?, 'Waiting for worker', NULL)",
                (job_id, json.dumps(clean), now, now),
            )
            db.execute(
                "INSERT INTO events(job_id, at, stage, detail) VALUES (?, ?, 'queued', ?)",
                (
                    job_id,
                    now,
                    "Request saved; local templates or explicit synthetic mock reasoning",
                ),
            )
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier(job_id),)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["request"] = json.loads(result["request"])
            result["result"] = json.loads(result["result"]) if result["result"] else None
            result["events"] = [
                dict(e)
                for e in db.execute(
                    "SELECT sequence, at, stage, detail FROM events WHERE job_id=? "
                    "ORDER BY sequence",
                    (job_id,),
                )
            ]
            return result

    def history(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [
                {**dict(r), "request": json.loads(r["request"])}
                for r in db.execute(
                    "SELECT id, request, status, created_at, updated_at, detail FROM jobs "
                    "ORDER BY created_at DESC LIMIT 50"
                )
            ]

    def queued(self) -> str | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            return str(row[0]) if row else None

    def update(
        self,
        job_id: str,
        stage: str,
        detail: str,
        *,
        status: str = "running",
        result: dict[str, Any] | None = None,
    ) -> bool:
        if status not in {"running", *TERMINAL}:
            raise ValueError("invalid job status")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE id=?", (identifier(job_id),)).fetchone()
            if row is None or row[0] in TERMINAL:
                return False
            now = timestamp()
            db.execute(
                "UPDATE jobs SET status=?, detail=?, updated_at=?, result=? WHERE id=?",
                (
                    status,
                    detail,
                    now,
                    json.dumps(result, allow_nan=False) if result else None,
                    job_id,
                ),
            )
            db.execute(
                "INSERT INTO events(job_id, at, stage, detail) VALUES (?, ?, ?, ?)",
                (job_id, now, stage, detail),
            )
            return True

    def recover(self) -> None:
        with self.connect() as db:
            ids = [
                r[0]
                for r in db.execute("SELECT id FROM jobs WHERE status IN ('queued', 'running')")
            ]
        for job_id in ids:
            self.update(
                job_id,
                "interrupted",
                "Server stopped; submit a new run to retry",
                status="interrupted",
            )
