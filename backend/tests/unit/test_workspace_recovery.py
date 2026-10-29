"""CONTROLLED recovery evidence. Fixtures are never empirical models or receipts."""

import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile, ZipInfo

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.api.workspace import workspace_lease
from entropytrade.data.sources import file_hash
from entropytrade.tracking.evaluate import evaluate
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations
from tests.unit.test_tracking import monitor, ready
from tests.unit.test_tracking_models import inputs, saved_model


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED lock identity: " + name)
    return tmp_path


def populated(repo: Path) -> tuple[TrackingStore, str, str, str]:
    store = TrackingStore(Jobs(repo / "data/cache/original"))
    spec, _data, _markets, model = inputs()
    paused = store.create(saved_model(store, spec, model))
    claim = store.claim()
    assert claim is not None
    assert claim[0] == paused
    root = store.jobs.root / "shadow" / paused / claim[1]
    root.mkdir(parents=True)
    (root / "receipt.json").write_text('{"CONTROLLED":true,"received_at":"2026-10-26T12:00:00Z"}')
    artifact = {
        "path": "receipt.json",
        "bytes": (root / "receipt.json").stat().st_size,
        "sha256": file_hash(root / "receipt.json"),
    }
    decision_spec, data, bundle, fee = ready()
    decisions = evaluate(decision_spec, data, bundle, fee=fee)
    assert decisions[0]["status"] == "shadow_eligible"
    result = {
        "detail": "CONTROLLED completed cycle",
        "artifacts": [artifact],
        "submission_enabled": False,
        "decisions": decisions,
    }
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    assert store.finish(paused, claim[1], result)
    store.control(paused, "pause")
    active = monitor(store)
    running = store.claim()
    assert running is not None
    assert running[0] == active
    partial = store.jobs.root / "shadow" / active / running[1]
    partial.mkdir(parents=True)
    (partial / "partial.json").write_text('{"CONTROLLED":"unfinished original receipt"}')
    unfinished = store.jobs.create(
        {"idea": "CONTROLLED queued", "family": "weather", "mode": "recorded"}
    )
    return store, paused, active, unfinished


def test_snapshot_restore_preserves_models_bytes_reservations_and_recovers_fresh_cycle(
    repo: Path,
) -> None:
    store, paused, active, unfinished = populated(repo)
    original = store.get(paused, export=True)
    assert original is not None
    held = reservations(original)
    assert held
    files = {
        p.relative_to(store.jobs.root): p.read_bytes()
        for folder in ("runs", "shadow")
        for p in (store.jobs.root / folder).rglob("*")
        if p.is_file()
    }
    archive = repo / "data/recovery/workspace.zip"
    result = snapshot(repo, store.jobs.root, archive)
    assert result["monitors"] == 2
    assert result["cycles"] == 2
    destination = repo / "data/cache/restored"
    assert restore(repo, archive, destination)["archive_sha256"] == file_hash(archive)
    reopened = TrackingStore(Jobs(destination))
    assert reopened.get(paused, export=True) == original
    assert all((destination / name).read_bytes() == content for name, content in files.items())
    reopened.jobs.recover()
    reopened.recover()
    assert reopened.get(paused, export=True) == original
    assert reservations(reopened.get(paused, export=True)) == held  # type: ignore[arg-type]
    spec, data, bundle, fee = ready()
    assert evaluate(spec, data, bundle, fee=fee, reservations=held)[0]["intent"] is None
    assert reopened.jobs.get(unfinished)["status"] == "interrupted"  # type: ignore[index]
    recovered = reopened.get(active, export=True)
    assert recovered is not None
    assert recovered["status"] == "active"
    assert recovered["cycles"][0]["status"] == "interrupted"
    old_id = recovered["cycles"][0]["id"]
    new_claim = reopened.claim()
    assert new_claim is not None
    assert new_claim[0] == active
    assert new_claim[1] != old_id
    assert not (destination / "shadow" / active / new_claim[1]).exists()
    assert reopened.get(active)["cycles"][0]["sequence"] == 2  # type: ignore[index]
    assert all((destination / name).read_bytes() == content for name, content in files.items())
    # Restore is repeatable into another new destination and does not mutate its archive.
    digest = file_hash(archive)
    restore(repo, archive, repo / "data/cache/second")
    assert file_hash(archive) == digest
    assert store.get(paused, export=True) == original


