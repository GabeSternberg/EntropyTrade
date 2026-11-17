"""Bounded offline encrypted backups; restore requires an independently trusted digest.

The server needs only a pinned public key. Decryption is an operator action on an
offline recovery machine with its explicitly selected private-key GnuPG home.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import selectors
import shutil
import stat
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from entropytrade.api import recovery
from entropytrade.data.sources import file_hash

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

SCHEMA = "entropytrade-encrypted-backup-v1"
MAX_KEY_BYTES = 1024 * 1024
MAX_CIPHER_BYTES = 3 * 1024**3
MAX_PLAINTEXT_BYTES = 3 * 1024**3
MAX_COMMAND_OUTPUT = 1024 * 1024
DISK_RESERVE = 32 * 1024**2
DEFAULT_TIMEOUT = 300.0
_REQUIRED_OPTIONS = {
    "--no-options",
    "--homedir",
    "--batch",
    "--no-tty",
    "--no-auto-key-retrieve",
    "--no-auto-key-import",
    "--no-autostart",
    "--auto-key-locate",
    "--no-encrypt-to",
    "--recipient-file",
    "--compress-algo",
    "--status-fd",
    "--max-output",
    "--import-options",
    "--with-colons",
    "--with-fingerprint",
    "--with-subkey-fingerprint",
}
_BAD_STATUS = {
    "FAILURE",
    "ERROR",
    "BADMDC",
    "ERRMDC",
    "DECRYPTION_FAILED",
    "NODATA",
    "BADARMOR",
    "UNEXPECTED",
    "NO_SECKEY",
    "INV_RECP",
    "NO_RECP",
    "KEYEXPIRED",
    "KEYREVOKED",
}


class BackupError(ValueError):
    """An offline backup operation was refused without publishing partial evidence."""


def _run(
    argv: Sequence[str], *, timeout_seconds: float = DEFAULT_TIMEOUT, home: Path | None = None
) -> bytes:
    """Bound both output pipes and runtime; never expose GnuPG diagnostics or user IDs."""
    if timeout_seconds <= 0:
        raise BackupError("GnuPG timeout must be positive")
    environment = {"PATH": os.defpath, "LC_ALL": "C"}
    if home is not None:
        environment["HOME"] = str(home)
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell or private input
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
    except OSError as exc:
        raise BackupError("GnuPG could not be started") from exc
    if process.stdout is None or process.stderr is None:
        raise BackupError("GnuPG output pipes unavailable")
    output = bytearray()
    deadline = time.monotonic() + timeout_seconds
    stderr_bytes = 0
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, data="stdout")
            selector.register(process.stderr, selectors.EVENT_READ, data="stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BackupError("GnuPG operation timed out")
                for key, _event in selector.select(min(remaining, 0.1)):
                    block = os.read(key.fd, 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                    elif key.data == "stdout":
                        output.extend(block)
                    else:
                        stderr_bytes += len(block)
                    if len(output) > MAX_COMMAND_OUTPUT or stderr_bytes > MAX_COMMAND_OUTPUT:
                        raise BackupError("GnuPG exceeded diagnostic output limits")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BackupError("GnuPG operation timed out")
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise BackupError("GnuPG operation timed out") from exc
        if code:
            raise BackupError("GnuPG operation failed")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def _gpg() -> str:
    executable = shutil.which("gpg")
    if executable is None:
        raise BackupError("GnuPG is required")
    return executable


def preflight_gpg() -> str:
    """Feature-detect installed GPG; never upgrade or consult an operator keyring."""
    options = set(_run([_gpg(), "--no-options", "--dump-options"]).decode("ascii").splitlines())
    if not _REQUIRED_OPTIONS.issubset(options):
        raise BackupError("GnuPG lacks required bounded offline backup options")
    return _run([_gpg(), "--no-options", "--version"]).decode("ascii").splitlines()[0]


def _base(home: Path) -> list[str]:
    return [
        _gpg(),
        "--no-options",
        "--homedir",
        str(home),
        "--batch",
        "--no-tty",
        "--no-auto-key-retrieve",
        "--no-auto-key-import",
        "--auto-key-locate",
        "clear",
        "--no-encrypt-to",
    ]


def _safe_path(path: Path) -> Path:
    path = path.absolute()
    if ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise BackupError("backup paths must not contain symlinks or parent traversal")
    return path


def _new_path(path: Path) -> Path:
    path = _safe_path(path)
    if path.exists():
        raise BackupError("backup output must be new; existing evidence is never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _safe_path(path)
    return path


def require_space(path: Path, needed_bytes: int) -> None:
    if needed_bytes < 0 or shutil.disk_usage(path).free < needed_bytes + DISK_RESERVE:
        raise BackupError("insufficient free disk space for bounded backup staging")


def _digest(value: str) -> str:
    hexdigest = value.removeprefix("sha256:").lower()
    if len(hexdigest) != 64 or any(c not in "0123456789abcdef" for c in hexdigest):
        raise BackupError("a complete independently trusted ciphertext SHA-256 is required")
    return "sha256:" + hexdigest


def _fingerprint(value: str) -> str:
    value = value.upper()
    if len(value) not in {40, 64} or any(c not in "0123456789ABCDEF" for c in value):
        raise BackupError("a complete primary public-key fingerprint is required")
    return value


def _copy_regular(source: Path, destination: Path, maximum: int) -> str:
    """Open once with NOFOLLOW and copy privately before hashing/decrypting that copy."""
    source = _safe_path(source)
    if maximum <= 0:
        raise BackupError("backup byte limit must be positive")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
            raise BackupError("backup input must be a bounded regular file")
        require_space(destination.parent, details.st_size)
        digest = hashlib.sha256()
        total = 0
        with (
            os.fdopen(descriptor, "rb", closefd=False) as original,
            destination.open("xb") as copied,
        ):
            destination.chmod(0o600)
            while block := original.read(min(1024**2, maximum - total + 1)):
                total += len(block)
                if total > maximum:
                    raise BackupError("backup input exceeds byte limit")
                copied.write(block)
                digest.update(block)
            copied.flush()
            os.fsync(copied.fileno())
        if total != details.st_size:
            raise BackupError("backup input changed while copying")
        return "sha256:" + digest.hexdigest()
    finally:
        os.close(descriptor)


def _key_listing(listing: bytes, expected: str) -> None:
    """Pin one primary and require a currently usable encryption key below it."""
    try:
        rows = [row.split(":") for row in listing.decode("utf-8").splitlines()]
        primaries = [row for row in rows if row[0] == "pub"]
        if len(primaries) != 1 or any(row[0] in {"sec", "ssb"} for row in rows):
            raise BackupError("recipient must contain exactly one public primary key")
        primary = primaries[0]
        index = rows.index(primary)
        if rows[index + 1][0] != "fpr" or rows[index + 1][9] != expected:
            raise BackupError("recipient primary fingerprint does not match the pin")
        now = time.time()

        def usable(row: list[str]) -> bool:
            return (
                len(row) > 11
                and row[1] not in {"r", "e", "d", "i"}
                and "D" not in row[11]
                and (not row[6] or int(row[6]) > now)
                and (not row[5] or int(row[5]) <= now)
            )

        if not usable(primary) or not any(
            row[0] in {"pub", "sub"} and usable(row) and "e" in row[11] for row in rows
        ):
            raise BackupError("recipient key is expired, revoked, disabled or unusable")
    except (UnicodeError, IndexError, ValueError) as exc:
        if isinstance(exc, BackupError):
            raise
        raise BackupError("malformed recipient public key") from exc


def validate_recipient(
    public_key: Path,
    fingerprint: str,
    private_stage: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> Path:
    """Return a validated private copy; no operator config or private keyring is used."""
    expected = _fingerprint(fingerprint)
    home = private_stage / "encryption-home"
    home.mkdir(mode=0o700)
    key = private_stage / "recipient.public"
    _copy_regular(public_key, key, MAX_KEY_BYTES)
    listing = _run(
        [
            *_base(home),
            "--no-autostart",
            "--with-colons",
            "--with-fingerprint",
            "--with-subkey-fingerprint",
            "--import-options",
            "show-only",
            "--import",
            str(key),
        ],
        timeout_seconds=timeout_seconds,
        home=home,
    )
    _key_listing(listing, expected)
    return key


def _check_status(status: bytes, required: str) -> None:
    try:
        tags = [
            line.split()[1]
            for line in status.decode("utf-8").splitlines()
            if line.startswith("[GNUPG:] ")
        ]
    except (UnicodeError, IndexError) as exc:
        raise BackupError("invalid GnuPG completion status") from exc
    bad = _BAD_STATUS.intersection(tags)
    if required == "DECRYPTION_OKAY":
        # Expiry/revocation prevents NEW encryption to this recipient. It must not
        # destroy access to old authenticated ciphertext pinned by a trusted hash.
        bad -= {"KEYEXPIRED", "KEYREVOKED"}
    if required not in tags or bad:
        raise BackupError("GnuPG did not confirm complete authenticated processing")


def encrypt_archive(
    archive: Path,
    ciphertext: Path,
    public_key: Path,
    private_stage: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> None:
    require_space(ciphertext.parent, archive.stat().st_size + 1024**2)
    home = private_stage / "encryption-home"
    status = _run(
        [
            *_base(home),
            "--no-autostart",
            "--recipient-file",
            str(public_key),
            "--compress-algo",
            "none",
            "--status-fd",
            "1",
            "--output",
            str(ciphertext),
            "--encrypt",
            str(archive),
        ],
        timeout_seconds=timeout_seconds,
        home=home,
    )
    _check_status(status, "END_ENCRYPTION")
    ciphertext.chmod(0o600)


def decrypt_archive(
    ciphertext: Path,
    archive: Path,
    secret_homedir: Path,
    *,
    max_plaintext_bytes: int = MAX_PLAINTEXT_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> None:
    home = _safe_path(secret_homedir)
    if not home.is_dir() or stat.S_IMODE(home.stat().st_mode) & 0o077:
        raise BackupError("offline private-key GnuPG home must be an existing private directory")
    limit = min(max_plaintext_bytes, shutil.disk_usage(archive.parent).free - DISK_RESERVE)
    if limit <= 0:
        raise BackupError("insufficient disk space or plaintext byte budget")
    status = _run(
        [
            *_base(home),
            "--max-output",
            str(limit),
            "--status-fd",
            "1",
            "--output",
            str(archive),
            "--decrypt",
            str(ciphertext),
        ],
        timeout_seconds=timeout_seconds,
        home=home,
    )
    _check_status(status, "DECRYPTION_OKAY")
    if not archive.is_file() or archive.stat().st_size > limit:
        raise BackupError("decrypted archive exceeds plaintext byte budget")
    archive.chmod(0o600)


def _fsync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish(ciphertext: Path, output: Path, receipt: dict[str, Any], receipt_path: Path) -> None:
    temporary = ciphertext.parent / "receipt.json"
    with temporary.open("x", encoding="utf-8") as handle:
        temporary.chmod(0o600)
        json.dump(receipt, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync(ciphertext)
    os.link(ciphertext, output)
    try:
        os.link(temporary, receipt_path)
    except OSError:
        if output.stat(follow_symlinks=False).st_ino == ciphertext.stat().st_ino:
            output.unlink()
        raise
    _fsync(output.parent)
    if receipt_path.parent != output.parent:
        _fsync(receipt_path.parent)


def _receipt(
    kind: str,
    archive: Path,
    ciphertext: Path,
    fingerprint: str,
    source: dict[str, Any],
    application: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "source_kind": kind,
        "created_at": datetime.now(UTC).isoformat(),
        "application": application,
        "source_sha256": source.get("source_sha256", source.get("sha256")),
        "archive_sha256": file_hash(archive),
        "archive_bytes": archive.stat().st_size,
        "ciphertext_sha256": file_hash(ciphertext),
        "ciphertext_bytes": ciphertext.stat().st_size,
        "recipient_primary_fingerprint": _fingerprint(fingerprint),
        "verification_scope": source.get(
            "verification_scope",
            "complete offline workspace validation; opaque models never executed",
        ),
        "inspection_only": kind == "collector-chain",
        "submission_enabled": False,
    }


@contextmanager
def _stage(parent: Path) -> Iterator[Path]:
    parent = _safe_path(parent)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with TemporaryDirectory(prefix=".encrypted-", dir=parent) as name:
        stage = Path(name)
        stage.chmod(0o700)
        yield stage


def _repo_path(repo: Path, path: Path) -> Path:
    return recovery.confined(repo, path if path.is_absolute() else repo / path)


def workspace_backup(
    repo: Path,
    workspace: Path,
    output: Path,
    recipient_file: Path,
    recipient_fingerprint: str,
    *,
    receipt_path: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    repo = _safe_path(repo)
    output = _repo_path(repo, output)
    if not output.is_relative_to(repo / "data/backups") or output.suffix != ".gpg":
        raise BackupError("workspace ciphertext must be a new data/backups/*.gpg file")
    output = _new_path(output)
    receipt_path = _new_path(
        _repo_path(repo, receipt_path) if receipt_path else Path(str(output) + ".receipt.json")
    )
    preflight_gpg()
    with _stage(repo / "data/recovery") as plain, _stage(output.parent) as encrypted:
        key = validate_recipient(
            recipient_file, recipient_fingerprint, encrypted, timeout_seconds=timeout_seconds
        )
        archive = plain / "workspace.zip"
        with recovery.snapshot_lease(repo, _repo_path(repo, workspace), archive) as source:
            ciphertext = encrypted / "archive.gpg"
            encrypt_archive(archive, ciphertext, key, encrypted, timeout_seconds=timeout_seconds)
            receipt = _receipt(
                "workspace",
                archive,
                ciphertext,
                recipient_fingerprint,
                source,
                recovery.application(repo),
            )
            _publish(ciphertext, output, receipt, receipt_path)
    return {**receipt, "ciphertext": str(output), "receipt": str(receipt_path)}


def workspace_restore(
    repo: Path,
    ciphertext: Path,
    expected_sha256: str,
    secret_homedir: Path,
    destination: Path,
    *,
    max_ciphertext_bytes: int = MAX_CIPHER_BYTES,
    max_plaintext_bytes: int = MAX_PLAINTEXT_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    repo = _safe_path(repo)
    expected = _digest(expected_sha256)
    destination = _repo_path(repo, destination)
    _new_path(destination)
    preflight_gpg()
    with _stage(repo / "data/recovery") as stage:
        copied = stage / "verified-ciphertext.gpg"
        if _copy_regular(ciphertext, copied, max_ciphertext_bytes) != expected:
            raise BackupError("ciphertext does not match the independently trusted SHA-256")
        archive = stage / "workspace.zip"
        decrypt_archive(
            copied,
            archive,
            secret_homedir,
            max_plaintext_bytes=max_plaintext_bytes,
            timeout_seconds=timeout_seconds,
        )
        result = recovery.restore(repo, archive, destination)
    return {**result, "ciphertext_sha256": expected, "decryption_verified": True}


def chain_export(
    source_repo: Path,
    chain: Path,
    output: Path,
    recipient_file: Path,
    recipient_fingerprint: str,
    *,
    receipt_path: Path | None = None,
    max_bytes: int = 64 * 1024**3,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    from entropytrade.operations.collector_export import export_chain

    output = _new_path(output)
    if output.is_relative_to(_safe_path(source_repo)) or output.suffix != ".gpg":
        raise BackupError("chain ciphertext must be a new .gpg outside the collector checkout")
    receipt_path = _new_path(receipt_path or Path(str(output) + ".receipt.json"))
    preflight_gpg()
    with _stage(output.parent) as stage:
        key = validate_recipient(
            recipient_file, recipient_fingerprint, stage, timeout_seconds=timeout_seconds
        )
        archive = stage / "chain.zip"
        source = export_chain(source_repo, chain, archive, max_bytes=max_bytes)
        ciphertext = stage / "archive.gpg"
        encrypt_archive(archive, ciphertext, key, stage, timeout_seconds=timeout_seconds)
        receipt = _receipt(
            "collector-chain", archive, ciphertext, recipient_fingerprint, source, None
        )
        _publish(ciphertext, output, receipt, receipt_path)
    return {**receipt, "ciphertext": str(output), "receipt": str(receipt_path)}


def chain_restore(
    ciphertext: Path,
    expected_sha256: str,
    secret_homedir: Path,
    destination: Path,
    *,
    max_ciphertext_bytes: int = 64 * 1024**3,
    max_plaintext_bytes: int = 64 * 1024**3,
    max_bytes: int = 64 * 1024**3,
    timeout_seconds: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    from entropytrade.operations.collector_export import restore_export

    expected = _digest(expected_sha256)
    destination = _new_path(destination)
    if any(
        p.name == "cache" and p.parent.name == "data" for p in (destination, *destination.parents)
    ):
        raise BackupError("collector inspection restore must stay outside data/cache")
    preflight_gpg()
    with _stage(destination.parent) as stage:
        copied = stage / "verified-ciphertext.gpg"
        if _copy_regular(ciphertext, copied, max_ciphertext_bytes) != expected:
            raise BackupError("ciphertext does not match the independently trusted SHA-256")
        archive = stage / "chain.zip"
        decrypt_archive(
            copied,
            archive,
            secret_homedir,
            max_plaintext_bytes=max_plaintext_bytes,
            timeout_seconds=timeout_seconds,
        )
        result = restore_export(archive, destination, max_bytes=max_bytes)
    return {**result, "ciphertext_sha256": expected, "decryption_verified": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("workspace-backup", "chain-export", "workspace-restore", "chain-restore"):
        command = commands.add_parser(action)
        command.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT)
        if action.startswith("workspace"):
            command.add_argument("--repo", required=True, type=Path)
        if action.endswith(("backup", "export")):
            command.add_argument("--output", required=True, type=Path)
            command.add_argument("--recipient-file", required=True, type=Path)
            command.add_argument("--recipient-fingerprint", required=True)
            command.add_argument("--receipt", type=Path)
            if action == "workspace-backup":
                command.add_argument("--workspace", required=True, type=Path)
            else:
                command.add_argument("--source-repo", required=True, type=Path)
                command.add_argument("--chain", required=True, type=Path)
                command.add_argument("--max-bytes", type=int, default=64 * 1024**3)
        else:
            command.add_argument("--ciphertext", required=True, type=Path)
            command.add_argument("--expected-sha256", required=True)
            command.add_argument("--secret-homedir", required=True, type=Path)
            command.add_argument("--destination", required=True, type=Path)
            default = MAX_PLAINTEXT_BYTES if action == "workspace-restore" else 64 * 1024**3
            command.add_argument("--max-plaintext-bytes", type=int, default=default)
            command.add_argument("--max-ciphertext-bytes", type=int, default=default)
            if action == "chain-restore":
                command.add_argument("--max-bytes", type=int, default=default)
    arguments = vars(parser.parse_args())
    action = arguments.pop("action")
    if "receipt" in arguments:
        arguments["receipt_path"] = arguments.pop("receipt")
    functions: dict[str, Callable[..., dict[str, Any]]] = {
        "workspace-backup": workspace_backup,
        "workspace-restore": workspace_restore,
        "chain-export": chain_export,
        "chain-restore": chain_restore,
    }
    function = functions[action]
    try:
        result = function(**arguments)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Encrypted recovery refused: {exc}\n")
    print(json.dumps(result, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
