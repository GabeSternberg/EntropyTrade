"""Full stored-metadata counts without constructor, evidence or refresh side effects."""

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import pytest

from entropytrade.api import workspace_summary as summary_module
from entropytrade.api.jobs import Jobs
from entropytrade.api.workspace_summary import workspace_summary
from entropytrade.research.store import ResearchStore
from entropytrade.tracking import alerts, readiness_store
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_workbench_http import exchange

if TYPE_CHECKING:
    from entropytrade.api.server import WorkbenchServer

AT = "2026-11-16T01:00:00+00:00"
PRIVATE = "PRIVATE_PROMPT_PATH_KEY_MUST_NOT_APPEAR"


def uid(index: int) -> str:
    return str(UUID(int=index + 1))


def digest(index: int) -> str:
    return "sha256:" + f"{index:064x}"


def seed(root: Path, count: int = 67) -> tuple[Jobs, ResearchStore]:
    """Actual schemas, with explicitly synthetic metadata fixtures, no financial proof."""
    jobs = Jobs(root)
    TrackingStore(jobs)
    research = ResearchStore(root / "research")
    with research.connect() as db:
        for index in range(count):
            db.execute(
                "INSERT INTO research_jobs "
                "(id,request,fingerprint,family,universe,status,detail,created_at,updated_at,"
                "next_run_at,usage) VALUES (?,?,?,'weather','[]',?,?,?, ?,?,'{}')",
                (
                    uid(index),
                    json.dumps({"objective": PRIVATE}),
                    digest(index),
                    "evaluated" if index % 2 else "failed",
                    PRIVATE,
                    AT,
                    AT,
                    AT,
                ),
            )
            result: dict[str, Any] | None = (
                {
                    "status": "evaluated" if index % 2 else "invalid",
                    "data_kind": "real" if index % 3 else "synthetic",
                    "validation": {"status": "evaluated" if index % 2 else "refused"},
                    "models": {"ridge": {"artifact_hash": digest(index), "path": PRIVATE}}
                    if index % 2
                    else {},
                    "backtest": {"status": "blocked", "reasons": [PRIVATE]},
                    "private": PRIVATE,
                }
                if index % 5
                else None
            )
            db.execute(
                "INSERT INTO research_experiments "
                "(job_id,id,hypothesis_id,status,config,result,created_at,updated_at) "
                "VALUES (?,?,?,'evaluated',?,?,?,?)",
                (
                    uid(index),
                    digest(index),
                    "h-synthetic-fixture",
                    json.dumps({"private": PRIVATE}),
                    json.dumps(result) if result is not None else None,
                    AT,
                    AT,
                ),
            )
    with jobs.connect() as db:
        db.executescript(readiness_store.SCHEMA)
        for index in range(count * 2):
            db.execute(
                "INSERT INTO jobs VALUES (?,?, 'completed',?,?,?,?)",
                (
                    uid(index),
                    json.dumps(
                        {
                            "mode": "cis1990" if index % 2 else "synthetic",
                            "family": "weather",
                            "idea": PRIVATE,
                        }
                    ),
                    AT,
                    AT,
                    PRIVATE,
                    json.dumps({"report": PRIVATE}),
                ),
            )
        for index in range(9):
            db.execute(
                "INSERT INTO monitors "
                "(id,job_id,candidate_id,family,spec,spec_hash,status,interval_seconds,next_at,"
                "created_at,failures,source_kind) VALUES (?,?,?,'weather',?,?,?,300,?,?,0,?)",
                (
                    uid(index),
                    uid(index),
                    "synthetic-fixture",
                    PRIVATE,
                    digest(index),
                    "active" if index % 2 else "cancelled",
                    AT,
                    AT,
                    "autonomous_research" if index % 3 else "legacy",
                ),
            )
        for index, kind in enumerate(("synthetic", "real", "real")):
            db.execute(
                "INSERT INTO shadow_accounts VALUES (?,?,?)",
                (uid(index), json.dumps({"data_kind": kind, "private": PRIVATE}), digest(index)),
            )
        for index in range(4):
            db.execute(
                "INSERT INTO shadow_alerts VALUES (?,?,?,?,?,?,?)",
                (
                    uid(index),
                    uid(index),
                    "stale_collection",
                    AT,
                    AT if index % 2 else None,
                    AT if index // 2 else None,
                    json.dumps({"private": PRIVATE}),
                ),
            )
        for index, status in enumerate(("proposed", "rejected")):
            db.execute(
                "INSERT INTO readiness_proposals VALUES (?,?,?,?,?,?,0,0,?,?)",
                (digest(index), uid(index), PRIVATE, digest(index), PRIVATE, status, AT, AT),
            )
    return jobs, research


