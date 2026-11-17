"""Bounded references and full counts without application state changes.

Nothing here validates scientific evidence or calls a store constructor. In particular,
recorded model, backtest and readiness states are not evidence of current eligibility.
Each component fails independently; unreadable metadata is unknown, never an empty store.
Active WAL reads may use SQLite's existing SHM read marks and coordination locks.
"""

import re
import sqlite3
import stat
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from entropytrade.api.jobs import _CONNECTION_LOCK

RECENT_LIMIT = 10
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_LABEL = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_READINESS_TABLES = frozenset(
    {
        "workspace_controls",
        "workspace_control_events",
        "shadow_cycle_controls",
        "readiness_proposals",
        "readiness_events",
        "readiness_investigations",
    }
)
type Component = dict[str, Any]
type Reader = Callable[[sqlite3.Connection, set[str]], tuple[dict[str, Any], list[dict[str, Any]]]]
type FileStamp = tuple[int, int, int, int, int, int] | None


def _label(value: object) -> str:
    return value if isinstance(value, str) and _LABEL.fullmatch(value) else "unknown"


def _uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return value if str(UUID(value)) == value else None
    except ValueError:
        return None


def _hash(value: object) -> str | None:
    return value if isinstance(value, str) and _HASH.fullmatch(value) else None


