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
from entropytrade.research.sources import SourceDecision

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
CREATE TABLE IF NOT EXISTS research_sources (
    job_id TEXT NOT NULL, requirement_id TEXT NOT NULL, source_id TEXT NOT NULL,
    decision TEXT NOT NULL, PRIMARY KEY(job_id, requirement_id, source_id));
CREATE TABLE IF NOT EXISTS research_acquisitions (
    id TEXT PRIMARY KEY, acquisition_key TEXT NOT NULL UNIQUE, source_id TEXT NOT NULL,
    params TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    requests INTEGER NOT NULL DEFAULT 0, bytes INTEGER NOT NULL DEFAULT 0,
    dataset_id TEXT, detail TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_acquisition_links (
    job_id TEXT NOT NULL, acquisition_id TEXT NOT NULL, requirement_id TEXT NOT NULL,
    approval TEXT NOT NULL, PRIMARY KEY(job_id, acquisition_id, requirement_id));
CREATE TABLE IF NOT EXISTS research_forward (
    id TEXT PRIMARY KEY, coverage_key TEXT NOT NULL UNIQUE, spec TEXT NOT NULL,
    source_id TEXT NOT NULL, collector TEXT NOT NULL, collector_status TEXT NOT NULL,
    events_required INTEGER NOT NULL, events_observed INTEGER NOT NULL, status TEXT NOT NULL,
    detail TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    next_check_at TEXT NOT NULL, estimated_ready_at TEXT);
CREATE TABLE IF NOT EXISTS research_forward_links (
    job_id TEXT NOT NULL, forward_id TEXT NOT NULL, requirement_id TEXT NOT NULL,
    PRIMARY KEY(job_id, forward_id, requirement_id));
CREATE TABLE IF NOT EXISTS research_features (
    artifact_id TEXT PRIMARY KEY, feature_id TEXT NOT NULL, version TEXT NOT NULL,
    definition_hash TEXT NOT NULL, entity TEXT NOT NULL, manifest TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_feature_links (
    job_id TEXT NOT NULL, artifact_id TEXT NOT NULL, hypothesis_ids TEXT NOT NULL,
    PRIMARY KEY(job_id, artifact_id));
CREATE TABLE IF NOT EXISTS research_experiments (
    job_id TEXT NOT NULL, id TEXT NOT NULL, hypothesis_id TEXT NOT NULL,
    status TEXT NOT NULL, config TEXT NOT NULL, result TEXT, error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    PRIMARY KEY(job_id, id));
CREATE TABLE IF NOT EXISTS research_validation_boundaries (
    scope TEXT PRIMARY KEY, boundaries TEXT NOT NULL, created_at TEXT NOT NULL);
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


def reject_collector_chain(root: Path) -> None:
    """Refuse research writes anywhere inside a canonical collector store, before mkdir."""
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("research workspace paths cannot traverse symlinks")
    for path in (root, *root.parents):
        if (
            path.name in {"chain", ".chain"}
            or (path / ".chain").exists()
            or ((path / "HEAD").is_file() and (path / "links").is_dir())
        ):
            raise ValueError("research cannot write inside a canonical collector chain")


class ResearchStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        reject_collector_chain(root)
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
            if target in TERMINAL:
                db.execute(
                    "UPDATE research_experiments SET status='cancelled', updated_at=? "
                    "WHERE job_id=? AND status IN ('queued', 'running')",
                    (stamp, job_id),
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

    # ------------------------------------------------------ C: experiments
    def freeze_boundaries(self, scope: str, boundaries: list[str], *, now: datetime) -> list[str]:
        """Shared market-family outcome protection survives new jobs and changing features."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if boundaries:
                if len(boundaries) != 3 or not boundaries[0] < boundaries[1] < boundaries[2]:
                    raise ValueError("three ordered validation boundaries required")
                db.execute(
                    "INSERT OR IGNORE INTO research_validation_boundaries VALUES (?, ?, ?)",
                    (scope, json.dumps(boundaries), now.isoformat()),
                )
            row = db.execute(
                "SELECT boundaries FROM research_validation_boundaries WHERE scope=?", (scope,)
            ).fetchone()
            return list(json.loads(row[0])) if row else []

    def plan_experiment(
        self,
        job_id: str,
        experiment_id: str,
        hypothesis_id: str,
        config: dict[str, Any],
        *,
        now: datetime,
    ) -> None:
        """Persist the frozen input identity before any fitting; repeats reuse this row."""
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO research_experiments "
                "(job_id, id, hypothesis_id, status, config, created_at, updated_at) "
                "SELECT ?, ?, ?, 'queued', ?, ?, ? WHERE EXISTS "
                "(SELECT 1 FROM research_jobs WHERE id=? AND status=?)",
                (
                    job_identifier(job_id),
                    experiment_id,
                    hypothesis_id,
                    json.dumps(config, sort_keys=True),
                    now.isoformat(),
                    now.isoformat(),
                    job_id,
                    JobStatus.MODELING.value,
                ),
            )

    def experiments(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM research_experiments WHERE job_id=? ORDER BY created_at, rowid",
                (job_identifier(job_id),),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            for field in ("config", "result", "error"):
                value[field] = json.loads(value[field]) if value[field] else None
            result.append(value)
        return result

    def start_experiment(self, job_id: str, experiment_id: str, *, now: datetime) -> bool:
        """A cancelled job cannot start work even if selected before cancellation."""
        with self.connect() as db:
            changed = db.execute(
                "UPDATE research_experiments SET status='running', attempts=attempts+1, "
                "updated_at=?, error=NULL WHERE job_id=? AND id=? "
                "AND status IN ('queued', 'failed') AND EXISTS "
                "(SELECT 1 FROM research_jobs WHERE id=? AND status=?)",
                (
                    now.isoformat(),
                    job_identifier(job_id),
                    experiment_id,
                    job_id,
                    JobStatus.MODELING.value,
                ),
            )
            return changed.rowcount == 1

    def finish_experiment(
        self,
        job_id: str,
        experiment_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        now: datetime,
    ) -> bool:
        if status not in {"completed", "refused", "failed", "cancelled"}:
            raise ValueError("invalid experiment completion status")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE research_experiments SET status=?, result=?, error=?, updated_at=? "
                "WHERE job_id=? AND id=? AND status='running' AND EXISTS "
                "(SELECT 1 FROM research_jobs WHERE id=? AND status=?)",
                (
                    status,
                    json.dumps(result, sort_keys=True) if result is not None else None,
                    json.dumps(error) if error else None,
                    now.isoformat(),
                    job_identifier(job_id),
                    experiment_id,
                    job_id,
                    JobStatus.MODELING.value,
                ),
            )
            return changed.rowcount == 1

    def recover_experiments(self, *, now: datetime) -> int:
        with self.connect() as db:
            changed = db.execute(
                "UPDATE research_experiments SET status='queued', updated_at=? "
                "WHERE status='running' AND job_id IN "
                "(SELECT id FROM research_jobs WHERE status IN (?, ?))",
                (now.isoformat(), JobStatus.MODELING.value, JobStatus.RECOVERABLE_ERROR.value),
            )
            return changed.rowcount

    def invalidate_experiment(self, job_id: str, experiment_id: str, *, now: datetime) -> None:
        """Keep the historical report but revoke its status if frozen files fail verification."""
        with self.connect() as db:
            db.execute(
                "UPDATE research_experiments SET status='failed', error=?, updated_at=? "
                "WHERE job_id=? AND id=? AND status IN ('completed', 'refused')",
                (
                    json.dumps(
                        {
                            "type": "ArtifactIntegrityError",
                            "reason": "Frozen experiment evidence or artifacts failed verification",
                        }
                    ),
                    now.isoformat(),
                    job_identifier(job_id),
                    experiment_id,
                ),
            )

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

    # ------------------------------------------------------- B: sources
    def save_source_decisions(
        self, job_id: str, requirement_id: str, decisions: list[SourceDecision]
    ) -> None:
        with self.connect() as db:
            for item in decisions:
                db.execute(
                    "INSERT OR REPLACE INTO research_sources VALUES (?, ?, ?, ?)",
                    (job_id, requirement_id, item.source_id, item.model_dump_json()),
                )

    def source_decisions(
        self, job_id: str, requirement_id: str | None = None
    ) -> list[SourceDecision]:
        query = "SELECT decision FROM research_sources WHERE job_id=?"
        args: tuple[str, ...] = (job_identifier(job_id),)
        if requirement_id is not None:
            query += " AND requirement_id=?"
            args += (requirement_id,)
        with self.connect() as db:
            return [
                SourceDecision.model_validate_json(r[0])
                for r in db.execute(query + " ORDER BY rowid", args)
            ]

    # -------------------------------------------------- B: acquisitions
    @staticmethod
    def _acquisition(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["params"] = json.loads(value["params"])
        return value

    def plan_acquisition(
        self, key: str, source_id: str, params: dict[str, str], *, status: str, now: datetime
    ) -> str:
        """Idempotent by content key: an equivalent acquisition is reused, never repeated."""
        stamp = now.isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM research_acquisitions WHERE acquisition_key=?", (key,)
            ).fetchone()
            if row:
                return str(row[0])
            acquisition_id = str(uuid4())
            db.execute(
                "INSERT INTO research_acquisitions(id, acquisition_key, source_id, params, status, "
                "detail, created_at, updated_at, next_attempt_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    acquisition_id,
                    key,
                    source_id,
                    json.dumps(params, sort_keys=True),
                    status,
                    "Waiting for approval" if status == "awaiting_approval" else "Queued",
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            return acquisition_id

    def link_acquisition(
        self, job_id: str, acquisition_id: str, requirement_id: str, approval: str
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO research_acquisition_links VALUES (?, ?, ?, ?)",
                (job_id, acquisition_id, requirement_id, approval),
            )

    def acquisitions_for(self, source_id: str, entity: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM research_acquisitions WHERE source_id=? AND "
                "json_extract(params, '$.entity')=? ORDER BY created_at",
                (source_id, entity),
            ).fetchall()
        return [self._acquisition(r) for r in rows]

    def job_acquisitions(
        self, job_id: str, *, statuses: tuple[str, ...] | None = None
    ) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT a.* FROM research_acquisitions a WHERE a.id IN ("
                "SELECT acquisition_id FROM research_acquisition_links WHERE job_id=?) "
                "ORDER BY a.next_attempt_at, a.created_at, a.rowid",
                (job_identifier(job_id),),
            ).fetchall()
        result = [self._acquisition(r) for r in rows]
        return [r for r in result if statuses is None or r["status"] in statuses]

    def requirement_acquisitions(self, job_id: str, requirement_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT a.* FROM research_acquisitions a JOIN research_acquisition_links l "
                "ON l.acquisition_id=a.id WHERE l.job_id=? AND l.requirement_id=?",
                (job_identifier(job_id), requirement_id),
            ).fetchall()
        return [self._acquisition(r) for r in rows]

    def start_acquisition(self, acquisition_id: str, *, now: datetime) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE research_acquisitions SET status='running', attempts=attempts+1, "
                "detail='Fetching', updated_at=? WHERE id=?",
                (now.isoformat(), acquisition_id),
            )

    def finish_acquisition(
        self,
        acquisition_id: str,
        status: str,
        detail: str,
        *,
        now: datetime,
        requests: int = 0,
        size: int = 0,
        dataset_id: str | None = None,
        next_attempt_at: datetime | None = None,
    ) -> None:
        if status not in {"queued", "completed", "failed", "denied"}:
            raise ValueError("invalid acquisition status")
        with self.connect() as db:
            db.execute(
                "UPDATE research_acquisitions SET status=?, detail=?, updated_at=?, "
                "requests=requests+?, bytes=bytes+?, dataset_id=COALESCE(?, dataset_id), "
                "next_attempt_at=? WHERE id=?",
                (
                    status,
                    detail[:600],
                    now.isoformat(),
                    requests,
                    size,
                    dataset_id,
                    (next_attempt_at or now).isoformat(),
                    acquisition_id,
                ),
            )

    def decide_acquisition(
        self, job_id: str, acquisition_id: str, *, approve: bool, now: datetime
    ) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT a.status FROM research_acquisitions a JOIN research_acquisition_links l "
                "ON l.acquisition_id=a.id WHERE l.job_id=? AND a.id=?",
                (job_identifier(job_id), job_identifier(acquisition_id)),
            ).fetchone()
            if row is None:
                raise KeyError("acquisition not found for this job")
            if row[0] != "awaiting_approval":
                return False
            db.execute(
                "UPDATE research_acquisitions SET status=?, detail=?, updated_at=? WHERE id=?",
                (
                    "queued" if approve else "denied",
                    "Approved by user" if approve else "Denied by user",
                    now.isoformat(),
                    acquisition_id,
                ),
            )
            db.execute(
                "UPDATE research_acquisition_links SET approval=? "
                "WHERE job_id=? AND acquisition_id=?",
                ("approved" if approve else "denied", job_id, acquisition_id),
            )
            return True

    def recover_acquisitions(self, *, now: datetime) -> int:
        """A fetch interrupted by a restart is retried; its preserved bytes are reused by key."""
        with self.connect() as db:
            return db.execute(
                "UPDATE research_acquisitions SET status='queued', detail='Interrupted by restart; "
                "queued again', updated_at=? WHERE status='running'",
                (now.isoformat(),),
            ).rowcount

    # ------------------------------------------------------- B: forward
    def plan_forward(
        self,
        requirement: DataRequirement,
        *,
        source_id: str,
        collector: str,
        collector_status: str,
        events_observed: int,
        detail: str,
        now: datetime,
        next_check_at: datetime,
    ) -> None:
        key = requirement.coverage_key
        stamp = now.isoformat()
        spec = json.dumps(
            {
                "kind": requirement.kind.value,
                "variable": requirement.variable,
                "entity": requirement.entity,
                "series": requirement.series,
                "family": requirement.family,
                "clock": requirement.clock,
                "fidelity": requirement.fidelity,
                "min_sources": requirement.min_sources,
            },
            sort_keys=True,
        )
        status = (
            "satisfied"
            if events_observed >= requirement.min_events
            else "awaiting_observations"
            if collector_status == "covered"
            else "blocked_collector_change"
        )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT events_required FROM research_forward WHERE coverage_key=?", (key,)
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO research_forward "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(uuid4()),
                        key,
                        spec,
                        source_id,
                        collector,
                        collector_status,
                        requirement.min_events,
                        events_observed,
                        status,
                        detail,
                        stamp,
                        stamp,
                        next_check_at.isoformat(),
                        None,
                    ),
                )
            else:
                required = max(int(row[0]), requirement.min_events)
                status = (
                    "satisfied"
                    if events_observed >= required
                    else "awaiting_observations"
                    if collector_status == "covered"
                    else "blocked_collector_change"
                )
                db.execute(
                    "UPDATE research_forward SET events_required=?, events_observed=?, status=?, "
                    "collector=?, collector_status=?, detail=?, updated_at=?, next_check_at=? "
                    "WHERE coverage_key=?",
                    (
                        required,
                        events_observed,
                        status,
                        collector,
                        collector_status,
                        detail,
                        stamp,
                        next_check_at.isoformat(),
                        key,
                    ),
                )

    def forward_id(self, coverage_key: str) -> str:
        with self.connect() as db:
            return str(
                db.execute(
                    "SELECT id FROM research_forward WHERE coverage_key=?", (coverage_key,)
                ).fetchone()[0]
            )

    def link_forward(self, job_id: str, forward_id: str, requirement_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO research_forward_links VALUES (?, ?, ?)",
                (job_id, forward_id, requirement_id),
            )

    @staticmethod
    def _forward(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value.update(json.loads(value.pop("spec")))
        return value

    def job_forward(self, job_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT DISTINCT f.* FROM research_forward f JOIN research_forward_links l "
                "ON l.forward_id=f.id WHERE l.job_id=? ORDER BY f.created_at",
                (job_identifier(job_id),),
            ).fetchall()
        return [self._forward(r) for r in rows]

    def requirement_forward(self, job_id: str, requirement_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT f.* FROM research_forward f "
                "JOIN research_forward_links l ON l.forward_id=f.id "
                "WHERE l.job_id=? AND l.requirement_id=?",
                (job_identifier(job_id), requirement_id),
            ).fetchone()
        return self._forward(row) if row else None

    def forward_requests(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM research_forward ORDER BY created_at").fetchall()
            result = []
            for row in rows:
                value = self._forward(row)
                value["jobs"] = [
                    str(r[0])
                    for r in db.execute(
                        "SELECT DISTINCT job_id FROM research_forward_links WHERE forward_id=?",
                        (value["id"],),
                    )
                ]
                result.append(value)
            return result

    # ------------------------------------------------------ B: features
    def register_feature(
        self, job_id: str, manifest: dict[str, Any], hypotheses: list[str], *, now: datetime
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO research_features VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    manifest["artifact_id"],
                    manifest["feature_id"],
                    manifest["version"],
                    manifest["definition_hash"],
                    manifest["entity"],
                    json.dumps(manifest, sort_keys=True),
                    now.isoformat(),
                ),
            )
            db.execute(
                "INSERT OR REPLACE INTO research_feature_links VALUES (?, ?, ?)",
                (job_id, manifest["artifact_id"], json.dumps(hypotheses)),
            )

    def job_features(self, job_id: str, *, history: bool = False) -> list[dict[str, Any]]:
        """Current artifact per feature and entity; earlier immutable artifacts on request."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT f.manifest, l.hypothesis_ids FROM research_features f JOIN "
                "research_feature_links l ON l.artifact_id=f.artifact_id WHERE l.job_id=? "
                "ORDER BY f.feature_id, f.entity, f.created_at, f.rowid",
                (job_identifier(job_id),),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for manifest, hypotheses in rows:
            value = json.loads(manifest)
            value["hypotheses"] = json.loads(hypotheses)
            value["inputs"] = value.pop("input_datasets")
            if result and (result[-1]["feature_id"], result[-1]["entity"]) == (
                value["feature_id"],
                value["entity"],
            ):
                value["supersedes"] = [*result[-1].get("supersedes", []), result[-1]["artifact_id"]]
                if not history:
                    result.pop()
            result.append(value)
        return result
