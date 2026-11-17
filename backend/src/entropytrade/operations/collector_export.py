"""Read-only collector history export and inactive, offline inspection restore.

Workspace ZIPs are opaque history: their original application locks and clocks survive
unchanged. This module never restores one against today's code or activates a collector.
The encryption/independently trusted ciphertext receipt belongs to operations.backup.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import IO, TYPE_CHECKING, Any, BinaryIO, cast
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from entropytrade.api.jobs import timestamp
from entropytrade.api.recovery import MAX_MANIFEST_BYTES, blob_member, relative
from entropytrade.api.workspace import publish_directory_no_replace
from entropytrade.operations import local_chain

if TYPE_CHECKING:
    from collections.abc import Iterator

SCHEMA = "entropytrade-collector-inspection-v1"
MAX_BYTES = 64 * 1024**3
MAX_FILES = 100_000
MAX_PATH_BYTES = 256
MANIFEST = "export-manifest.json"
MARKER = "INSPECTION_ONLY.json"
_MARKER = {"schema": SCHEMA, "inspection_only": True, "collector_activation_supported": False}
_CHUNK = 1024 * 1024
_METADATA_BYTES = MAX_MANIFEST_BYTES


class ExportError(ValueError):
    """The source or inactive inspection export failed closed."""


@dataclass(frozen=True)
class _File:
    device: int
    inode: int
    mode: int
    size: int
    mtime: int
    ctime: int

    @classmethod
    def of(cls, info: os.stat_result) -> _File:
        if not stat.S_ISREG(info.st_mode):
            raise ExportError("collector inventory requires regular files without symlinks")
        return cls(
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )


def _absolute(path: Path) -> Path:
    result = path.absolute()
    if ".." in result.parts:
        raise ExportError("inspection paths must not contain parent traversal")
    return result


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    """Walk from / using no-follow directory descriptors, including every parent."""
    path = _absolute(path)
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _regular(root: int, name: str) -> Iterator[BinaryIO]:
    parts = PurePosixPath(relative(name)).parts
    descriptor = os.dup(root)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
        )
        try:
            _File.of(os.fstat(file_descriptor))
        except BaseException:
            os.close(file_descriptor)
            raise
        with os.fdopen(file_descriptor, "rb") as handle:
            yield handle
    finally:
        os.close(descriptor)


def _limits(max_bytes: int, max_files: int) -> None:
    if type(max_bytes) is not int or type(max_files) is not int or min(max_bytes, max_files) < 1:
        raise ExportError("inspection capacity limits must be positive integers")


def _names(root: int, maximum: int) -> list[str]:
    names = []
    with os.scandir(root) as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names) > maximum:
                raise ExportError("collector exceeds inspection inventory budget")
    return names


def _inventory(
    root: int, max_bytes: int, max_files: int, *, require_lock: bool = True
) -> dict[str, _File]:
    """Inspect only the complete flat link format; never omit hidden/stale entries."""
    expected = {"HEAD", "links"} | ({".lock"} if require_lock else set())
    if set(_names(root, 4)) != expected:
        raise ExportError("unexpected/stale collector entries; inspection is required")
    files = {"HEAD": _File.of(os.stat("HEAD", dir_fd=root, follow_symlinks=False))}
    if require_lock:
        _File.of(os.stat(".lock", dir_fd=root, follow_symlinks=False))
    links_descriptor = os.open("links", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
    try:
        names = sorted(_names(links_descriptor, max_files))
        if not names or names != [f"{i:06d}" for i in range(1, len(names) + 1)]:
            raise ExportError("collector requires contiguous complete links")
        if len(names) > max_files:
            raise ExportError("collector exceeds inspection file budget")
        total = files["HEAD"].size
        for name in names:
            link = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=links_descriptor
            )
            try:
                children = _names(link, max_files)
                if not {*local_chain.SNAPSHOT_FILES, local_chain.MANIFEST} <= set(children):
                    raise ExportError("collector link is incomplete")
                for child in children:
                    relative(child)
                    path = f"links/{name}/{child}"
                    if child.startswith(".") or len(path.encode()) > MAX_PATH_BYTES:
                        raise ExportError("unexpected collector link entry")
                    item = _File.of(os.stat(child, dir_fd=link, follow_symlinks=False))
                    files[path] = item
                    total += item.size
                    if total > max_bytes or len(files) > max_files:
                        raise ExportError("collector exceeds inspection capacity budget")
                    if child in {"manifest.json", "lineage.txt"} and item.size > _METADATA_BYTES:
                        raise ExportError("collector metadata exceeds inspection budget")
                    if child == "workspace.sha256" and item.size > 1024:
                        raise ExportError("collector checksum exceeds inspection budget")
            finally:
                os.close(link)
    finally:
        os.close(links_descriptor)
    if files["HEAD"].size > 1024 or total > max_bytes:
        raise ExportError("collector HEAD/bytes exceed inspection budget")
    return files


def _read(root: int, name: str, expected: _File, limit: int) -> bytes:
    with _regular(root, name) as handle:
        if _File.of(os.fstat(handle.fileno())) != expected or expected.size > limit:
            raise ExportError("collector changed during inspection")
        value = handle.read(limit + 1)
        if len(value) != expected.size or len(value) > limit:
            raise ExportError("collector changed during inspection")
        return value


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _pins(root: int, files: dict[str, _File]) -> tuple[dict[str, str], bytes]:
    head = _read(root, "HEAD", files["HEAD"], 1024)
    pins = {"HEAD": _digest(head)}
    for path, item in files.items():
        if not path.endswith("/manifest.json"):
            continue
        raw = _read(root, path, item, _METADATA_BYTES)
        manifest = json.loads(raw)
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"schema", "files"}
            or manifest["schema"] != local_chain.SCHEMA
            or not isinstance(manifest["files"], dict)
        ):
            raise ExportError("unsupported collector link manifest")
        prefix = path.removesuffix("manifest.json")
        listed = manifest["files"]
        present = {p.removeprefix(prefix) for p in files if p.startswith(prefix) and p != path}
        if set(listed) != present:
            raise ExportError("collector files differ from link manifest")
        pins[path] = _digest(raw)
        for name, digest in listed.items():
            if not isinstance(name, str) or "/" in relative(name):
                raise ExportError("unsafe collector manifest filename")
            blob_member(digest)
            pins[prefix + name] = digest
    if set(pins) != set(files):
        raise ExportError("incomplete collector manifest inventory")
    return pins, head


def _capacity(parent: Path, required: int) -> None:
    if shutil.disk_usage(parent).free < required:
        raise ExportError("insufficient free space for complete inspection export")


def _encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _archive_limit(max_bytes: int, max_files: int) -> int:
    return max_bytes + MAX_MANIFEST_BYTES + (max_files + 2) * (MAX_PATH_BYTES + 256)


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.compress_type = ZIP_STORED
    return info


def _copy(root: int, path: str, item: _File, target: IO[bytes]) -> str:
    digest = hashlib.sha256()
    with _regular(root, path) as source:
        if _File.of(os.fstat(source.fileno())) != item:
            raise ExportError("collector changed before export copy")
        remaining = item.size
        while remaining:
            chunk = source.read(min(_CHUNK, remaining))
            if not chunk:
                raise ExportError("collector changed during export copy")
            target.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        if source.read(1) or _File.of(os.fstat(source.fileno())) != item:
            raise ExportError("collector changed during export copy")
    return "sha256:" + digest.hexdigest()


def _file_hash(path: Path) -> str:
    with _directory(path.parent) as parent, _regular(parent, path.name) as source:
        return _stream_hash(source)


def _stream_hash(source: BinaryIO) -> str:
    source.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(_CHUNK), b""):
        digest.update(chunk)
    source.seek(0)
    return "sha256:" + digest.hexdigest()


def export_chain(
    source_repo: Path,
    chain: Path,
    output_archive: Path,
    *,
    max_bytes: int = MAX_BYTES,
    max_files: int = MAX_FILES,
) -> dict[str, Any]:
    """Hold ONE existing read-only lock through verification, copy and final pin checks.

    The output parent must already exist outside the collector checkout. Historical ZIPs
    are hash-verified opaque files; no current-version workspace restore is attempted.
    """
    _limits(max_bytes, max_files)
    source_repo, chain, output_archive = map(_absolute, (source_repo, chain, output_archive))
    if (
        not chain.is_relative_to(source_repo / "data/cache")
        or chain == source_repo / "data/cache"
        or output_archive.is_relative_to(source_repo)
    ):
        raise ExportError("export requires a collector data/cache chain and external output")
    try:
        with _directory(chain) as root:
            lock = os.open(".lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
            try:
                locked_file = _File.of(os.fstat(lock))
                try:
                    fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except OSError as exc:
                    raise ExportError(
                        "collector lock is busy; retry after its bounded cycle"
                    ) from exc
                files = _inventory(root, max_bytes, max_files)
                pins, head = _pins(root, files)
                links, digest, manifest_digest, _ = local_chain._verified_state(
                    chain, roll_forward=False
                )
                if _inventory(root, max_bytes, max_files) != files:
                    raise ExportError("collector changed during verification")
                inventory = [
                    {"path": path, "bytes": item.size, "sha256": pins[path]}
                    for path, item in sorted(files.items())
                ]
                receipt = {
                    "schema": SCHEMA,
                    "source_kind": "collector-chain",
                    "created_at": timestamp(),
                    "inspection_only": True,
                    "links": len(links),
                    "head_sha256": digest,
                    "head_manifest_sha256": manifest_digest,
                    "source_sha256": _digest(_encoded(inventory)),
                    "verification_scope": "complete hash-linked history; workspace ZIPs opaque",
                    "submission_enabled": False,
                }
                metadata = _encoded({**receipt, "files": inventory})
                if len(metadata) > MAX_MANIFEST_BYTES:
                    raise ExportError("collector exceeds inspection manifest budget")
                with _directory(output_archive.parent):
                    if os.path.lexists(output_archive):
                        raise ExportError("inspection archive output already exists")
                    required = sum(item.size for item in files.values()) + len(metadata)
                    required += (len(files) + 2) * (MAX_PATH_BYTES + 256)
                    _capacity(output_archive.parent, required)
                    with TemporaryDirectory(
                        prefix=".collector-export-", dir=output_archive.parent
                    ) as tmp:
                        private = Path(tmp)
                        private.chmod(0o700)
                        staged = private / "inspection.zip"
                        with staged.open("xb") as handle:
                            staged.chmod(0o600)
                            with ZipFile(handle, "w", compression=ZIP_STORED) as bundle:
                                bundle.writestr(_zip_info(MANIFEST), metadata)
                                bundle.writestr(_zip_info(MARKER), _encoded(_MARKER))
                                for path, item in sorted(files.items()):
                                    with bundle.open(
                                        _zip_info("chain/" + path), "w", force_zip64=True
                                    ) as target:
                                        copied = _copy(root, path, item, target)
                                    if copied != pins[path]:
                                        raise ExportError("collector copy checksum mismatch")
                            handle.flush()
                            os.fsync(handle.fileno())
                        if (
                            _inventory(root, max_bytes, max_files) != files
                            or _read(root, "HEAD", files["HEAD"], 1024) != head
                            or _pins(root, files)[0] != pins
                            or _File.of(os.stat(".lock", dir_fd=root, follow_symlinks=False))
                            != locked_file
                        ):
                            raise ExportError("collector changed before export completed")
                        with _directory(chain) as current:
                            a, b = os.fstat(root), os.fstat(current)
                            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                                raise ExportError("collector directory changed during export")
                        archive_digest = _file_hash(staged)
                        archive_bytes = staged.stat().st_size
                        os.link(staged, output_archive, follow_symlinks=False)
                        with _directory(output_archive.parent) as parent:
                            os.fsync(parent)
                        return {
                            **receipt,
                            "archive_sha256": archive_digest,
                            "archive_bytes": archive_bytes,
                        }
            finally:
                os.close(lock)
    except ExportError:
        raise
    except (OSError, local_chain.ChainError, UnicodeError, ValueError) as exc:
        raise ExportError("collector export refused: " + str(exc)) from exc


def _bounded_zip_directory(source: BinaryIO, max_files: int) -> None:
    """Bound central-directory allocation before ZipFile reads an untrusted ZIP."""
    source.seek(0, os.SEEK_END)
    length = source.tell()
    if length < 22:
        raise ExportError("incomplete inspection archive")
    source.seek(-22, os.SEEK_END)
    signature, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack(
        "<4s4H2LH", source.read(22)
    )
    if signature != b"PK\x05\x06" or disk or start_disk or comment or disk_count != count:
        raise ExportError("unsupported inspection ZIP directory")
    if count == 0xFFFF or size == 0xFFFFFFFF or offset == 0xFFFFFFFF:
        if length < 98:
            raise ExportError("incomplete inspection ZIP64 directory")
        source.seek(-42, os.SEEK_END)
        signature, disk, position, disks = struct.unpack("<4sLQL", source.read(20))
        if signature != b"PK\x06\x07" or disk or disks != 1 or position > length - 98:
            raise ExportError("unsupported inspection ZIP64 locator")
        source.seek(position)
        fields = struct.unpack("<4sQ2H2L4Q", source.read(56))
        signature, record_size, _, _, disk, start_disk, disk_count, count, size, offset = fields
        if (
            signature != b"PK\x06\x06"
            or record_size != 44
            or disk
            or start_disk
            or disk_count != count
        ):
            raise ExportError("unsupported inspection ZIP64 directory")
    if (
        count > max_files + 2
        or size > (max_files + 2) * (MAX_PATH_BYTES + 256)
        or offset + size > length - 22
    ):
        raise ExportError("inspection ZIP directory exceeds budget")
    source.seek(0)


def _manifest(bundle: ZipFile, max_bytes: int, max_files: int) -> dict[str, Any]:
    members = bundle.infolist()
    names = [item.filename for item in members]
    if len(names) > max_files + 2 or len(names) != len(set(names)):
        raise ExportError("duplicate/excessive inspection archive members")
    for item in members:
        relative(item.filename)
        if (
            len(item.filename.encode()) > MAX_PATH_BYTES + 6
            or item.is_dir()
            or stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG}
            or item.flag_bits & 1
            or item.compress_type != ZIP_STORED
        ):
            raise ExportError("inspection members require plain regular files")
    if (
        MANIFEST not in names
        or MARKER not in names
        or bundle.getinfo(MANIFEST).file_size > MAX_MANIFEST_BYTES
        or bundle.getinfo(MARKER).file_size > 1024
    ):
        raise ExportError("missing/oversized inspection manifest or marker")
    manifest = json.loads(bundle.read(MANIFEST))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != SCHEMA
        or manifest.get("source_kind") != "collector-chain"
        or manifest.get("inspection_only") is not True
        or manifest.get("submission_enabled") is not False
        or json.loads(bundle.read(MARKER)) != _MARKER
        or not isinstance(manifest.get("files"), list)
    ):
        raise ExportError("unsupported/inactive inspection manifest required")
    files = manifest["files"]
    if len(files) > max_files:
        raise ExportError("inspection file budget exceeded")
    total = 0
    paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
            raise ExportError("invalid inspection inventory")
        path = relative(item["path"])
        parts = PurePosixPath(path).parts
        if path != "HEAD" and (
            len(parts) != 3
            or parts[0] != "links"
            or not parts[1].isdigit()
            or len(parts[1]) != 6
            or parts[2].startswith(".")
        ):
            raise ExportError("unexpected inspection chain entry")
        if len(path.encode()) > MAX_PATH_BYTES or path in paths:
            raise ExportError("duplicate/oversized inspection path")
        paths.add(path)
        blob_member(item["sha256"])
        size = item["bytes"]
        if type(size) is not int or size < 0 or size != bundle.getinfo("chain/" + path).file_size:
            raise ExportError("invalid inspection member size")
        total += size
        if total > max_bytes:
            raise ExportError("inspection byte capacity budget exceeded")
        if parts[-1] in {"manifest.json", "lineage.txt"} and size > _METADATA_BYTES:
            raise ExportError("inspection metadata exceeds budget")
        if (path == "HEAD" or parts[-1] == "workspace.sha256") and size > 1024:
            raise ExportError("inspection HEAD/checksum exceeds budget")
    if set(names) != {MANIFEST, MARKER} | {"chain/" + path for path in paths}:
        raise ExportError("incomplete inspection archive inventory")
    if manifest["source_sha256"] != _digest(_encoded(files)):
        raise ExportError("inspection inventory checksum mismatch")
    return cast("dict[str, Any]", manifest)


def restore_export(
    archive: Path,
    destination: Path,
    *,
    max_bytes: int = MAX_BYTES,
    max_files: int = MAX_FILES,
) -> dict[str, Any]:
    """Restore only to a NEW inactive inspection area outside every data/cache tree."""
    _limits(max_bytes, max_files)
    archive, destination = map(_absolute, (archive, destination))
    if any(
        a == "data" and b == "cache"
        for a, b in zip(destination.parts, destination.parts[1:], strict=False)
    ):
        raise ExportError("inspection restore must stay outside data/cache")
    try:
        with _directory(destination.parent), _directory(archive.parent) as archive_parent:
            if os.path.lexists(destination):
                raise ExportError("inspection restore requires a new destination")
            with _regular(archive_parent, archive.name) as source:
                original = _File.of(os.fstat(source.fileno()))
                if original.size > _archive_limit(max_bytes, max_files):
                    raise ExportError("inspection archive exceeds capacity budget")
                archive_digest = _stream_hash(source)
                _bounded_zip_directory(source, max_files)
                with ZipFile(source) as bundle:
                    manifest = _manifest(bundle, max_bytes, max_files)
                    _capacity(
                        destination.parent,
                        sum(item["bytes"] for item in manifest["files"]) + MAX_MANIFEST_BYTES,
                    )
                    with TemporaryDirectory(
                        prefix=".collector-inspection-", dir=destination.parent
                    ) as tmp:
                        private = Path(tmp)
                        private.chmod(0o700)
                        stage = private / "inspection"
                        stage.mkdir(mode=0o700)
                        for name in (MANIFEST, MARKER):
                            target = stage / name
                            target.write_bytes(bundle.read(name))
                            target.chmod(0o600)
                        for item in manifest["files"]:
                            target = stage / "chain" / item["path"]
                            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                            digest = hashlib.sha256()
                            remaining = item["bytes"]
                            with (
                                bundle.open("chain/" + item["path"]) as reader,
                                target.open("xb") as writer,
                            ):
                                target.chmod(0o600)
                                while remaining:
                                    chunk = reader.read(min(_CHUNK, remaining))
                                    if not chunk:
                                        raise ExportError("incomplete inspection member")
                                    writer.write(chunk)
                                    digest.update(chunk)
                                    remaining -= len(chunk)
                                if reader.read(1):
                                    raise ExportError("inspection member exceeds size")
                                writer.flush()
                                os.fsync(writer.fileno())
                            if "sha256:" + digest.hexdigest() != item["sha256"]:
                                raise ExportError("inspection member checksum mismatch")
                        with _directory(stage / "chain") as chain_root:
                            staged_files = _inventory(
                                chain_root, max_bytes, max_files, require_lock=False
                            )
                            _pins(chain_root, staged_files)
                            links, head_digest, head_manifest, _ = local_chain._verified_state(
                                stage / "chain", roll_forward=False
                            )
                        if (
                            len(links) != manifest["links"]
                            or head_digest != manifest["head_sha256"]
                            or head_manifest != manifest["head_manifest_sha256"]
                            or _File.of(os.fstat(source.fileno())) != original
                            or _stream_hash(source) != archive_digest
                        ):
                            raise ExportError("inspection head/source changed or mismatched")
                        publish_directory_no_replace(stage, destination)
                return {
                    **{key: value for key, value in manifest.items() if key != "files"},
                    "inspection": str(destination),
                    "archive_sha256": archive_digest,
                }
    except ExportError:
        raise
    except (
        OSError,
        BadZipFile,
        local_chain.ChainError,
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
        struct.error,
    ) as exc:
        raise ExportError("inspection restore refused: " + str(exc)) from exc
