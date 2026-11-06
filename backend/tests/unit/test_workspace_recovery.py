"""CONTROLLED recovery evidence. Fixtures are never empirical models or receipts."""

import json
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import LEGACY_SCHEMA, SCHEMA, blob_member, restore, snapshot
from entropytrade.api.workspace import workspace_lease
from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import StrategySpec
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.evaluate import evaluate
from entropytrade.tracking.models import score
from entropytrade.tracking.replay import decision_inputs, reproduce
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations
from tests.unit.test_tracking import forbid_shadow_execution, monitor, ready
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


def test_migrated_legacy_null_bindings_survive_recovery_without_enabling_scoring(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, paused, active, unfinished = populated(repo)
    # Recreate the supported schema before frozen bindings existed, keeping the
    # model reference/export and completed/partial evidence already on disk.
    with store.jobs.connect() as db:
        db.execute("ALTER TABLE monitors DROP COLUMN model_binding")
        legacy = [dict(row) for row in db.execute("SELECT * FROM monitors ORDER BY id")]

    def unexpected(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("legacy recovery must not invent a model binding")

    monkeypatch.setattr("entropytrade.tracking.store.freeze_binding", unexpected)
    forbid_shadow_execution(monkeypatch)
    migrated = TrackingStore(store.jobs)
    with migrated.jobs.connect() as db:
        assert [dict(row) for row in db.execute("SELECT * FROM monitors ORDER BY id")] == [
            {**row, "model_binding": None} for row in legacy
        ]
        original_sql = list(db.iterdump())
    original = migrated.get(paused, export=True)
    original_active = migrated.get(active, export=True)
    assert original is not None
    assert original_active is not None
    assert original["spec"]["model_ref"] is not None
    assert list((store.jobs.root / "runs").rglob("*.forward.json"))
    files = {
        p.relative_to(store.jobs.root): p.read_bytes()
        for folder in ("runs", "shadow")
        for p in (store.jobs.root / folder).rglob("*")
        if p.is_file()
    }
    _, data, markets, _model = inputs()
    _, _, _, fee = ready()

    def assert_blocked(value: dict[str, Any]) -> None:
        assert value["model_binding"] is None
        spec = StrategySpec.model_validate(value["spec"])
        bundle = score(spec, data, value["model_binding"], markets)
        assert bundle.records == ()
        assert bundle.refusals == {"model": "No frozen model binding"}
        rows = evaluate(spec, data, bundle, fee=fee)
        assert len(rows) == 1
        assert rows[0]["status"] == "blocked"
        assert rows[0]["prediction"] is rows[0]["intent"] is rows[0]["risk"] is None
        assert "point_in_time_prediction" in rows[0]["reasons"]
        replay = json.loads(json.dumps(decision_inputs(spec, data, bundle, fee=fee)))
        assert reproduce(replay) == rows

    assert_blocked(original)
    archive = repo / "legacy.zip"
    assert snapshot(repo, store.jobs.root, archive)["monitors"] == 2
    archive_hash = file_hash(archive)
    destination = repo / "data/cache/legacy-restored"
    assert restore(repo, archive, destination)["archive_sha256"] == archive_hash
    reopened = TrackingStore(Jobs(destination))
    with reopened.jobs.connect() as db:
        assert list(db.iterdump()) == original_sql
    assert reopened.get(paused, export=True) == original
    assert reopened.get(active, export=True) == original_active
    assert all((destination / name).read_bytes() == content for name, content in files.items())

    # These are the same recovery calls used at server startup, without a listener.
    reopened.jobs.recover()
    reopened.recover()
    current = reopened.get(paused, export=True)
    assert current == original
    assert_blocked(current)
    recovered = reopened.get(active, export=True)
    assert recovered is not None
    assert {k: v for k, v in recovered.items() if k not in {"cycles", "events"}} == {
        k: v for k, v in original_active.items() if k not in {"cycles", "events"}
    }
    assert recovered["events"][:-1] == original_active["events"]
    assert recovered["cycles"][0]["status"] == "interrupted"
    assert recovered["cycles"][0]["started_at"] == original_active["cycles"][0]["started_at"]
    assert reopened.jobs.get(unfinished)["status"] == "interrupted"  # type: ignore[index]
    reopened.jobs.recover()
    reopened.recover()
    assert reopened.get(active, export=True) == recovered
    fresh = reopened.claim()
    assert fresh is not None
    assert fresh[0] == active
    assert fresh[1] != original_active["cycles"][0]["id"]
    assert not (destination / "shadow" / active / fresh[1]).exists()
    reopened.control(paused, "resume")
    resumed = reopened.get(paused, export=True)
    assert resumed is not None
    assert resumed["status"] == "active"
    assert_blocked(resumed)
    with reopened.jobs.connect() as db:
        assert all(row[0] is None for row in db.execute("SELECT model_binding FROM monitors"))
    assert all((destination / name).read_bytes() == content for name, content in files.items())
    with store.jobs.connect() as db:
        assert list(db.iterdump()) == original_sql
    assert file_hash(archive) == archive_hash


def rewrite(archive: Path, output: Path, change: str, *, model_binding: str = "{}") -> None:
    with ZipFile(archive) as source:
        contents = {n: source.read(n) for n in source.namelist()}
    manifest: dict[str, Any] = json.loads(contents["manifest.json"])
    receipt = next(f for f in manifest["files"] if f["path"].endswith("receipt.json"))
    if change == "checksum":
        contents[blob_member(receipt["sha256"])] = b"x" * receipt["bytes"]
    elif change == "missing":
        del contents[blob_member(receipt["sha256"])]
    elif change == "missing-indexed":
        del contents[blob_member(receipt["sha256"])]
        manifest["files"].remove(receipt)
    elif change in {"binding", "spec", "cycle", "orphan", "sequence", "schema"}:
        db_entry = next(f for f in manifest["files"] if f["path"] == "jobs.sqlite")
        db_file = output.with_suffix(".sqlite")
        db_file.write_bytes(contents.pop(blob_member(db_entry["sha256"])))
        with sqlite3.connect(db_file) as db:
            if change == "binding":
                db.execute("UPDATE monitors SET model_binding=?", (model_binding,))
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
        db_entry.update(bytes=db_file.stat().st_size, sha256=file_hash(db_file))
        contents[blob_member(db_entry["sha256"])] = db_file.read_bytes()
    elif change == "path":
        contents["files/../../escape"] = b"never extracted"
    elif change == "symlink":
        pass
    elif change == "application":
        manifest["application"]["uv.lock"] = "wrong lock"
    elif change == "size":
        receipt["bytes"] = 2**40
    elif change == "not-database":
        db_entry = next(f for f in manifest["files"] if f["path"] == "jobs.sqlite")
        contents[blob_member(db_entry["sha256"])] = b"not sqlite"
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


@pytest.mark.parametrize(
    "value",
    ["", "null", "false", "0", '""', "[]", "{}", "{", "invalid-status", "blocked-snapshot"],
)
def test_non_null_malformed_bindings_are_refused_by_snapshot_and_restore(
    repo: Path, value: str
) -> None:
    store, _paused, _active, _unfinished = populated(repo)
    archive = repo / "valid.zip"
    snapshot(repo, store.jobs.root, archive)
    if value in {"invalid-status", "blocked-snapshot"}:
        binding: dict[str, Any] = {
            "status": "invalid" if value == "invalid-status" else "blocked",
            "snapshot": None if value == "invalid-status" else {},
        }
        binding["binding_hash"] = scientific_hash(binding)
        value = json.dumps(binding)
    corrupt = repo / "malformed-binding.zip"
    rewrite(archive, corrupt, "binding", model_binding=value)
    destination = repo / "data/cache/refused-binding"
    with pytest.raises(ValueError, match=r"binding|Expecting"):
        restore(repo, corrupt, destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".restore-*"))
    with store.jobs.connect() as db:
        db.execute("UPDATE monitors SET model_binding=?", (value,))
    refused = repo / "refused-binding.zip"
    with pytest.raises(ValueError, match=r"binding|Expecting"):
        snapshot(repo, store.jobs.root, refused)
    assert not refused.exists()
    assert not list(repo.glob(".snapshot-*"))


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


def test_snapshots_are_deflated_and_stored_legacy_archives_still_restore(repo: Path) -> None:
    store, *_ = populated(repo)
    archive = repo / "snapshot.zip"
    snapshot(repo, store.jobs.root, archive)
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        manifest = json.loads(bundle.read("manifest.json"))
        assert {m.compress_type for m in members} == {ZIP_DEFLATED}
        assert sum(m.compress_size for m in members) < sum(m.file_size for m in members)
        contents = {m.filename: bundle.read(m) for m in members}
    expected = {f["path"]: f["sha256"] for f in manifest["files"]}

    # Chained workspaces published before compression must remain restorable.
    legacy = repo / "legacy.zip"
    with ZipFile(legacy, "w", compression=ZIP_STORED) as bundle:
        for name, body in contents.items():
            bundle.writestr(name, body)
    for name, source in (("deflated", archive), ("stored", legacy)):
        restored = repo / "data/cache" / name
        restore(repo, source, restored)
        actual = {
            p.relative_to(restored).as_posix(): file_hash(p)
            for p in restored.rglob("*")
            if p.is_file() and p.name not in {"jobs.sqlite", "registry.sqlite"}
        }
        assert actual == {k: v for k, v in expected.items() if not k.endswith(".sqlite")}

    unsupported = repo / "bzip2.zip"
    with ZipFile(unsupported, "w", compression=ZIP_BZIP2) as bundle:
        for name, body in contents.items():
            bundle.writestr(name, body)
    with pytest.raises(ValueError, match="regular files"):
        restore(repo, unsupported, repo / "data/cache/refused")
    assert not (repo / "data/cache/refused").exists()


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
        contents = {n: bundle.read(n) for n in bundle.namelist()}
    manifest = json.loads(contents["manifest.json"])
    registry = next(f for f in manifest["files"] if f["path"] == "registry.sqlite")
    del contents[blob_member(registry["sha256"])]
    manifest["files"].remove(registry)
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


def duplicated(repo: Path) -> TrackingStore:
    """CONTROLLED workspace whose immutable dataset copies a shadow receipt byte for byte."""
    store, paused, _active, _unfinished = populated(repo)
    cycle = next((store.jobs.root / "shadow" / paused).iterdir())
    dataset = store.jobs.root / "runs/controlled-copy/shadow/digest"
    dataset.mkdir(parents=True)
    for name in ("receipt.json", "result.json"):
        (dataset / name).write_bytes((cycle / name).read_bytes())
    # Equal content at unrelated paths is also stored once; empty files are distinct paths.
    (store.jobs.root / "runs/controlled-copy/empty-1.json").write_bytes(b"")
    (store.jobs.root / "runs/controlled-copy/empty-2.json").write_bytes(b"")
    return store


def test_snapshot_stores_each_distinct_content_once_and_restores_independent_files(
    repo: Path,
) -> None:
    store = duplicated(repo)
    archive = repo / "snapshot.zip"
    snapshot(repo, store.jobs.root, archive)
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest = json.loads(bundle.read("manifest.json"))
    files = manifest["files"]
    digests = {f["sha256"] for f in files}
    assert manifest["schema"] == SCHEMA
    assert len(digests) < len(files)  # the dataset copies really are duplicates
    assert sorted(names) == sorted(["manifest.json", *map(blob_member, digests)])

    destination = repo / "data/cache/restored"
    restore(repo, archive, destination)
    for item in files:
        assert file_hash(destination / item["path"]) == item["sha256"]
    copy = destination / "runs/controlled-copy/shadow/digest/receipt.json"
    original = next(destination.glob("shadow/*/*/receipt.json"))
    assert copy.read_bytes() == original.read_bytes()
    # Every path is its own file: no hard links, so a later write cannot alter another record.
    assert copy.stat().st_nlink == original.stat().st_nlink == 1
    assert copy.stat().st_ino != original.stat().st_ino
    copy.write_text("CONTROLLED overwrite")
    assert file_hash(original) == next(
        f["sha256"]
        for f in files
        if f["path"].endswith(original.relative_to(destination).as_posix())
    )
    assert (destination / "runs/controlled-copy/empty-2.json").read_bytes() == b""


def test_legacy_per_path_archives_still_restore_within_their_original_budget(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = duplicated(repo)
    archive = repo / "snapshot.zip"
    snapshot(repo, store.jobs.root, archive)
    with ZipFile(archive) as bundle:
        contents = {n: bundle.read(n) for n in bundle.namelist()}
    manifest = json.loads(contents.pop("manifest.json"))
    manifest["schema"] = LEGACY_SCHEMA
    legacy = repo / "legacy.zip"
    with ZipFile(legacy, "w", compression=ZIP_STORED) as bundle:
        bundle.writestr("manifest.json", json.dumps(manifest))
        for item in manifest["files"]:
            bundle.writestr("files/" + item["path"], contents[blob_member(item["sha256"])])
    restore(repo, legacy, repo / "data/cache/legacy")
    for item in manifest["files"]:
        assert file_hash(repo / "data/cache/legacy" / item["path"]) == item["sha256"]

    # A v1 archive was always bounded by expanded bytes; that bound is unchanged for it,
    # while a v2 archive of the same workspace is bounded by distinct bytes.
    expanded = sum(f["bytes"] for f in manifest["files"])
    distinct = sum({f["sha256"]: f["bytes"] for f in manifest["files"]}.values())
    assert distinct < expanded
    monkeypatch.setattr("entropytrade.api.recovery.MAX_BYTES", distinct)
    with pytest.raises(ValueError, match="size budget"):
        restore(repo, legacy, repo / "data/cache/legacy-over")
    assert not (repo / "data/cache/legacy-over").exists()
    restore(repo, archive, repo / "data/cache/v2-within")


def test_snapshot_budgets_count_distinct_and_expanded_bytes_separately(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = duplicated(repo)
    archive = repo / "baseline.zip"
    snapshot(repo, store.jobs.root, archive)
    with ZipFile(archive) as bundle:
        files = json.loads(bundle.read("manifest.json"))["files"]
    expanded = sum(f["bytes"] for f in files)
    distinct = sum({f["sha256"]: f["bytes"] for f in files}.values())
    monkeypatch.setattr("entropytrade.api.recovery.MAX_BYTES", distinct)
    snapshot(repo, store.jobs.root, repo / "distinct-exact.zip")
    monkeypatch.setattr("entropytrade.api.recovery.MAX_BYTES", distinct - 1)
    with pytest.raises(ValueError, match="size budget"):
        snapshot(repo, store.jobs.root, repo / "distinct-over.zip")
    assert not (repo / "distinct-over.zip").exists()
    with pytest.raises(ValueError, match="size budget"):
        restore(repo, archive, repo / "data/cache/distinct-over")
    monkeypatch.setattr("entropytrade.api.recovery.MAX_BYTES", distinct)
    monkeypatch.setattr("entropytrade.api.recovery.MAX_EXPANDED_BYTES", expanded - 1)
    with pytest.raises(ValueError, match="size budget"):
        snapshot(repo, store.jobs.root, repo / "expanded-over.zip")
    assert not (repo / "expanded-over.zip").exists()
    with pytest.raises(ValueError, match="size budget"):
        restore(repo, archive, repo / "data/cache/expanded-over")
    assert not list((repo / "data/cache").glob("*-over"))


@pytest.mark.parametrize("digest", ["sha256:../../escape", "md5:" + "0" * 64, "sha256:" + "G" * 64])
def test_archive_members_must_be_named_by_a_valid_content_digest(repo: Path, digest: str) -> None:
    store = duplicated(repo)
    archive = repo / "snapshot.zip"
    snapshot(repo, store.jobs.root, archive)
    with ZipFile(archive) as bundle:
        contents = {n: bundle.read(n) for n in bundle.namelist()}
    manifest = json.loads(contents["manifest.json"])
    manifest["files"][0]["sha256"] = digest
    contents["manifest.json"] = json.dumps(manifest).encode()
    corrupt = repo / "corrupt.zip"
    with ZipFile(corrupt, "w") as bundle:
        for name, body in contents.items():
            bundle.writestr(name, body)
    with pytest.raises(ValueError, match="digest"):
        restore(repo, corrupt, repo / "data/cache/refused")
    assert not (repo / "data/cache/refused").exists()
