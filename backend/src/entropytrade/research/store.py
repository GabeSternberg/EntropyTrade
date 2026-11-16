"""Durable research-job state. Every step writes an inspectable row before moving on.

The store enforces the job state machine and the hypothesis statuses this service may set.
It never stores credentials; provider choice is a public name only.
"""

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from entropytrade.research.model import (
    RESEARCH_SETTABLE,
    RUNNABLE,
    TERMINAL,
    Assessment,
    DataRequirement,
    HypothesisSpec,
    HypothesisStatus,
    JobStatus,
    ResearchRequest,
    check_transition,
)
from entropytrade.research.registry import Resolution

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY, request TEXT NOT NULL, fingerprint TEXT NOT NULL,
    family TEXT NOT NULL, universe TEXT NOT NULL, status TEXT NOT NULL,
    detail TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    next_run_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    checkpoint TEXT NOT NULL DEFAULT '{}', usage TEXT NOT NULL, error TEXT);
CREATE INDEX IF NOT EXISTS research_jobs_status ON research_jobs(status, next_run_at);
CREATE TABLE IF NOT EXISTS research_events (
    sequence INTEGER PRIMARY KEY, job_id TEXT NOT NULL, at TEXT NOT NULL,
    stage TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_hypotheses (
    job_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL, version INTEGER NOT NULL,
    rank INTEGER NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL,
    reasons TEXT NOT NULL, facets TEXT NOT NULL, search_note TEXT NOT NULL,
    updated_at TEXT NOT NULL, PRIMARY KEY(job_id, hypothesis_id, version));
CREATE TABLE IF NOT EXISTS research_signatures (
    signature TEXT PRIMARY KEY, first_job_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL,
    first_seen TEXT NOT NULL, searches INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS research_requirements (
    job_id TEXT NOT NULL, requirement_id TEXT NOT NULL, spec TEXT NOT NULL,
    assessment TEXT, PRIMARY KEY(job_id, requirement_id));
CREATE TABLE IF NOT EXISTS research_resolutions (
    job_id TEXT NOT NULL, hypothesis_id TEXT NOT NULL, requested TEXT NOT NULL,
    resolution TEXT NOT NULL, PRIMARY KEY(job_id, hypothesis_id, requested));
"""

_ZERO_USAGE = {
    "ai_usd": "0",
    "ai_requests": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "http_requests": 0,
    "bytes": 0,
    "runtime_seconds": 0.0,
}


def job_identifier(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("invalid research job ID")
    return value


class ResearchStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError("research workspace paths cannot traverse symlinks")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "research.sqlite"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    # ------------------------------------------------------------------ jobs
    def create_job(
        self,
        request: ResearchRequest,
        *,
        universe: tuple[str, ...],
        now: datetime,
        limit: int = 12,
    ) -> tuple[str, bool]:
        """Idempotent: an equivalent unfinished request returns the existing job."""
        fingerprint = request.fingerprint()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT id FROM research_jobs WHERE fingerprint=? AND status NOT IN (?, ?) "
                "ORDER BY created_at DESC LIMIT 1",
                (fingerprint, JobStatus.FAILED.value, JobStatus.CANCELLED.value),
            ).fetchone()
            if existing:
                return str(existing["id"]), False
            active = db.execute(
                # Only fixed "?" placeholders are interpolated; values stay parameterized.
                "SELECT count(*) FROM research_jobs WHERE status IN ({})".format(  # noqa: S608
                    ",".join("?" * len(RUNNABLE))
                ),
                tuple(s.value for s in RUNNABLE),
            ).fetchone()[0]
            if active >= limit:
                raise ValueError("research queue is full; wait for active jobs to finish")
            job_id = str(uuid4())
            stamp = now.isoformat()
            db.execute(
                "INSERT INTO research_jobs(id, request, fingerprint, family, universe, status, "
                "detail, created_at, updated_at, next_run_at, usage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    request.model_dump_json(),
                    fingerprint,
                    request.family,
                    json.dumps(list(universe)),
                    JobStatus.QUEUED.value,
                    "Research request saved",
                    stamp,
                    stamp,
                    stamp,
                    json.dumps(_ZERO_USAGE),
                ),
            )
            db.execute(
                "INSERT INTO research_events(job_id, at, stage, detail) VALUES (?, ?, ?, ?)",
                (job_id, stamp, "queued", "Research request saved; no order path exists"),
            )
        return job_id, True

    @staticmethod
    def _job(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["request"] = json.loads(value["request"])
        value["universe"] = json.loads(value["universe"])
        value["checkpoint"] = json.loads(value["checkpoint"])
        value["usage"] = json.loads(value["usage"])
        value["error"] = json.loads(value["error"]) if value["error"] else None
        return value

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM research_jobs WHERE id=?", (job_identifier(job_id),)
            ).fetchone()
            return self._job(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM research_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            jobs = [self._job(r) for r in rows]
            for job in jobs:
                counts = db.execute(
                    "SELECT status, count(*) FROM research_hypotheses h WHERE job_id=? AND "
                    "version=(SELECT max(version) FROM research_hypotheses g WHERE "
                    "g.job_id=h.job_id AND g.hypothesis_id=h.hypothesis_id) GROUP BY status",
                    (job["id"],),
                ).fetchall()
                job["hypothesis_counts"] = {str(r[0]): int(r[1]) for r in counts}
            return jobs

    def runnable(self, now: datetime) -> str | None:
        waiting = (JobStatus.AWAITING_OBSERVATIONS.value,)
        with self.connect() as db:
            row = db.execute(
                # Only fixed "?" placeholders are interpolated; values stay parameterized.
                "SELECT id FROM research_jobs WHERE next_run_at <= ? AND (status IN ({}) OR "  # noqa: S608
                "status IN ({})) ORDER BY next_run_at, created_at LIMIT 1".format(
                    ",".join("?" * len(RUNNABLE)), ",".join("?" * len(waiting))
                ),
                (now.isoformat(), *(s.value for s in RUNNABLE), *waiting),
            ).fetchone()
            return str(row[0]) if row else None

    def transition(
        self,
        job_id: str,
        target: JobStatus,
        detail: str,
        *,
        now: datetime,
        next_run_at: datetime | None = None,
        checkpoint: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        expect: JobStatus | None = None,
    ) -> bool:
        """Apply a legal transition. Returns False if the job is terminal or was changed."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM research_jobs WHERE id=?", (job_identifier(job_id),)
            ).fetchone()
            if row is None:
                raise KeyError("research job not found")
            current = JobStatus(row[0])
            if current in TERMINAL or (expect is not None and current is not expect):
                return False
            if current is not target:
                check_transition(current, target)
            stamp = now.isoformat()
            db.execute(
                "UPDATE research_jobs SET status=?, detail=?, updated_at=?, next_run_at=?, "
                "checkpoint=COALESCE(?, checkpoint), error=? WHERE id=?",
                (
                    target.value,
                    detail,
                    stamp,
                    (next_run_at or now).isoformat(),
                    json.dumps(checkpoint) if checkpoint is not None else None,
                    json.dumps(error) if error else None,
                    job_id,
                ),
            )
            db.execute(
                "INSERT INTO research_events(job_id, at, stage, detail) VALUES (?, ?, ?, ?)",
                (job_id, stamp, target.value, detail),
            )
            return True

    def event(self, job_id: str, stage: str, detail: str, *, now: datetime) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO research_events(job_id, at, stage, detail) VALUES (?, ?, ?, ?)",
                (job_identifier(job_id), now.isoformat(), stage, detail[:2000]),
            )

    def events(self, job_id: str, limit: int = 400) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT sequence, at, stage, detail FROM research_events WHERE job_id=? "
                    "ORDER BY sequence DESC LIMIT ?",
                    (job_identifier(job_id), limit),
                )
            ][::-1]

    def add_usage(self, job_id: str, **deltas: int | float | Decimal) -> dict[str, Any]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT usage FROM research_jobs WHERE id=?", (job_identifier(job_id),)
            ).fetchone()
            usage: dict[str, Any] = {**_ZERO_USAGE, **json.loads(row[0])}
            for name, value in deltas.items():
                if name not in _ZERO_USAGE:
                    raise KeyError("unknown usage counter")
                if name == "ai_usd":
                    usage[name] = str(Decimal(usage[name]) + Decimal(value))
                else:
                    usage[name] = usage[name] + value
            db.execute("UPDATE research_jobs SET usage=? WHERE id=?", (json.dumps(usage), job_id))
            return usage

    def set_attempts(self, job_id: str, attempts: int) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE research_jobs SET attempts=? WHERE id=?", (attempts, job_identifier(job_id))
            )

    # ------------------------------------------------------------ hypotheses
    def prior_signatures(self) -> dict[str, str]:
        with self.connect() as db:
            return {
                str(r[0]): str(r[1])
                for r in db.execute("SELECT signature, first_job_id FROM research_signatures")
            }

    def search_count(self, signature: str) -> int:
        with self.connect() as db:
            row = db.execute(
                "SELECT searches FROM research_signatures WHERE signature=?", (signature,)
            ).fetchone()
            return int(row[0]) if row else 0

    def save_hypotheses(
        self,
        job_id: str,
        items: list[tuple[HypothesisSpec, HypothesisStatus, tuple[str, ...], str]],
        *,
        now: datetime,
    ) -> None:
        """Insert version 1 rows idempotently and record the global search history."""
        stamp = now.isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM research_hypotheses WHERE job_id=? LIMIT 1", (job_id,)
            ).fetchone():
                return
            for rank, (spec, status, reasons, note) in enumerate(items):
                if status not in RESEARCH_SETTABLE:
                    raise ValueError("research cannot set a validation or deployment status")
                db.execute(
                    "INSERT INTO research_hypotheses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id,
                        spec.hypothesis_id,
                        spec.version,
                        rank,
                        spec.model_dump_json(),
                        status.value,
                        json.dumps(list(reasons)),
                        "{}",
                        note,
                        stamp,
                    ),
                )
                if status is HypothesisStatus.DUPLICATE:
                    continue
                db.execute(
                    "INSERT INTO research_signatures VALUES (?, ?, ?, ?, 1) "
                    "ON CONFLICT(signature) DO UPDATE SET searches=searches+1",
                    (spec.signature, job_id, spec.hypothesis_id, stamp),
                )

    def hypotheses(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM research_hypotheses h WHERE job_id=? AND version=("
                "SELECT max(version) FROM research_hypotheses g WHERE g.job_id=h.job_id "
                "AND g.hypothesis_id=h.hypothesis_id) ORDER BY rank",
                (job_identifier(job_id),),
            ).fetchall()
            result = []
            for row in rows:
                value = dict(row)
                value["spec"] = json.loads(value["spec"])
                value["reasons"] = json.loads(value["reasons"])
                value["facets"] = json.loads(value["facets"])
                value["searches"] = int(
                    (
                        db.execute(
                            "SELECT searches FROM research_signatures WHERE signature=?",
                            (value["spec"]["signature"],),
                        ).fetchone()
                        or (0,)
                    )[0]
                )
                result.append(value)
            return result

    def set_hypothesis_status(
        self,
        job_id: str,
        hypothesis_id: str,
        status: HypothesisStatus,
        reasons: list[str],
        facets: dict[str, Any],
        *,
        now: datetime,
    ) -> None:
        if status not in RESEARCH_SETTABLE:
            raise ValueError("research cannot set a validation or deployment status")
        with self.connect() as db:
            db.execute(
                "UPDATE research_hypotheses SET status=?, reasons=?, facets=?, updated_at=? "
                "WHERE job_id=? AND hypothesis_id=? AND version=(SELECT max(version) FROM "
                "research_hypotheses WHERE job_id=? AND hypothesis_id=?)",
                (
                    status.value,
                    json.dumps(reasons),
                    json.dumps(facets),
                    now.isoformat(),
                    job_id,
                    hypothesis_id,
                    job_id,
                    hypothesis_id,
                ),
            )

    # ---------------------------------------------------------- requirements
    def save_requirements(
        self,
        job_id: str,
        requirements: list[DataRequirement],
        resolutions: dict[str, list[Resolution]],
    ) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for item in requirements:
                db.execute(
                    "INSERT INTO research_requirements(job_id, requirement_id, spec) "
                    "VALUES (?, ?, ?) ON CONFLICT(job_id, requirement_id) "
                    "DO UPDATE SET spec=excluded.spec",
                    (job_id, item.requirement_id, item.model_dump_json()),
                )
            for hypothesis_id, items in resolutions.items():
                for resolution in items:
                    db.execute(
                        "INSERT OR REPLACE INTO research_resolutions VALUES (?, ?, ?, ?)",
                        (job_id, hypothesis_id, resolution.requested, resolution.model_dump_json()),
                    )

    def requirements(self, job_id: str) -> list[DataRequirement]:
        with self.connect() as db:
            return [
                DataRequirement.model_validate_json(r[0])
                for r in db.execute(
                    "SELECT spec FROM research_requirements WHERE job_id=? ORDER BY rowid",
                    (job_identifier(job_id),),
                )
            ]

    def resolutions(self, job_id: str) -> dict[str, list[Resolution]]:
        result: dict[str, list[Resolution]] = {}
        with self.connect() as db:
            for row in db.execute(
                "SELECT hypothesis_id, resolution FROM research_resolutions WHERE job_id=? "
                "ORDER BY rowid",
                (job_identifier(job_id),),
            ):
                result.setdefault(str(row[0]), []).append(Resolution.model_validate_json(row[1]))
        return result

    def save_assessments(self, job_id: str, assessments: list[Assessment]) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for item in assessments:
                db.execute(
                    "UPDATE research_requirements SET assessment=? WHERE job_id=? "
                    "AND requirement_id=?",
                    (item.model_dump_json(), job_id, item.requirement_id),
                )

    def assessments(self, job_id: str) -> dict[str, Assessment]:
        with self.connect() as db:
            return {
                str(r[0]): Assessment.model_validate_json(r[1])
                for r in db.execute(
                    "SELECT requirement_id, assessment FROM research_requirements "
                    "WHERE job_id=? AND assessment IS NOT NULL",
                    (job_identifier(job_id),),
                )
            }
