"""CONTROLLED paper-source recovery tests; no empirical trading or model approval."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import (
    LEGACY_MONITOR_COLUMNS,
    restore,
    snapshot,
    validate_database,
)
from entropytrade.data.sources import file_hash
from entropytrade.research.model import ResearchRequest
from entropytrade.research.paper import _source
from entropytrade.research.store import ResearchStore
from entropytrade.tracking.store import TrackingStore
from tests.research_paper_support import paper_fixture
from tests.unit.test_tracking import monitor


@pytest.fixture
def controlled_repo(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED recovery dependency identity: " + name)
    return tmp_path


def previous_layout(store: TrackingStore) -> None:
    """Recreate an actual pre-D column inventory without running any migration."""
    columns = ", ".join(LEGACY_MONITOR_COLUMNS.split())
    with store.jobs.connect() as db:
        db.execute(f"CREATE TABLE pre_d_monitors AS SELECT {columns} FROM monitors")  # noqa: S608 - fixed schema constant
        db.execute("DROP TABLE monitors")
        db.execute("ALTER TABLE pre_d_monitors RENAME TO monitors")


def dump(path: Path) -> list[str]:
    with sqlite3.connect(path) as db:
        return list(db.iterdump())


def test_pre_d_archive_remains_byte_stable_until_explicit_store_migration(
    controlled_repo: Path,
) -> None:
    workspace = controlled_repo / "data/cache/pre-d"
    store = TrackingStore(Jobs(workspace))
    monitor_id = monitor(store)
    previous_layout(store)
    before = dump(workspace / "jobs.sqlite")
    archive = controlled_repo / "data/recovery/pre-d.zip"
    assert snapshot(controlled_repo, workspace, archive)["monitors"] == 1
    assert dump(workspace / "jobs.sqlite") == before
    destination = controlled_repo / "data/cache/restored-pre-d"
    restore(controlled_repo, archive, destination)
    assert dump(destination / "jobs.sqlite") == before
    reopened = TrackingStore(Jobs(destination))
    current = reopened.get(monitor_id)
    assert current is not None
    assert current["source_kind"] == "legacy"
    assert current["research_job_id"] is None
    assert current["source_ref"] is None
    assert current["submission_enabled"] is False


def test_partially_migrated_source_columns_are_refused_read_only(controlled_repo: Path) -> None:
    workspace = controlled_repo / "data/cache/partial"
    store = TrackingStore(Jobs(workspace))
    monitor(store)
    previous_layout(store)
    with store.jobs.connect() as db:
        db.execute("ALTER TABLE monitors ADD COLUMN source_kind TEXT DEFAULT 'legacy'")
    before = dump(workspace / "jobs.sqlite")
    with pytest.raises(ValueError, match="columns"):
        validate_database(workspace)
    assert dump(workspace / "jobs.sqlite") == before


@pytest.mark.parametrize("action", ["cancel", "suspend"])
def test_terminal_paper_controls_survive_snapshot_restore(
    controlled_repo: Path, action: str
) -> None:
    workspace = controlled_repo / "data/cache/terminal"
    store = TrackingStore(Jobs(workspace))
    monitor_id = monitor(store)
    claim = store.claim()
    assert claim is not None
    store.control(monitor_id, action)
    archived = store.get(monitor_id, export=True)
    assert archived is not None
    assert archived["cycles"][0]["status"] == "interrupted"
    archive = controlled_repo / "data/recovery/terminal.zip"
    snapshot(controlled_repo, workspace, archive)
    destination = controlled_repo / "data/cache/restored-terminal"
    restore(controlled_repo, archive, destination)
    reopened = TrackingStore(Jobs(destination))
    reopened.recover()
    assert reopened.get(monitor_id, export=True) == archived
    assert reopened.claim() is None
    with pytest.raises(ValueError, match=r"paused|terminal|cancel|suspend"):
        reopened.control(monitor_id, "resume")
    refused: dict[str, Any] = {"detail": "CONTROLLED late result", "submission_enabled": False}
    assert reopened.finish(monitor_id, claim[1], refused) is False


@pytest.mark.parametrize("damage", ["unknown_origin", "mixed_legacy_source", "terminal_running"])
def test_invalid_monitor_sources_and_terminal_cycles_fail_closed(
    controlled_repo: Path, damage: str
) -> None:
    workspace = controlled_repo / "data/cache/invalid-monitor"
    store = TrackingStore(Jobs(workspace))
    monitor_id = monitor(store)
    if damage == "terminal_running":
        assert store.claim() is not None
    with store.jobs.connect() as db:
        if damage == "unknown_origin":
            db.execute(
                "UPDATE monitors SET source_kind='unreviewed-import' WHERE id=?", (monitor_id,)
            )
        elif damage == "mixed_legacy_source":
            db.execute("UPDATE monitors SET research_job_id='unverified' WHERE id=?", (monitor_id,))
        else:
            db.execute("UPDATE monitors SET status='cancelled' WHERE id=?", (monitor_id,))
    before = dump(workspace / "jobs.sqlite")
    with pytest.raises(ValueError, match=r"source|origin|running"):
        validate_database(workspace)
    assert dump(workspace / "jobs.sqlite") == before


def test_frozen_paper_source_lookup_does_not_change_restored_research_database(
    controlled_repo: Path,
) -> None:
    workspace = controlled_repo / "data/cache/read-only-source"
    research = ResearchStore(workspace / "research")
    job_id, _ = research.create_job(
        ResearchRequest(objective="CONTROLLED source identity test", family="weather"),
        universe=("KXHIGHPHIL",),
        now=datetime(2026, 11, 16, tzinfo=UTC),
    )
    experiment_id = "sha256:" + "a" * 64
    result = {
        "experiment_id": experiment_id,
        "provenance": {"identity": {"spec": {"hypothesis_id": "controlled"}}},
    }
    root = workspace / "research/experiments" / experiment_id.replace("sha256:", "sha256-")
    root.mkdir(parents=True)
    (root / "results.json").write_text(json.dumps(result))
    (root / "checksums.json").write_text(
        json.dumps({"results.json": file_hash(root / "results.json")})
    )
    with research.connect() as db:
        db.execute(
            "INSERT INTO research_experiments "
            "(job_id,id,hypothesis_id,status,config,result,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                job_id,
                experiment_id,
                "controlled",
                "completed",
                "{}",
                json.dumps(result),
                "2026-11-16T00:00:00Z",
                "2026-11-16T00:00:00Z",
            ),
        )
        db.commit()
        # Recovery backup files deliberately use DELETE journal mode.
        db.execute("PRAGMA journal_mode=DELETE")
    path = workspace / "research/research.sqlite"
    before = path.read_bytes()
    assert _source(workspace, job_id, experiment_id)[1] == result
    assert path.read_bytes() == before
    assert not path.with_name("research.sqlite-wal").exists()


@pytest.fixture(scope="module")
def research_archive(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, str, dict[str, Any]]:
    repo = tmp_path_factory.mktemp("controlled-research-paper-recovery")
    for name in ("pyproject.toml", "uv.lock"):
        (repo / name).write_text("CONTROLLED paper recovery dependency identity: " + name)
    fixture = paper_fixture(repo / "data/cache/research-source")
    created = fixture.service.create(fixture.job_id, fixture.request)
    monitor_id = str(created["id"])
    fixture.tracking.control(monitor_id, "pause")
    original = fixture.tracking.get(monitor_id, export=True)
    assert original is not None
    with fixture.jobs.connect() as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    source_bytes = (fixture.jobs.root / "research/research.sqlite").read_bytes()
    archive = repo / "data/recovery/research-paper.zip"
    with patch(
        "entropytrade.ml.models.WeatherModel.load",
        side_effect=AssertionError("executable model loading forbidden during recovery"),
    ):
        counts = snapshot(repo, fixture.jobs.root, archive)
    assert counts["jobs"] == 0
    assert counts["monitors"] == 1
    assert (fixture.jobs.root / "research/research.sqlite").read_bytes() == source_bytes
    return repo, archive, monitor_id, original


def test_research_source_roundtrip_preserves_frozen_proof_without_legacy_job_rows(
    research_archive: tuple[Path, Path, str, dict[str, Any]],
) -> None:
    repo, archive, monitor_id, original = research_archive
    destination = repo / "data/cache/research-restored"
    with patch(
        "entropytrade.ml.models.WeatherModel.load",
        side_effect=AssertionError("executable model loading forbidden during recovery"),
    ):
        restore(repo, archive, destination)
    reopened = TrackingStore(Jobs(destination))
    reopened.recover()
    actual = reopened.get(monitor_id, export=True)
    assert actual is not None
    assert actual == original
    assert actual["source_kind"] == "autonomous_research"
    assert actual["source_ref"]["eligibility"]["data_kind"] == "synthetic"
    assert actual["submission_enabled"] is False
    with reopened.jobs.connect() as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    # The copied ResearchStore source remains independently verifiable without reopening
    # an experiment runner, provider, collector, or fitted Python object.
    before = (destination / "research/research.sqlite").read_bytes()
    assert validate_database(destination)["monitors"] == 1
    assert (destination / "research/research.sqlite").read_bytes() == before


@pytest.mark.parametrize("damage", ["source_database", "portable_model", "source_hash"])
def test_corrupt_research_origin_is_refused_after_restore(
    research_archive: tuple[Path, Path, str, dict[str, Any]], damage: str
) -> None:
    repo, archive, monitor_id, original = research_archive
    destination = repo / ("data/cache/corrupt-" + damage)
    restore(repo, archive, destination)
    if damage == "source_database":
        with sqlite3.connect(destination / "research/research.sqlite") as db:
            db.execute("UPDATE research_experiments SET result='{}'")
    elif damage == "portable_model":
        experiment_id = original["experiment_id"].replace("sha256:", "sha256-")
        model = destination / "research/experiments" / experiment_id / "ridge.paper.json"
        model.write_bytes(model.read_bytes() + b" ")
    else:
        with sqlite3.connect(destination / "jobs.sqlite") as db:
            db.execute("UPDATE monitors SET source_ref='{}' WHERE id=?", (monitor_id,))
    with pytest.raises(ValueError, match=r"reference|hash|report|checksum|experiment"):
        validate_database(destination)
