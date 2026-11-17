"""Controlled inactive history copies. No private collector or service is accessed."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
from typing import TYPE_CHECKING, Any
from zipfile import ZipFile

import pytest

from entropytrade.api.workspace import publish_directory_no_replace
from entropytrade.operations import collector_export as ce
from entropytrade.operations import local_chain as lc

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import IO


def _hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _manifest(link: Path) -> None:
    files = {p.name: _hash(p.read_bytes()) for p in link.iterdir() if p.name != "manifest.json"}
    (link / "manifest.json").write_text(
        json.dumps({"schema": lc.SCHEMA, "files": files}, sort_keys=True) + "\n"
    )


def _head(chain: Path) -> None:
    last = sorted((chain / "links").iterdir())[-1]
    (chain / "HEAD").write_text(
        f"{int(last.name)} {lc.sha256_file(last / 'workspace.zip')} "
        f"{lc.sha256_file(last / 'manifest.json')}\n"
    )


def _tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@pytest.fixture
def history(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Two complete links, with deliberately older opaque workspace application locks."""
    repo = tmp_path / "collector"
    chain = repo / "data/cache/chain"
    chain.mkdir(parents=True)
    (chain / ".lock").write_bytes(b"original lock bytes\n")
    previous = previous_manifest = ""
    for seq in range(1, 3):
        link = chain / "links" / f"{seq:06d}"
        link.mkdir(parents=True)
        with ZipFile(link / "workspace.zip", "w") as archive:
            archive.writestr(
                "manifest.json",
                json.dumps({"application": {"uv.lock": f"original-lock-{seq}"}}),
            )
            archive.writestr("original-clock.txt", f"2020-01-0{seq}T00:00:00Z")
        digest = lc.sha256_file(link / "workspace.zip")
        (link / "workspace.sha256").write_text(digest + "\n")
        (link / "lineage.txt").write_text(
            f"seq={seq}\nrun_id=old-{seq}\ncommit=old-code-{seq}\n"
            f"previous_sha256={previous}\nprevious_manifest_sha256={previous_manifest}\n"
            f"started_at=2020-01-0{seq}T00:00:00+00:00\n"
        )
        (link / "server.log").write_bytes(f"original log {seq}\n".encode())
        _manifest(link)
        previous = digest
        previous_manifest = lc.sha256_file(link / "manifest.json")
    _head(chain)
    return repo, chain, tmp_path / "history.zip"


def _forbid_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("inspection must never invoke a mutating collector operation")

    for name in (
        "run",
        "import_actions",
        "restore",
        "snapshot",
        "_lock",
        "_write_head",
        "subprocess_collector",
        "code_provenance",
    ):
        monkeypatch.setattr(lc, name, forbidden)