def _time(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        return value if datetime.fromisoformat(value).utcoffset() is not None else None
    except ValueError:
        return None


def _stamp(path: Path, *, directory: bool = False) -> FileStamp:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("metadata path is not a regular file or directory")
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _snapshot(path: Path) -> tuple[FileStamp, ...]:
    # lstat every ancestor before opening SQLite: reject symlinks, FIFOs and devices.
    # Directory timestamps are excluded because independent workspace activity is fine.
    for parent in path.parents:
        _stamp(parent, directory=True)
    return tuple(_stamp(Path(str(path) + suffix)) for suffix in ("", "-wal", "-shm", "-journal"))


def _component(
    path: Path,
    table: str,
    empty: dict[str, Any],
    reader: Reader,
) -> Component:
    try:
        # Jobs connections share this lock, including their close/checkpoint boundary.
        # Other processes retain SQLite's ordinary read/coordination locks.
        with _CONNECTION_LOCK:
            before = _snapshot(path)
            if before[0] is None:
                if any(before[1:]) or _snapshot(path) != before:
                    raise ValueError("incomplete or changing database files")
                return {"available": True, "initialized": False, "counts": empty, "recent": []}
            if before[0][3] < 100:
                # SQLite accepts an existing empty file as a new blank database. An
                # existing workspace store this small is truncated, not unstarted.
                raise ValueError("truncated database file")
            if before[3] is not None or (before[1] is None) != (before[2] is None):
                raise ValueError("incomplete or recovering database files")
            # A plain mode=ro connection to a closed WAL database can create WAL/SHM.
            # immutable avoids that only when neither sidecar exists. Check all file
            # stamps afterwards so a concurrent writer cannot produce stale success.
            suffix = "?mode=ro&immutable=1" if before[1] is None else "?mode=ro"
            db = sqlite3.connect(path.absolute().as_uri() + suffix, uri=True, timeout=0.2)
            db.row_factory = sqlite3.Row
            try:
                db.execute("BEGIN")
                tables = {
                    str(row[0])
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if (
                    table == "readiness_proposals"
                    and tables & _READINESS_TABLES
                    and not tables >= _READINESS_TABLES
                ):
                    raise ValueError("incomplete readiness metadata schema")
                counts, recent = (
                    reader(db, tables)
                    if table in tables or table == "shadow_accounts"
                    else (empty, [])
                )
                initialized = table in tables
                db.rollback()
            finally:
                db.close()
            if _snapshot(path) != before:
                raise ValueError("metadata changed during read")
            return {
                "available": True,
                "initialized": initialized,
                "counts": counts,
                "recent": recent,
            }
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return {"available": False, "initialized": None, "counts": None, "recent": []}


def _groups(db: sqlite3.Connection, sql: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for value, count in db.execute(sql):
        key = _label(value)
        result[key] = result.get(key, 0) + int(count)
    return dict(sorted(result.items()))


def _research_jobs(db: sqlite3.Connection, _tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    counts = {
        "total": db.execute("SELECT count(*) FROM research_jobs").fetchone()[0],
        "by_status": _groups(db, "SELECT status, count(*) FROM research_jobs GROUP BY status"),
    }
    recent = [
        {
            "id": job_id,
            "job_id": job_id,
            "family": _label(row["family"]),
            "status": _label(row["status"]),
            "created_at": _time(row["created_at"]),
            "updated_at": _time(row["updated_at"]),
            "href": f"#/research/{job_id}",
        }
        for row in db.execute(
            "SELECT id, family, status, created_at, updated_at FROM research_jobs "
            "ORDER BY updated_at DESC, id ASC LIMIT 10"
        )
        if (job_id := _uuid(row["id"]))
    ]
    return counts, recent


def _experiments(db: sqlite3.Connection, _tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    counts = dict(
        db.execute(
            "SELECT count(*) AS total, "
            "coalesce(sum(json_type(result)='object'),0) AS with_recorded_result, "
            "coalesce(sum(json_type(result,'$.validation')='object'),0) "
            "AS with_recorded_validation, "
            "coalesce(sum(json_type(result,'$.backtest')='object'),0) AS with_recorded_backtest, "
            "coalesce(sum(EXISTS(SELECT 1 FROM json_each(result,'$.models') AS model "
            "WHERE CASE WHEN model.type='object' THEN "
            "json_type(model.value,'$.artifact_hash')='text' ELSE 0 END)),0) "
            "AS with_recorded_model FROM research_experiments"
        ).fetchone()
    )
    counts["by_status"] = _groups(
        db, "SELECT status, count(*) FROM research_experiments GROUP BY status"
    )
    counts["by_result_status"] = _groups(
        db,
        "SELECT coalesce(json_extract(result,'$.status'),'not_recorded'), count(*) "
        "FROM research_experiments GROUP BY 1",
    )
    counts["by_validation_status"] = _groups(
        db,
        "SELECT coalesce(json_extract(result,'$.validation.status'),'not_recorded'), count(*) "
        "FROM research_experiments GROUP BY 1",
    )
    counts["by_backtest_status"] = _groups(
        db,
        "SELECT coalesce(json_extract(result,'$.backtest.status'),'not_recorded'), count(*) "
        "FROM research_experiments GROUP BY 1",
    )
    counts["by_data_kind"] = _groups(
        db,
        "SELECT coalesce(json_extract(result,'$.data_kind'),'not_recorded'), count(*) "
        "FROM research_experiments GROUP BY 1",
    )
    recent = []
    for row in db.execute(
        "SELECT job_id, id, status, updated_at, "
        "json_extract(result,'$.status') AS result_status, "
        "json_extract(result,'$.validation.status') AS validation_status, "
        "json_extract(result,'$.backtest.status') AS backtest_status, "
        "json_extract(result,'$.data_kind') AS data_kind FROM research_experiments "
        "ORDER BY updated_at DESC, job_id ASC, id ASC LIMIT 10"
    ):
        job_id, experiment_id = _uuid(row["job_id"]), _hash(row["id"])
        if job_id and experiment_id:
            recent.append(
                {
                    "job_id": job_id,
                    "experiment_id": experiment_id,
                    **{
                        key: _label(row[key]) if row[key] is not None else None
                        for key in (
                            "status",
                            "result_status",
                            "validation_status",
                            "backtest_status",
                            "data_kind",
                        )
                    },
                    "updated_at": _time(row["updated_at"]),
                    "href": f"#/research/{job_id}?"
                    + urlencode({"tab": "experiments", "experiment": experiment_id}),
                }
            )
    return counts, recent


def _legacy_jobs(db: sqlite3.Connection, *, course: bool) -> tuple[dict[str, Any], list[Any]]:
    counts: dict[str, Any] = {"total": 0, "by_status": {}}
    # These are two fixed, internal SQL strings, never browser input.
    total_sql = (
        "SELECT count(*) FROM jobs WHERE json_extract(request,'$.mode')='cis1990'"
        if course
        else "SELECT count(*) FROM jobs WHERE "
        "coalesce(json_extract(request,'$.mode'),'')<>'cis1990'"
    )
    group_sql = (
        "SELECT status,count(*) FROM jobs WHERE json_extract(request,'$.mode')='cis1990' "
        "GROUP BY status"
        if course
        else "SELECT status,count(*) FROM jobs WHERE "
        "coalesce(json_extract(request,'$.mode'),'')<>'cis1990' GROUP BY status"
    )
    counts["total"] = db.execute(total_sql).fetchone()[0]
    counts["by_status"] = _groups(db, group_sql)
    recent = [
        {
            "id": job_id,
            "job_id": job_id,
            "family": _label(row["family"]),
            "status": _label(row["status"]),
            "created_at": _time(row["created_at"]),
            "updated_at": _time(row["updated_at"]),
            "href": f"#/cis1990/{job_id}" if course else f"#/workbench?job={job_id}",
        }
        for row in db.execute(
            "SELECT id,status,created_at,updated_at,json_extract(request,'$.family') AS family "
            "FROM jobs WHERE (coalesce(json_extract(request,'$.mode'),'')='cis1990')=? "
            "ORDER BY updated_at DESC,id ASC LIMIT 10",
            (course,),
        )
        if (job_id := _uuid(row["id"]))
    ]
    return counts, recent


def _monitors(db: sqlite3.Connection, _tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    # Pre-D monitors have no source_kind; their schema records legacy provenance.
    columns = {row[1] for row in db.execute("PRAGMA table_info(monitors)")}
    current = "source_kind" in columns
    counts = {
        "total": db.execute("SELECT count(*) FROM monitors").fetchone()[0],
        "by_status": _groups(db, "SELECT status,count(*) FROM monitors GROUP BY status"),
        "by_source_kind": _groups(
            db,
            "SELECT source_kind,count(*) FROM monitors GROUP BY source_kind"
            if current
            else "SELECT 'legacy',count(*) FROM monitors HAVING count(*)>0",
        ),
    }
    rows = db.execute(
        "SELECT id,status,family,created_at,source_kind FROM monitors "
        "ORDER BY created_at DESC,id ASC LIMIT 10"
        if current
        else "SELECT id,status,family,created_at,'legacy' AS source_kind FROM monitors "
        "ORDER BY created_at DESC,id ASC LIMIT 10"
    )
    recent = [
        {
            "id": monitor_id,
            "monitor_id": monitor_id,
            "status": _label(row["status"]),
            "family": _label(row["family"]),
            "source_kind": _label(row["source_kind"]),
            "created_at": _time(row["created_at"]),
            "href": f"#/paper/{monitor_id}?tab=monitoring",
        }
        for row in rows
        if (monitor_id := _uuid(row["id"]))
    ]
    return counts, recent


def _accounts(db: sqlite3.Connection, tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    if "shadow_accounts" not in tables:
        return {
            "total": 0,
            "by_data_kind": {},
            "monitors_without_account": db.execute("SELECT count(*) FROM monitors").fetchone()[0]
            if "monitors" in tables
            else 0,
        }, []
    counts = {
        "total": db.execute("SELECT count(*) FROM shadow_accounts").fetchone()[0],
        "by_data_kind": _groups(
            db,
            "SELECT coalesce(json_extract(state,'$.data_kind'),'unknown'),count(*) "
            "FROM shadow_accounts GROUP BY 1",
        ),
        "monitors_without_account": db.execute(
            "SELECT count(*) FROM monitors WHERE NOT EXISTS "
            "(SELECT 1 FROM shadow_accounts WHERE monitor_id=monitors.id)"
        ).fetchone()[0]
        if "monitors" in tables
        else 0,
    }
    rows = db.execute(
        "SELECT a.monitor_id,json_extract(a.state,'$.data_kind') AS data_kind,m.created_at "
        "FROM shadow_accounts AS a LEFT JOIN monitors AS m ON m.id=a.monitor_id "
        "ORDER BY m.created_at DESC,a.monitor_id ASC LIMIT 10"
        if "monitors" in tables
        else "SELECT monitor_id,json_extract(state,'$.data_kind') AS data_kind,NULL AS created_at "
        "FROM shadow_accounts ORDER BY monitor_id ASC LIMIT 10"
    )
    recent = [
        {
            "monitor_id": monitor_id,
            "data_kind": _label(row["data_kind"]),
            "created_at": _time(row["created_at"]),
            "href": f"#/paper/{monitor_id}?tab=account",
        }
        for row in rows
        if (monitor_id := _uuid(row["monitor_id"]))
    ]
    return counts, recent


def _alerts(db: sqlite3.Connection, _tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    counts = dict(
        db.execute(
            "SELECT count(*) AS total,coalesce(sum(resolved_at IS NULL),0) AS unresolved, "
            "coalesce(sum(acknowledged_at IS NULL),0) AS unacknowledged, "
            "coalesce(sum(resolved_at IS NULL AND acknowledged_at IS NULL),0) "
            "AS unresolved_unacknowledged FROM shadow_alerts"
        ).fetchone()
    )
    recent = []
    for row in db.execute(
        "SELECT id,monitor_id,kind,opened_at,acknowledged_at,resolved_at FROM shadow_alerts "
        "ORDER BY opened_at DESC,id ASC LIMIT 10"
    ):
        alert_id, monitor_id = _uuid(row["id"]), _uuid(row["monitor_id"])
        if alert_id and monitor_id:
            recent.append(
                {
                    "id": alert_id,
                    "alert_id": alert_id,
                    "monitor_id": monitor_id,
                    "kind": _label(row["kind"]),
                    "opened_at": _time(row["opened_at"]),
                    "acknowledged_at": _time(row["acknowledged_at"]),
                    "resolved_at": _time(row["resolved_at"]),
                    "href": "#/ops?"
                    + urlencode({"tab": "alerts", "monitor": monitor_id, "alert": alert_id}),
                    "monitor_href": f"#/paper/{monitor_id}?tab=monitoring",
                }
            )
    return counts, recent


def _readiness(db: sqlite3.Connection, _tables: set[str]) -> tuple[dict[str, Any], list[Any]]:
    counts = {
        "total": db.execute("SELECT count(*) FROM readiness_proposals").fetchone()[0],
        "by_status": _groups(db, "SELECT status,count(*) FROM readiness_proposals GROUP BY status"),
    }
    recent = []
    for row in db.execute(
        "SELECT id,monitor_id,status,created_at,updated_at FROM readiness_proposals "
        "ORDER BY updated_at DESC,id ASC LIMIT 10"
    ):
        proposal_id, monitor_id = _hash(row["id"]), _uuid(row["monitor_id"])
        if proposal_id and monitor_id:
            recent.append(
                {
                    "id": proposal_id,
                    "proposal_id": proposal_id,
                    "monitor_id": monitor_id,
                    "status": _label(row["status"]),
                    "created_at": _time(row["created_at"]),
                    "updated_at": _time(row["updated_at"]),
                    "href": f"#/paper/{monitor_id}?"
                    + urlencode({"tab": "readiness", "proposal": proposal_id}),
                }
            )
    return counts, recent


def workspace_summary(root: Path) -> dict[str, Any]:
    """Inspect existing stores only, with no schema, source, model or alert refresh."""
    research = root / "research/research.sqlite"
    jobs = root / "jobs.sqlite"
    components = {
        "research_jobs": _component(
            research, "research_jobs", {"total": 0, "by_status": {}}, _research_jobs
        ),
        "experiments": _component(
            research,
            "research_experiments",
            {
                "total": 0,
                "by_status": {},
                "by_result_status": {},
                "by_validation_status": {},
                "by_backtest_status": {},
                "by_data_kind": {},
                "with_recorded_result": 0,
                "with_recorded_validation": 0,
                "with_recorded_backtest": 0,
                "with_recorded_model": 0,
            },
            _experiments,
        ),
        "legacy_jobs": _component(
            jobs,
            "jobs",
            {"total": 0, "by_status": {}},
            lambda db, _tables: _legacy_jobs(db, course=False),
        ),
        "course_jobs": _component(
            jobs,
            "jobs",
            {"total": 0, "by_status": {}},
            lambda db, _tables: _legacy_jobs(db, course=True),
        ),
        "monitors": _component(
            jobs, "monitors", {"total": 0, "by_status": {}, "by_source_kind": {}}, _monitors
        ),
        "paper_accounts": _component(
            jobs,
            "shadow_accounts",
            {"total": 0, "by_data_kind": {}, "monitors_without_account": 0},
            _accounts,
        ),
        "alerts": _component(
            jobs,
            "shadow_alerts",
            {"total": 0, "unresolved": 0, "unacknowledged": 0, "unresolved_unacknowledged": 0},
            _alerts,
        ),
        "readiness": _component(
            jobs, "readiness_proposals", {"total": 0, "by_status": {}}, _readiness
        ),
    }
    return {
        "schema": "workspace-summary-v1",
        "recorded_metadata_only": True,
        "recent_limit": RECENT_LIMIT,
        "components": components,
    }
