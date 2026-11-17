"""Shared local workspace boundary and exclusive server/maintenance lease."""

import ctypes
import errno
import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


def publish_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish a complete directory, refusing any destination at commit time.

    Ordinary directory rename can replace an empty directory created after an existence
    check. Linux/WSL's RENAME_NOREPLACE closes that race. Unsupported hosts/filesystems
    fail closed; an ordinary rename is never a safe fallback.
    """
    if source.is_symlink() or not source.is_dir():
        raise ValueError("publication requires a staged regular directory")
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise OSError(errno.ENOTSUP, "atomic no-replace directory publication unavailable") from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    # AT_FDCWD and RENAME_NOREPLACE are stable Linux ABI constants. Both paths are
    # absolute so a concurrent process-wide cwd change cannot redirect publication.
    result = rename(
        -100, os.fsencode(source.absolute()), -100, os.fsencode(destination.absolute()), 1
    )
    if result:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise ValueError("publication destination already exists")
        raise OSError(error, "atomic no-replace directory publication failed")


def workspace_path(repo: Path, workspace: Path) -> Path:
    resolved = workspace.resolve()
    cache = (repo.resolve() / "data" / "cache").resolve()
    if (
        not cache.is_relative_to(repo.resolve())
        or not resolved.is_relative_to(cache)
        or resolved == cache
    ):
        raise ValueError("workspace must be a subdirectory of repository data/cache")
    return resolved


def acquire_workspace(root: Path) -> TextIO:
    """Acquire before opening/migrating SQLite or starting any worker."""
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".writer.lock").is_symlink():
        raise ValueError("workspace lock must not be a symlink")
    lock = (root / ".writer.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lock.close()
        raise
    return lock


@contextmanager
def workspace_lease(root: Path) -> Iterator[None]:
    lock = acquire_workspace(root)
    try:
        yield
    finally:
        lock.close()