def rewrite(archive: Path, output: Path, change: str) -> None:
    with ZipFile(archive) as source:
        contents = {n: source.read(n) for n in source.namelist()}
    manifest: dict[str, Any] = json.loads(contents["manifest.json"])
    receipt = next(f for f in manifest["files"] if f["path"].endswith("receipt.json"))
    if change == "checksum":
        contents["files/" + receipt["path"]] = b"x" * receipt["bytes"]
    elif change == "missing":
        del contents["files/" + receipt["path"]]
    elif change == "missing-indexed":
        del contents["files/" + receipt["path"]]
        manifest["files"].remove(receipt)
    elif change in {"binding", "spec", "cycle", "orphan", "sequence", "schema"}:
        db_file = output.with_suffix(".sqlite")
        db_file.write_bytes(contents["files/jobs.sqlite"])
        with sqlite3.connect(db_file) as db:
            if change == "binding":
                db.execute("UPDATE monitors SET model_binding='{}'")
            elif change == "spec":
                db.execute("UPDATE monitors SET spec_hash='tampered'")
            elif change == "cycle":
                db.execute("UPDATE shadow_cycles SET digest='tampered' WHERE result IS NOT NULL")
            elif change == "orphan":
                db.execute("DELETE FROM jobs")
            elif change == "sequence":
                db.execute("UPDATE shadow_cycles SET sequence=3")
            elif change == "schema":
                db.execute("DROP TABLE shadow_contracts")
        db.close()
        contents["files/jobs.sqlite"] = db_file.read_bytes()
        db_entry = next(f for f in manifest["files"] if f["path"] == "jobs.sqlite")
        db_entry.update(bytes=db_file.stat().st_size, sha256=file_hash(db_file))
    elif change == "path":
        contents["files/../../escape"] = b"never extracted"
    elif change == "symlink":
        pass
    elif change == "application":
        manifest["application"]["uv.lock"] = "wrong lock"
    elif change == "size":
        receipt["bytes"] = 2**40
    elif change == "not-database":
        contents["files/jobs.sqlite"] = b"not sqlite"
    else:
        raise AssertionError(change)
    contents["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(output, "w") as target:
        for name, body in contents.items():
            target.writestr(name, body)
        if change == "symlink":
            info = ZipInfo("files/link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            target.writestr(info, "../../escape")


@pytest.mark.parametrize(
    "change",
    [
        "checksum",
        "missing",
        "missing-indexed",
        "binding",
        "spec",
        "cycle",
        "orphan",
        "sequence",
        "schema",
        "path",
        "symlink",
        "application",
        "size",
        "not-database",
    ],
)
def test_corrupt_incomplete_or_unsafe_restore_never_publishes(repo: Path, change: str) -> None:
    store, _paused, _active, _unfinished = populated(repo)
    archive = repo / "snapshot.zip"
    snapshot(repo, store.jobs.root, archive)
    corrupt = repo / "corrupt.zip"
    rewrite(archive, corrupt, change)
    destination = repo / "data/cache/refused"
    with pytest.raises(
        ValueError, match=r"snapshot|restored|evidence|cycle|workspace|path|binding"
    ):
        restore(repo, corrupt, destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".restore-*"))
    assert not (repo / "data/escape").exists()


def test_lock_no_overwrite_symlinks_and_missing_source_fail_closed(repo: Path) -> None:
    store, _paused, _active, _unfinished = populated(repo)
    archive = repo / "snapshot.zip"
    with workspace_lease(store.jobs.root), pytest.raises(BlockingIOError):
        snapshot(repo, store.jobs.root, archive)
    assert not archive.exists()
    snapshot(repo, store.jobs.root, archive)
    before = file_hash(archive)
    with pytest.raises(ValueError, match="new archive"):
        snapshot(repo, store.jobs.root, archive)
    assert file_hash(archive) == before
    with pytest.raises(ValueError, match="new workspace"):
        restore(repo, archive, store.jobs.root)
    with pytest.raises(ValueError, match="no database"):
        snapshot(repo, repo / "data/cache/missing", repo / "missing.zip")
    assert not (repo / "data/cache/missing").exists()
    (store.jobs.root / "runs/link").symlink_to(repo / "uv.lock")
    with pytest.raises(ValueError, match="link"):
        snapshot(repo, store.jobs.root, repo / "linked.zip")
    (repo / "data/cache/link").symlink_to(store.jobs.root, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        restore(repo, archive, repo / "data/cache/link/restored")
    with pytest.raises(ValueError, match="repository"):
        restore(repo, archive, repo.parent / "escape")


def test_snapshot_rejects_existing_corrupt_artifact_without_publishing(repo: Path) -> None:
    store, paused, _active, _unfinished = populated(repo)
    saved = store.get(paused)
    assert saved is not None
    cycle = saved["cycles"][0]["id"]
    (store.jobs.root / "shadow" / paused / cycle / "receipt.json").write_text("corrupt")
    with pytest.raises(ValueError, match="corrupt evidence"):
        snapshot(repo, store.jobs.root, repo / "refused.zip")
    assert not (repo / "refused.zip").exists()


def test_duplicate_archive_members_are_refused(repo: Path) -> None:
    archive = repo / "duplicate.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", "{}")
        with pytest.warns(UserWarning, match="Duplicate name"):
            bundle.writestr("manifest.json", "{}")
    with pytest.raises(ValueError, match="duplicate"):
        restore(repo, archive, repo / "data/cache/refused")


def test_server_cannot_open_or_migrate_database_without_workspace_lease(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.api.server import WorkbenchServer

    root = repo / "data/cache/locked"

    def unexpected(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("locked maintenance must prevent database initialization")

    monkeypatch.setattr("entropytrade.api.server.Jobs", unexpected)
    with workspace_lease(root), pytest.raises(BlockingIOError):
        WorkbenchServer(repo, root, port=0)
    assert not (root / "jobs.sqlite").exists()


def test_worker_retains_exclusive_lease_after_parent_closes_it(repo: Path) -> None:
    from entropytrade.api.workspace import acquire_workspace

    root = repo / "data/cache/inherited"
    lock = acquire_workspace(root)
    # The server's runners pass this exact file description to fixed worker modules.
    # Pipes keep a real child alive without requiring network/asyncio permissions.
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        pass_fds=(lock.fileno(),),
    ) as child:
        lock.close()
        with pytest.raises(BlockingIOError):
            acquire_workspace(root)
        assert child.stdin is not None
        child.stdin.write(b"x")
        child.stdin.flush()
        child.wait(timeout=10)
    with workspace_lease(root):
        pass


def test_lineage_registry_is_restored_and_missing_research_lineage_is_refused(repo: Path) -> None:
    from entropytrade.strategy_registry.store import Registry

    store, _paused, _active, _unfinished = populated(repo)
    registry = Registry(store.jobs.root / "registry.sqlite")
    registry.record_experiment("CONTROLLED-experiment", "{}", 1, "synthetic")
    registry.close()
    with sqlite3.connect(store.jobs.root / "registry.sqlite") as db:
        db.execute("INSERT INTO agent_research_runs VALUES ('CONTROLLED-run', '{}')")
    db.close()
    job = store.jobs.create({"idea": "CONTROLLED review", "family": "weather", "mode": "recorded"})
    result = {
        "schema": "workbench-review-v1",
        "experiment_id": "CONTROLLED-experiment",
        "research_run": "CONTROLLED-run",
        "artifacts": [],
    }
    review = store.jobs.root / "runs" / job / "review.json"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps(result))
    store.jobs.update(job, "completed", "CONTROLLED", status="completed", result=result)
    archive = repo / "registry.zip"
    snapshot(repo, store.jobs.root, archive)
    destination = repo / "data/cache/registry-restored"
    restore(repo, archive, destination)
    with sqlite3.connect(destination / "registry.sqlite") as restored_db:
        assert restored_db.execute("SELECT * FROM agent_research_runs").fetchall() == [
            ("CONTROLLED-run", "{}")
        ]
    restored_db.close()
    # Updating the outer manifest cannot conceal absent registry evidence.
    with ZipFile(archive) as bundle:
        contents = {n: bundle.read(n) for n in bundle.namelist() if n != "files/registry.sqlite"}
    manifest = json.loads(contents["manifest.json"])
    manifest["files"] = [f for f in manifest["files"] if f["path"] != "registry.sqlite"]
    contents["manifest.json"] = json.dumps(manifest).encode()
    corrupt = repo / "missing-registry.zip"
    with ZipFile(corrupt, "w") as bundle:
        for name, content in contents.items():
            bundle.writestr(name, content)
    with pytest.raises(ValueError, match="lineage registry"):
        restore(repo, corrupt, repo / "data/cache/missing-registry")
    (store.jobs.root / "registry.sqlite").unlink()
    with pytest.raises(ValueError, match="lineage registry"):
        snapshot(repo, store.jobs.root, repo / "missing-registry-source.zip")


def test_installed_cli_round_trip_uses_workspace_and_archive_in_both_directions() -> None:
    from entropytrade.api.runner import worker_environment

    project = Path(__file__).resolve().parents[3]
    cache = project / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="recovery-cli-", dir=cache) as name:
        root = Path(name)
        original = root / "original"
        TrackingStore(Jobs(original))
        archive = root / "workspace.zip"
        destination = root / "restored"
        for action, workspace in (("snapshot", original), ("restore", destination)):
            process = subprocess.run(  # noqa: S603 - fixed module/paths, no shell
                [
                    sys.executable,
                    "-m",
                    "entropytrade.api.recovery",
                    action,
                    "--workspace",
                    str(workspace),
                    "--archive",
                    str(archive),
                ],
                cwd=project,
                env=worker_environment(project, root),
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            result = json.loads(process.stdout)
            assert result["jobs"] == 0
            assert result["submission_enabled"] is False
        assert TrackingStore(Jobs(destination)).history() == []


def test_snapshot_refuses_directory_and_manifest_budgets_before_publish(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _paused, _active, _unfinished = populated(repo)
    monkeypatch.setattr("entropytrade.api.recovery.MAX_FILES", 1)
    with pytest.raises(ValueError, match="budget"):
        snapshot(repo, store.jobs.root, repo / "directory-budget.zip")
    assert not (repo / "directory-budget.zip").exists()
    monkeypatch.setattr("entropytrade.api.recovery.MAX_FILES", 100_000)
    monkeypatch.setattr("entropytrade.api.recovery.MAX_MANIFEST_BYTES", 1)
    with pytest.raises(ValueError, match="manifest budget"):
        snapshot(repo, store.jobs.root, repo / "manifest-budget.zip")
    assert not (repo / "manifest-budget.zip").exists()
