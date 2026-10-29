"""Offline proof refuses unsafe/busy inputs before store construction or migration."""

import json
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, validate_database
from entropytrade.api.recovery_proof import verify_recovery
from entropytrade.api.workspace import acquire_workspace, workspace_lease
from entropytrade.data.sources import file_hash
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_tracking import monitor
from tests.unit.test_workspace_recovery import repo as repo


def forbid_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("refused source must not initialize or migrate an application store")

    monkeypatch.setattr("entropytrade.api.recovery_proof.Jobs", unexpected)
    monkeypatch.setattr("entropytrade.api.recovery_proof.TrackingStore", unexpected)


def contents(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("legacy", [False, True])
def test_busy_source_proof_never_creates_or_migrates_stores(
    repo: Path, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    root = repo / "data/cache/source"
    if legacy:
        store = TrackingStore(Jobs(root))
        with store.jobs.connect() as db:
            db.execute("ALTER TABLE monitors DROP COLUMN model_binding")
    forbid_stores(monkeypatch)
    with workspace_lease(root):
        before = contents(root)
        with pytest.raises((BlockingIOError, ValueError), match=r"unavailable|no database"):
            verify_recovery(repo, root, repo / "data/cache/restored", repo / "proof")
        assert contents(root) == before
    assert not (repo / "proof/workspace.zip").exists()
    assert not (repo / "data/cache/restored").exists()
    assert json.loads((repo / "proof/verification.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("case", ["missing", "empty", "out-of-cache", "outside-legacy", "legacy"])
def test_invalid_source_proof_cannot_create_or_migrate_database(
    repo: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    root = repo / ("data/source" if case.startswith(("out", "outside")) else "data/cache/source")
    if case in {"empty", "out-of-cache"}:
        root.mkdir(parents=True)
    if case in {"outside-legacy", "legacy"}:
        store = TrackingStore(Jobs(root))
        with store.jobs.connect() as db:
            db.execute("ALTER TABLE monitors DROP COLUMN model_binding")
    before = contents(root)
    forbid_stores(monkeypatch)
    with pytest.raises(ValueError, match=r"data/cache|no database|columns"):
        verify_recovery(repo, root, repo / "data/cache/restored", repo / "proof")
    # A read-only SQLite WAL backup can create runtime sidecars for an existing valid
    # source. Its authoritative database must remain byte-identical and unmigrated.
    after = contents(root)
    runtime = {".writer.lock", "jobs.sqlite-wal", "jobs.sqlite-shm"} if case == "legacy" else set()
    assert {k: v for k, v in after.items() if k not in runtime} == before
    if case == "missing":
        assert not root.exists()
    assert not (repo / "proof/workspace.zip").exists()
    assert not (repo / "data/cache/restored").exists()


def test_source_and_restored_leases_cover_snapshot_inspection_comparison_and_recovery(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, destination = repo / "data/cache/source", repo / "data/cache/restored"
    store = TrackingStore(Jobs(root))
    paused = monitor(store)
    store.control(paused, "pause")
    evidence = root / "runs/original.json"
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text('{"CONTROLLED":"original bytes and clocks"}')
    original = store.get(paused, export=True)
    checks: list[str] = []

    def held(path: Path) -> None:
        with pytest.raises(BlockingIOError):
            acquire_workspace(path)

    def checked_jobs(path: Path) -> Jobs:
        held(root)
        held(path)
        checks.append("initialize:" + path.name)
        return Jobs(path)

    def checked_validation(path: Path) -> dict[str, int]:
        held(root)
        checks.append("validate:" + path.name)
        return validate_database(path)

    def checked_hash(path: Path) -> str:
        held(root)
        if path.is_relative_to(destination):
            held(destination)
            checks.append("compare:restored")
        elif path.is_relative_to(root):
            checks.append("compare:source")
        return file_hash(path)

    recover_jobs, recover_tracking = Jobs.recover, TrackingStore.recover

    def checked_recover_jobs(jobs: Jobs) -> None:
        held(root)
        held(destination)
        checks.append("recover:jobs")
        recover_jobs(jobs)

    def checked_recover_tracking(tracking: TrackingStore) -> None:
        held(root)
        held(destination)
        checks.append("recover:tracking")
        recover_tracking(tracking)

    monkeypatch.setattr("entropytrade.api.recovery_proof.Jobs", checked_jobs)
    monkeypatch.setattr("entropytrade.api.recovery_proof.file_hash", checked_hash)
    monkeypatch.setattr("entropytrade.api.recovery.validate_database", checked_validation)
    monkeypatch.setattr(Jobs, "recover", checked_recover_jobs)
    monkeypatch.setattr(TrackingStore, "recover", checked_recover_tracking)
    verify_recovery(repo, root, destination, repo / "proof")
    assert set(checks) >= {
        "initialize:source",
        "initialize:restored",
        "validate:payload",
        "validate:workspace",
        "compare:source",
        "compare:restored",
        "recover:jobs",
        "recover:tracking",
    }
    assert store.get(paused, export=True) == original
    assert (destination / evidence.relative_to(root)).read_bytes() == evidence.read_bytes()
    assert json.loads((repo / "proof/verification.json").read_text())["status"] == "passed"
    with workspace_lease(root), workspace_lease(destination):
        pass


def test_busy_restored_workspace_is_not_initialized_and_source_lease_releases(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, destination = repo / "data/cache/source", repo / "data/cache/restored"
    TrackingStore(Jobs(root))
    locks = []
    restored_bytes: dict[str, bytes] = {}

    def busy_restore(repo: Path, archive: Path, workspace: Path) -> dict[str, Any]:
        receipt = restore(repo, archive, workspace)
        locks.append(acquire_workspace(workspace))
        restored_bytes.update(contents(workspace))
        return receipt

    def checked_jobs(path: Path) -> Jobs:
        assert path == root, "busy restored workspace must not initialize stores"
        return Jobs(path)

    monkeypatch.setattr("entropytrade.api.recovery_proof.restore", busy_restore)
    monkeypatch.setattr("entropytrade.api.recovery_proof.Jobs", checked_jobs)
    try:
        with pytest.raises(BlockingIOError):
            verify_recovery(repo, root, destination, repo / "proof")
        assert contents(destination) == restored_bytes
        with workspace_lease(root):
            pass
    finally:
        for lock in locks:
            lock.close()