def fingerprints(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        str(path.relative_to(root)): (
            path.read_bytes(),
            path.stat().st_mtime_ns,
            path.stat().st_ino,
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def test_full_counts_separate_course_experiments_accounts_and_alert_lifecycles(
    tmp_path: Path,
) -> None:
    seed(tmp_path)
    result = workspace_summary(tmp_path)
    assert result["schema"] == "workspace-summary-v1"
    assert result["recorded_metadata_only"] is True
    assert result["recent_limit"] == 10
    components = result["components"]
    assert all(
        component["available"] and component["initialized"] for component in components.values()
    )
    assert components["research_jobs"]["counts"] == {
        "total": 67,
        "by_status": {"evaluated": 33, "failed": 34},
    }
    assert (
        components["legacy_jobs"]["counts"]
        == components["course_jobs"]["counts"]
        == {
            "total": 67,
            "by_status": {"completed": 67},
        }
    )
    counts = components["experiments"]["counts"]
    assert counts["total"] == 67
    assert counts["by_status"] == {"evaluated": 67}
    assert counts["by_result_status"] == {"evaluated": 26, "invalid": 27, "not_recorded": 14}
    assert counts["by_validation_status"] == {"evaluated": 26, "refused": 27, "not_recorded": 14}
    assert counts["by_backtest_status"] == {"blocked": 53, "not_recorded": 14}
    assert counts["by_data_kind"] == {"real": 35, "synthetic": 18, "not_recorded": 14}
    assert counts["with_recorded_result"] == counts["with_recorded_validation"] == 53
    assert counts["with_recorded_backtest"] == 53  # Recorded blocked backtests are not success.
    assert counts["with_recorded_model"] == 26
    assert components["monitors"]["counts"] == {
        "total": 9,
        "by_status": {"active": 4, "cancelled": 5},
        "by_source_kind": {"autonomous_research": 6, "legacy": 3},
    }
    assert components["paper_accounts"]["counts"] == {
        "total": 3,
        "by_data_kind": {"real": 2, "synthetic": 1},
        "monitors_without_account": 6,
    }
    assert components["alerts"]["counts"] == {
        "total": 4,
        "unresolved": 2,
        "unacknowledged": 2,
        "unresolved_unacknowledged": 1,
    }
    assert components["readiness"]["counts"] == {
        "total": 2,
        "by_status": {"proposed": 1, "rejected": 1},
    }
    assert PRIVATE not in json.dumps(result)


def test_recent_references_are_deterministic_bounded_and_canonical(tmp_path: Path) -> None:
    seed(tmp_path)
    result = workspace_summary(tmp_path)
    assert workspace_summary(tmp_path) == result
    components = result["components"]
    for key in ("research_jobs", "experiments", "legacy_jobs", "course_jobs"):
        assert len(components[key]["recent"]) == 10
    assert components["research_jobs"]["recent"][0]["href"] == f"#/research/{uid(0)}"
    assert components["experiments"]["recent"][0]["href"] == (
        f"#/research/{uid(0)}?tab=experiments&experiment=sha256%3A{'0' * 64}"
    )
    assert components["legacy_jobs"]["recent"][0]["href"] == f"#/workbench?job={uid(0)}"
    assert components["course_jobs"]["recent"][0]["href"] == f"#/cis1990/{uid(1)}"
    assert components["monitors"]["recent"][0]["href"] == f"#/paper/{uid(0)}?tab=monitoring"
    assert components["paper_accounts"]["recent"][0]["href"] == f"#/paper/{uid(0)}?tab=account"
    assert components["alerts"]["recent"][0]["href"] == (
        f"#/ops?tab=alerts&monitor={uid(0)}&alert={uid(0)}"
    )
    assert components["readiness"]["recent"][0]["href"] == (
        f"#/paper/{uid(0)}?tab=readiness&proposal=sha256%3A{'0' * 64}"
    )


def test_missing_workspace_and_optional_tables_are_not_started_without_creation(
    tmp_path: Path,
) -> None:
    absent = tmp_path / "absent"
    for component in workspace_summary(absent)["components"].values():
        assert component["available"] is True
        assert component["initialized"] is False
        assert component["counts"]["total"] == 0
    assert not absent.exists()
    jobs = Jobs(tmp_path / "legacy")
    components = workspace_summary(jobs.root)["components"]
    assert components["legacy_jobs"]["initialized"] is True
    for key in (
        "research_jobs",
        "experiments",
        "monitors",
        "paper_accounts",
        "alerts",
        "readiness",
    ):
        assert components[key]["available"] is True
        assert components[key]["initialized"] is False
    with jobs.connect() as db:
        assert {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        } == {
            "jobs",
            "events",
        }


def test_missing_optional_account_table_counts_unstarted_monitors(tmp_path: Path) -> None:
    jobs, _ = seed(tmp_path, 1)
    with jobs.connect() as db:
        db.execute("DROP TABLE shadow_accounts")
    account = workspace_summary(tmp_path)["components"]["paper_accounts"]
    assert account["available"] is True
    assert account["initialized"] is False
    assert account["counts"] == {"total": 0, "by_data_kind": {}, "monitors_without_account": 9}


def test_closed_wal_reads_create_no_sidecars_and_touch_no_workspace_evidence(
    tmp_path: Path,
) -> None:
    seed(tmp_path, 2)
    evidence = tmp_path / "research/models/private-evidence.json"
    evidence.parent.mkdir()
    evidence.write_text(PRIVATE)
    assert not list(tmp_path.rglob("*-wal"))
    before = fingerprints(tmp_path)
    assert all(c["available"] for c in workspace_summary(tmp_path)["components"].values())
    assert fingerprints(tmp_path) == before


def test_active_uncheckpointed_wal_is_current_without_application_writes(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    writer = sqlite3.connect(jobs.path)
    try:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO jobs VALUES (?,?,'completed',?,?,?,NULL)",
            (uid(0), '{"mode":"synthetic","family":"weather"}', AT, AT, PRIVATE),
        )
        writer.commit()
        before = fingerprints(tmp_path)
        result = workspace_summary(tmp_path)
        assert result["components"]["legacy_jobs"]["counts"]["total"] == 1
        assert result["components"]["course_jobs"]["counts"]["total"] == 0
        after = fingerprints(tmp_path)
        assert set(after) == set(before)
        # Existing SHM read marks are volatile SQLite coordination, like read locks.
        assert {k: v for k, v in after.items() if not k.endswith("-shm")} == {
            k: v for k, v in before.items() if not k.endswith("-shm")
        }
    finally:
        writer.close()


@pytest.mark.parametrize("name", ["jobs.sqlite", "research/research.sqlite"])
@pytest.mark.parametrize("content", [b"", b"controlled corrupt database"])
def test_corrupt_database_is_unknown_and_other_database_remains_available(
    tmp_path: Path, name: str, content: bytes
) -> None:
    seed(tmp_path, 2)
    (tmp_path / name).write_bytes(content)
    before = fingerprints(tmp_path)
    components = workspace_summary(tmp_path)["components"]
    affected = (
        {"research_jobs", "experiments"}
        if name.startswith("research/")
        else {"legacy_jobs", "course_jobs", "monitors", "paper_accounts", "alerts", "readiness"}
    )
    for key, component in components.items():
        if key in affected:
            assert component == {
                "available": False,
                "initialized": None,
                "counts": None,
                "recent": [],
            }
        else:
            assert component["available"] is True
    assert fingerprints(tmp_path) == before


@pytest.mark.parametrize(
    ("table", "column"), [("research_experiments", "result"), ("shadow_accounts", "state")]
)
def test_bad_component_json_does_not_hide_other_counts(
    tmp_path: Path, table: str, column: str
) -> None:
    jobs, research = seed(tmp_path, 2)
    store = research if table == "research_experiments" else jobs
    with store.connect() as db:
        # Parameters are fixed test cases, never user/browser input.
        db.execute(f"UPDATE {table} SET {column}='not-json'")  # noqa: S608
    components = workspace_summary(tmp_path)["components"]
    unavailable = "experiments" if table == "research_experiments" else "paper_accounts"
    assert components[unavailable]["counts"] is None
    assert all(value["available"] for key, value in components.items() if key != unavailable)


def test_partial_readiness_schema_is_unknown_but_does_not_hide_monitors(tmp_path: Path) -> None:
    jobs, _ = seed(tmp_path, 1)
    with jobs.connect() as db:
        db.execute("DROP TABLE readiness_events")
    components = workspace_summary(tmp_path)["components"]
    assert components["readiness"]["counts"] is None
    assert components["monitors"]["counts"]["total"] == 9


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_symlink_and_special_files_are_refused_without_opening_targets(
    tmp_path: Path, suffix: str
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = tmp_path / "private-target"
    target.write_bytes(PRIVATE.encode())
    (root / ("jobs.sqlite" + suffix)).symlink_to(target)
    components = workspace_summary(root)["components"]
    assert components["legacy_jobs"]["counts"] is None
    assert components["research_jobs"]["available"] is True
    assert target.read_bytes() == PRIVATE.encode()
    (root / ("jobs.sqlite" + suffix)).unlink()
    (root / ("jobs.sqlite" + suffix)).mkdir()
    assert workspace_summary(root)["components"]["legacy_jobs"]["counts"] is None


def test_symlink_workspace_parent_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "actual"
    seed(root, 1)
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    assert all(not c["available"] for c in workspace_summary(link)["components"].values())


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_incomplete_sidecars_are_unknown_and_never_repaired(tmp_path: Path, suffix: str) -> None:
    jobs = Jobs(tmp_path)
    Path(str(jobs.path) + suffix).write_bytes(b"controlled incomplete sidecar")
    before = fingerprints(tmp_path)
    assert workspace_summary(tmp_path)["components"]["legacy_jobs"]["counts"] is None
    assert fingerprints(tmp_path) == before


def test_concurrent_writer_cannot_turn_immutable_read_into_stale_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = Jobs(tmp_path)
    original = summary_module._snapshot
    writer: sqlite3.Connection | None = None

    def race(path: Path) -> tuple[summary_module.FileStamp, ...]:
        nonlocal writer
        snapshot = original(path)
        if path == jobs.path and writer is None:
            writer = sqlite3.connect(jobs.path)
            writer.execute(
                "INSERT INTO jobs VALUES (?,?,'completed',?,?,?,NULL)",
                (uid(0), '{"mode":"synthetic","family":"weather"}', AT, AT, PRIVATE),
            )
            writer.commit()
        return snapshot

    monkeypatch.setattr(summary_module, "_snapshot", race)
    try:
        components = workspace_summary(tmp_path)["components"]
        assert components["legacy_jobs"]["counts"] is None
        assert components["course_jobs"]["counts"]["total"] == 0
    finally:
        if writer is not None:
            writer.close()


def test_summary_http_uses_only_read_transactions_and_never_refreshes_or_constructs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs, _ = seed(tmp_path, 1)
    server = cast("WorkbenchServer", SimpleNamespace(jobs=jobs, server_port=43128))
    statements: list[str] = []
    original = sqlite3.connect

    def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        db = cast("sqlite3.Connection", original(*args, **kwargs))
        db.set_trace_callback(statements.append)
        return db

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("summary attempted store creation or evidence/alert refresh")

    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(Jobs, "__init__", refuse)
    monkeypatch.setattr(TrackingStore, "__init__", refuse)
    monkeypatch.setattr(ResearchStore, "__init__", refuse)
    monkeypatch.setattr(TrackingStore, "alerts", refuse)
    monkeypatch.setattr(alerts, "refresh", refuse)
    monkeypatch.setattr(readiness_store, "initialize", refuse)
    before = fingerprints(tmp_path)
    status, headers, body = exchange(server, "/api/workspace/summary")
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body)["components"]["research_jobs"]["counts"]["total"] == 1
    assert statements
    assert all(
        sql.startswith(("SELECT", "BEGIN", "ROLLBACK", "PRAGMA table_info")) for sql in statements
    )
    assert fingerprints(tmp_path) == before
    assert PRIVATE not in body.decode()
    assert (
        exchange(server, "/api/workspace/summary", headers={"Origin": "https://external.test"})[0]
        == 403
    )