def test_readonly_two_link_roundtrip_preserves_every_byte_and_old_locks(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chain, output = history
    _forbid_activation(monkeypatch)
    before = _tree(chain)
    original_modes = {p: p.stat().st_mode for p in (chain, *chain.rglob("*"))}
    for path in original_modes:
        path.chmod(0o555 if path.is_dir() else 0o444)
    metadata = {p: (p.stat().st_mtime_ns, p.stat().st_ctime_ns) for p in original_modes}
    try:
        exported = ce.export_chain(repo, chain, output)
        assert exported["links"] == 2
        assert exported["inspection_only"] is True
        assert "opaque" in exported["verification_scope"]
        destination = output.parent / "offline-inspection"
        restored = ce.restore_export(output, destination)
        assert restored["inspection_only"] is True
        assert restored["archive_sha256"] == exported["archive_sha256"]
        assert json.loads((destination / ce.MARKER).read_bytes())["inspection_only"] is True
        assert _tree(destination / "chain") == {k: v for k, v in before.items() if k != ".lock"}
        assert not (destination / "chain/.lock").exists()
        assert lc.verify(destination / "chain")["links"] == 2
        assert _tree(chain) == before
        assert {p: (p.stat().st_mtime_ns, p.stat().st_ctime_ns) for p in original_modes} == metadata
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    finally:
        for path, mode in original_modes.items():
            path.chmod(stat.S_IMODE(mode))


def test_only_one_existing_readonly_lock_covers_verification_copy_and_publication(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chain, output = history
    opened: list[int] = []
    original_open = os.open
    original_copy = ce._copy
    original_link = os.link

    def open_spy(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        descriptor = original_open(path, flags, *args, **kwargs)
        if path == ".lock":
            assert flags & os.O_ACCMODE == os.O_RDONLY
            assert flags & os.O_NOFOLLOW
            assert flags & os.O_NONBLOCK
            opened.append(descriptor)
        return descriptor

    def writer_blocked() -> None:
        result = subprocess.run(  # noqa: S603 - fixed interpreter and controlled lock path
            [
                sys.executable,
                "-c",
                (
                    "import fcntl,os,sys\n"
                    "fd=os.open(sys.argv[1],os.O_RDONLY)\n"
                    "try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                    "except BlockingIOError: sys.exit(75)\n"
                    "sys.exit(0)\n"
                ),
                str(chain / ".lock"),
            ],
            check=False,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 75

    copied: list[str] = []

    def copy_spy(root: int, path: str, item: ce._File, target: IO[bytes]) -> str:
        assert len(opened) == 1
        assert fcntl.fcntl(opened[0], fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        if not copied:
            writer_blocked()
        copied.append(path)
        return original_copy(root, path, item, target)

    def link_spy(source: Any, target: Any, **kwargs: Any) -> None:
        writer_blocked()
        original_link(source, target, **kwargs)

    monkeypatch.setattr(os, "open", open_spy)
    monkeypatch.setattr(ce, "_copy", copy_spy)
    monkeypatch.setattr(os, "link", link_spy)
    ce.export_chain(repo, chain, output)
    assert len(opened) == 1
    assert len(copied) == len(_tree(chain)) - 1
    with (chain / ".lock").open("rb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize("missing", [".lock", "HEAD", "links/000002/workspace.zip"])
def test_missing_source_refuses_without_creation_or_repair(
    history: tuple[Path, Path, Path], missing: str
) -> None:
    repo, chain, output = history
    (chain / missing).unlink()
    before = _tree(chain)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert _tree(chain) == before
    assert not output.exists()
    assert not list(output.parent.glob(".collector-export-*"))


def test_busy_source_lock_refuses_without_writes(history: tuple[Path, Path, Path]) -> None:
    repo, chain, output = history
    before = _tree(chain)
    with (chain / ".lock").open("rb") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ce.ExportError, match="busy"):
            ce.export_chain(repo, chain, output)
    assert _tree(chain) == before
    assert not output.exists()


@pytest.mark.parametrize(
    "extra", [".stage-123", ".work-123", ".failed-old", ".hidden", "owner.json"]
)
def test_any_uncommitted_or_unexpected_root_material_blocks_export(
    history: tuple[Path, Path, Path], extra: str
) -> None:
    repo, chain, output = history
    (chain / extra).mkdir()
    before = sorted(p.relative_to(chain).as_posix() for p in chain.rglob("*"))
    with pytest.raises(ce.ExportError, match="unexpected/stale"):
        ce.export_chain(repo, chain, output)
    assert sorted(p.relative_to(chain).as_posix() for p in chain.rglob("*")) == before
    assert not output.exists()


@pytest.mark.parametrize("change", ["tamper", "extra", "missing-link", "head-lag", "schema"])
def test_corrupt_history_refuses_without_mutation(
    history: tuple[Path, Path, Path], change: str
) -> None:
    repo, chain, output = history
    first, second = chain / "links/000001", chain / "links/000002"
    if change == "tamper":
        with (first / "workspace.zip").open("ab") as handle:
            handle.write(b"tamper")
    elif change == "extra":
        (second / "unlisted.log").write_text("unlisted")
    elif change == "missing-link":
        shutil.rmtree(first)
    elif change == "head-lag":
        (chain / "HEAD").write_text(
            f"1 {lc.sha256_file(first / 'workspace.zip')} "
            f"{lc.sha256_file(first / 'manifest.json')}\n"
        )
    else:
        manifest = json.loads((second / "manifest.json").read_bytes())
        manifest["schema"] = "unsupported"
        (second / "manifest.json").write_text(json.dumps(manifest))
        _head(chain)
    before = _tree(chain)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert _tree(chain) == before
    assert not output.exists()


@pytest.mark.parametrize("name", ["HEAD", ".lock", "links/000002/server.log"])
@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_nonregular_source_files_refuse_without_blocking(
    history: tuple[Path, Path, Path], name: str, kind: str
) -> None:
    repo, chain, output = history
    target = chain / name
    saved = target.read_bytes()
    target.unlink()
    if kind == "fifo":
        os.mkfifo(target)
    else:
        external = output.parent / "external"
        external.write_bytes(saved)
        target.symlink_to(external)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert not output.exists()
    assert target.is_symlink() if kind == "symlink" else stat.S_ISFIFO(target.lstat().st_mode)


def test_symlink_parent_and_link_directory_refuse(history: tuple[Path, Path, Path]) -> None:
    repo, chain, output = history
    alias = output.parent / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ce.ExportError):
        ce.export_chain(alias, alias / "data/cache/chain", output)
    link = chain / "links/000002"
    moved = output.parent / "moved"
    link.rename(moved)
    link.symlink_to(moved, target_is_directory=True)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert not output.exists()


@pytest.mark.parametrize("limits", [{"max_bytes": 1}, {"max_files": 2}])
def test_independent_history_budget_refuses_complete_copy_without_pruning(
    history: tuple[Path, Path, Path], limits: dict[str, int]
) -> None:
    repo, chain, output = history
    before = _tree(chain)
    with pytest.raises(ce.ExportError, match="budget"):
        ce.export_chain(repo, chain, output, **limits)
    assert _tree(chain) == before
    assert not output.exists()


def test_capacity_preflight_before_copy_and_no_source_changes(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chain, output = history
    before = _tree(chain)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(100, 100, 0))
    with pytest.raises(ce.ExportError, match="free space"):
        ce.export_chain(repo, chain, output)
    assert _tree(chain) == before
    assert not output.exists()
    assert not list(output.parent.glob(".collector-export-*"))


@pytest.mark.parametrize("change", ["HEAD", "links/000002/server.log", "extra-link"])
def test_source_change_while_copying_refuses_unpublished_archive(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    repo, chain, output = history
    original = ce._copy
    changed = False

    def change_copy(root: int, path: str, item: ce._File, target: IO[bytes]) -> str:
        nonlocal changed
        result = original(root, path, item, target)
        if not changed:
            changed = True
            if change == "extra-link":
                (chain / "links/000003").mkdir()
            else:
                source = chain / change
                source.write_bytes(source.read_bytes() + b"changed")
        return result

    monkeypatch.setattr(ce, "_copy", change_copy)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert not output.exists()
    assert not list(output.parent.glob(".collector-export-*"))


def test_export_publication_race_never_overwrites_existing_output(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chain, output = history
    original = os.link

    def race(source: Any, destination: Any, **kwargs: Any) -> None:
        output.write_bytes(b"concurrent output")
        original(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", race)
    with pytest.raises(ce.ExportError):
        ce.export_chain(repo, chain, output)
    assert output.read_bytes() == b"concurrent output"
    assert not list(output.parent.glob(".collector-export-*"))


def test_restore_refuses_active_location_existing_destination_and_race(
    history: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chain, output = history
    ce.export_chain(repo, chain, output)
    with pytest.raises(ce.ExportError, match="outside data/cache"):
        ce.restore_export(output, repo / "data/cache/restored")
    destination = output.parent / "inspection"
    destination.mkdir()
    with pytest.raises(ce.ExportError, match="new destination"):
        ce.restore_export(output, destination)
    destination.rmdir()
    publish = publish_directory_no_replace

    def race(source: Path, target: Path) -> None:
        target.mkdir()
        publish(source, target)

    monkeypatch.setattr(ce, "publish_directory_no_replace", race)
    with pytest.raises(ce.ExportError):
        ce.restore_export(output, destination)
    assert list(destination.iterdir()) == []
    assert not list(output.parent.glob(".collector-inspection-*"))


def _rewrite(archive: Path, mutate: Callable[[dict[str, bytes]], None]) -> None:
    with ZipFile(archive) as bundle:
        members = {name: bundle.read(name) for name in bundle.namelist()}
    mutate(members)
    archive.unlink()
    with ZipFile(archive, "w") as bundle:
        for name, content in members.items():
            bundle.writestr(ce._zip_info(name), content)


@pytest.mark.parametrize("change", ["tamper", "extra", "marker", "manifest", "size"])
def test_restore_invalid_archive_never_publishes_partial_inspection(
    history: tuple[Path, Path, Path], change: str
) -> None:
    repo, chain, output = history
    ce.export_chain(repo, chain, output)

    def mutate(members: dict[str, bytes]) -> None:
        if change == "tamper":
            name = "chain/links/000001/server.log"
            members[name] = b"X" * len(members[name])
        elif change == "extra":
            members["chain/owner.json"] = b"{}"
        elif change == "marker":
            members[ce.MARKER] = b'{"inspection_only":false}'
        elif change == "manifest":
            members[ce.MANIFEST] = b"[]"
        else:
            manifest = json.loads(members[ce.MANIFEST])
            manifest["files"][0]["bytes"] = 10**15
            members[ce.MANIFEST] = json.dumps(manifest).encode()

    _rewrite(output, mutate)
    destination = output.parent / "invalid"
    with pytest.raises(ce.ExportError):
        ce.restore_export(output, destination)
    assert not destination.exists()
    assert not list(output.parent.glob(".collector-inspection-*"))


def test_restore_budget_and_oversized_zip_directory_refuse(
    history: tuple[Path, Path, Path],
) -> None:
    repo, chain, output = history
    ce.export_chain(repo, chain, output)
    destination = output.parent / "inspection"
    with pytest.raises(ce.ExportError, match="budget"):
        ce.restore_export(output, destination, max_bytes=1)
    with output.open("r+b") as handle:
        handle.seek(-22, os.SEEK_END)
        fields = list(struct.unpack("<4s4H2LH", handle.read(22)))
        fields[5] = 0x7FFFFFFF
        handle.seek(-22, os.SEEK_END)
        handle.write(struct.pack("<4s4H2LH", *fields))
    with pytest.raises(ce.ExportError, match="directory exceeds budget"):
        ce.restore_export(output, destination)
    assert not destination.exists()
