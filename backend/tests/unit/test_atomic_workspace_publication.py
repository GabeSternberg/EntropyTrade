"""Real kernel no-replace publication, including the last-check restore race."""

import ctypes
import errno
from pathlib import Path
from types import SimpleNamespace

import pytest

from entropytrade.api import recovery, workspace


def test_directory_publication_moves_complete_stage(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "evidence").write_bytes(b"preserved immutable evidence")
    destination = tmp_path / "published"

    workspace.publish_directory_no_replace(stage, destination)

    assert not stage.exists()
    assert (destination / "evidence").read_bytes() == b"preserved immutable evidence"


@pytest.mark.parametrize("kind", ["empty", "populated", "symlink"])
def test_directory_publication_preserves_existing_destination(tmp_path: Path, kind: str) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "evidence").write_bytes(b"new")
    destination = tmp_path / "existing"
    if kind == "symlink":
        destination.symlink_to(tmp_path / "absent", target_is_directory=True)
    else:
        destination.mkdir()
        if kind == "populated":
            (destination / "owner").write_bytes(b"original")

    with pytest.raises(ValueError, match="destination already exists"):
        workspace.publish_directory_no_replace(stage, destination)

    assert (stage / "evidence").read_bytes() == b"new"
    assert not (destination / "evidence").exists()
    if kind == "symlink":
        assert destination.is_symlink()
    elif kind == "populated":
        assert (destination / "owner").read_bytes() == b"original"
    else:
        assert list(destination.iterdir()) == []


def test_directory_publication_fails_closed_without_kernel_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    destination = tmp_path / "published"
    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace())

    with pytest.raises(OSError, match="publication unavailable") as error:
        workspace.publish_directory_no_replace(stage, destination)

    assert error.value.errno == errno.ENOTSUP
    assert stage.is_dir()
    assert not destination.exists()


@pytest.mark.parametrize("failure", [errno.ENOSYS, errno.EINVAL, errno.EXDEV])
def test_directory_publication_never_falls_back_after_kernel_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: int
) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "evidence").write_bytes(b"complete stage")
    destination = tmp_path / "published"

    def refuse(*arguments: object) -> int:
        ctypes.set_errno(failure)
        return -1

    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace(renameat2=refuse))

    with pytest.raises(OSError, match="publication failed") as error:
        workspace.publish_directory_no_replace(stage, destination)

    assert error.value.errno == failure
    assert (stage / "evidence").read_bytes() == b"complete stage"
    assert not destination.exists()


def test_restore_preserves_destination_created_after_last_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "data/recovery/verified.zip"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"controlled archive; unpack is separately tested")
    destination = tmp_path / "data/cache/restored"
    stages: list[Path] = []

    def unpack(repo: Path, source: Path, stage: Path) -> dict[str, int]:
        stages.append(stage)
        (stage / "evidence").write_bytes(b"complete verified stage")
        return {"jobs": 0, "monitors": 0, "cycles": 0}

    def concurrent_publish(stage: Path, target: Path) -> None:
        # The restore already passed its final target.exists() check. A competing
        # process creates an empty directory immediately before the actual syscall.
        assert target == destination
        target.mkdir()
        workspace.publish_directory_no_replace(stage, target)

    monkeypatch.setattr(recovery, "unpack", unpack)
    monkeypatch.setattr(recovery, "publish_directory_no_replace", concurrent_publish)

    with pytest.raises(ValueError, match="destination already exists"):
        recovery.restore(tmp_path, archive, destination)

    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert stages
    assert not stages[0].exists()
    assert list(destination.parent.glob(".restore-*")) == []


def test_failed_verification_publishes_no_partial_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"invalid archive")
    destination = tmp_path / "data/cache/restored"

    def unpack(repo: Path, source: Path, stage: Path) -> dict[str, int]:
        (stage / "partial").write_bytes(b"unfinished")
        raise ValueError("controlled verification refusal")

    monkeypatch.setattr(recovery, "unpack", unpack)

    with pytest.raises(ValueError, match="verification refusal"):
        recovery.restore(tmp_path, archive, destination)

    assert not destination.exists()
    assert list(destination.parent.glob(".restore-*")) == []
