"""CONTROLLED real-GnuPG tests. Generated keys are temporary and never user credentials."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zipfile import ZipFile

import pytest

from entropytrade.api import recovery
from entropytrade.api.jobs import Jobs
from entropytrade.api.workspace import workspace_lease
from entropytrade.data.sources import file_hash
from entropytrade.operations import backup
from entropytrade.operations import collector_export as ce
from entropytrade.operations import local_chain as lc
from entropytrade.research.recovery import validate_research
from tests.research_paper_support import paper_fixture

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class ControlledKey:
    home: Path
    public: Path
    secret: Path
    fingerprint: str


def _command(home: Path, *args: str, data: bytes | None = None) -> bytes:
    executable = shutil.which("gpg")
    assert executable is not None
    return subprocess.run(  # noqa: S603 - controlled fixed GPG test argv, no shell
        [executable, "--no-options", "--homedir", str(home), "--batch", *args],
        input=data,
        capture_output=True,
        check=True,
    ).stdout


@pytest.fixture(scope="module")
def controlled_keys(tmp_path_factory: pytest.TempPathFactory) -> Iterator[list[ControlledKey]]:
    root = tmp_path_factory.mktemp("controlled-backup-keys")
    keys = []
    for number in range(2):
        home = root / f"home-{number}"
        home.mkdir(mode=0o700)
        specification = (
            "Key-Type: eddsa\nKey-Curve: Ed25519\nKey-Usage: cert\n"
            "Subkey-Type: ecdh\nSubkey-Curve: Curve25519\nSubkey-Usage: encrypt\n"
            f"Name-Real: CONTROLLED BACKUP {number}\n"
            "Name-Email: controlled@example.invalid\nExpire-Date: 1d\n"
            "%no-protection\n%commit\n"
        ).encode()
        _command(home, "--generate-key", data=specification)
        listing = _command(home, "--with-colons", "--list-keys").decode()
        fingerprint = next(
            row.split(":")[9] for row in listing.splitlines() if row.startswith("fpr:")
        )
        public = root / f"public-{number}.asc"
        public.write_bytes(_command(home, "--armor", "--export", fingerprint))
        secret = root / f"secret-{number}.asc"
        secret.write_bytes(_command(home, "--armor", "--export-secret-keys", fingerprint))
        keys.append(ControlledKey(home, public, secret, fingerprint))
    try:
        yield keys
    finally:
        for key in keys:
            executable = shutil.which("gpgconf")
            assert executable is not None
            subprocess.run(  # noqa: S603 - fixed temporary controlled GPG home
                [executable, "--homedir", str(key.home), "--kill", "gpg-agent"],
                check=True,
                capture_output=True,
            )


def encrypted(
    tmp_path: Path, key: ControlledKey, payload: bytes = b"CONTROLLED opaque archive"
) -> Path:
    stage = tmp_path / "crypto"
    stage.mkdir(mode=0o700)
    public = backup.validate_recipient(key.public, key.fingerprint, stage)
    plain = stage / "plain.zip"
    plain.write_bytes(payload)
    cipher = stage / "cipher.gpg"
    backup.encrypt_archive(plain, cipher, public, stage)
    return cipher


def test_real_gpg_round_trip_and_private_files(
    tmp_path: Path, controlled_keys: list[ControlledKey]
) -> None:
    key = controlled_keys[0]
    payload = b"CONTROLLED immutable opaque model bytes\x00" * 100
    cipher = encrypted(tmp_path, key, payload)
    target = tmp_path / "decrypted.zip"
    backup.decrypt_archive(cipher, target, key.home)
    assert target.read_bytes() == payload
    assert target.stat().st_mode & 0o777 == 0o600
    assert cipher.stat().st_mode & 0o777 == 0o600
    assert (cipher.parent / "encryption-home").stat().st_mode & 0o777 == 0o700
    assert not (cipher.parent / "encryption-home/private-keys-v1.d").exists()
    assert "GnuPG" in backup.preflight_gpg()


def test_old_ciphertext_can_be_recovered_after_recipient_expiry(
    tmp_path: Path, controlled_keys: list[ControlledKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    key = controlled_keys[0]
    payload = b"CONTROLLED historical encrypted evidence"
    cipher = encrypted(tmp_path, key, payload)
    original = backup._base

    def future(home: Path) -> list[str]:
        return [*original(home), "--faked-system-time", str(int(time.time()) + 2 * 86400)]

    monkeypatch.setattr(backup, "_base", future)
    target = tmp_path / "recovered-old.zip"
    backup.decrypt_archive(cipher, target, key.home)
    assert target.read_bytes() == payload
    stage = tmp_path / "future-encryption"
    stage.mkdir(mode=0o700)
    with pytest.raises(backup.BackupError, match="expired"):
        backup.validate_recipient(key.public, key.fingerprint, stage)


def test_real_gpg_application_backup_restore_keeps_unpromoted_models_and_history(
    tmp_path: Path, controlled_keys: list[ControlledKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "research-checkout"
    repo.mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        (repo / name).write_text("CONTROLLED application identity")
    workspace = repo / "data/cache/research"
    paper_fixture(workspace)
    root = workspace / "research"
    before = {
        p.relative_to(root): file_hash(p)
        for p in root.rglob("*")
        if p.is_file() and not p.name.startswith("research.sqlite")
    }
    key = controlled_keys[0]
    output = repo / "data/backups/controlled.gpg"
    receipt = backup.workspace_backup(repo, workspace, output, key.public, key.fingerprint)
    assert receipt["submission_enabled"] is False
    assert not list((repo / "data/recovery").glob(".encrypted-*"))
    assert not list(output.parent.glob(".encrypted-*"))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("encrypted restore must not execute a model")

    monkeypatch.setattr("joblib.load", forbidden)
    destination = repo / "data/cache/drill"
    restored = backup.workspace_restore(
        repo, output, receipt["ciphertext_sha256"], key.home, destination
    )
    assert restored["decryption_verified"] is True
    assert restored["submission_enabled"] is False
    assert validate_research(destination) == {
        "jobs": 1,
        "datasets": 2,
        "features": 3,
        "experiments": 1,
    }
    assert all(
        file_hash(destination / "research" / name) == digest for name, digest in before.items()
    )
    assert not list((repo / "data/recovery").glob(".encrypted-*"))


def test_real_gpg_collector_chain_export_and_inspection_restore_preserve_source(
    tmp_path: Path, controlled_keys: list[ControlledKey]
) -> None:
    repo = tmp_path / "collector-checkout"
    chain = repo / "data/cache/chain"
    link = chain / "links/000001"
    link.mkdir(parents=True)
    (chain / ".lock").write_bytes(b"original lock")
    with ZipFile(link / "workspace.zip", "w") as bundle:
        bundle.writestr("old-application-lock", "CONTROLLED older opaque workspace")
    digest = lc.sha256_file(link / "workspace.zip")
    (link / "workspace.sha256").write_text(digest + "\n")
    (link / "lineage.txt").write_text(
        "seq=1\nrun_id=controlled\ncommit=old-code\nprevious_sha256=\n"
        "previous_manifest_sha256=\nstarted_at=2020-01-01T00:00:00+00:00\n"
    )
    (link / "server.log").write_bytes(b"original log")
    files = {p.name: lc.sha256_file(p) for p in link.iterdir()}
    (link / "manifest.json").write_text(json.dumps({"schema": lc.SCHEMA, "files": files}))
    (chain / "HEAD").write_text(f"1 {digest} {lc.sha256_file(link / 'manifest.json')}\n")
    before = {p.relative_to(chain): p.read_bytes() for p in chain.rglob("*") if p.is_file()}
    key = controlled_keys[0]
    output = tmp_path / "encrypted-chain.gpg"
    receipt = backup.chain_export(repo, chain, output, key.public, key.fingerprint)
    destination = tmp_path / "inspection-only"
    restored = backup.chain_restore(output, receipt["ciphertext_sha256"], key.home, destination)
    assert restored["decryption_verified"] is True
    assert restored["inspection_only"] is True
    assert json.loads((destination / ce.MARKER).read_text())["inspection_only"] is True
    assert {p.relative_to(chain): p.read_bytes() for p in chain.rglob("*") if p.is_file()} == before
    assert {
        p.relative_to(destination / "chain"): p.read_bytes()
        for p in (destination / "chain").rglob("*")
        if p.is_file()
    } == {name: value for name, value in before.items() if str(name) != ".lock"}
    assert not list(tmp_path.glob(".encrypted-*"))


@pytest.mark.parametrize("kind", ["wrong-pin", "secret", "multiple", "symlink", "fifo"])
def test_unsafe_recipients_are_rejected(
    tmp_path: Path, controlled_keys: list[ControlledKey], kind: str
) -> None:
    key = controlled_keys[0]
    public = key.public
    pin = key.fingerprint
    if kind == "wrong-pin":
        pin = controlled_keys[1].fingerprint
    elif kind == "secret":
        public = key.secret
    elif kind == "multiple":
        public = tmp_path / "multiple.asc"
        public.write_bytes(key.public.read_bytes() + controlled_keys[1].public.read_bytes())
    elif kind == "symlink":
        public = tmp_path / "link.asc"
        public.symlink_to(key.public)
    elif kind == "fifo":
        public = tmp_path / "fifo.asc"
        os.mkfifo(public)
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    with pytest.raises(backup.BackupError):
        backup.validate_recipient(public, pin, stage)


def _listing(*, validity: str = "-", expires: str = "", capability: str = "e") -> bytes:
    primary = ["pub", validity, "255", "22", "KEY", "1", expires, "", "", "", "", capability]
    return (":".join(primary) + "\nfpr:::::::::" + "A" * 40 + ":\n").encode()


@pytest.mark.parametrize(
    ("validity", "expires", "capability"),
    [
        ("r", "", "e"),
        ("e", "", "e"),
        ("d", "", "e"),
        ("i", "", "e"),
        ("-", "1", "e"),
        ("-", "", "eD"),
        ("-", "", "sC"),
        ("-", "broken", "e"),
    ],
)
def test_expired_revoked_disabled_unusable_key_status_is_not_trusted(
    validity: str, expires: str, capability: str
) -> None:
    with pytest.raises(backup.BackupError):
        backup._key_listing(
            _listing(validity=validity, expires=expires, capability=capability), "A" * 40
        )


@pytest.mark.parametrize("kind", ["wrong-key", "tamper", "truncate", "limit"])
def test_real_gpg_decryption_failure_never_reaches_restore_and_cleans_stages(
    tmp_path: Path, controlled_keys: list[ControlledKey], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    key = controlled_keys[0]
    cipher = encrypted(tmp_path, key, b"CONTROLLED" * 1024)
    raw = cipher.read_bytes()
    if kind == "tamper":
        cipher.write_bytes(raw[:-20] + bytes([raw[-20] ^ 1]) + raw[-19:])
    elif kind == "truncate":
        cipher.write_bytes(raw[: len(raw) // 2])
    home = controlled_keys[1].home if kind == "wrong-key" else key.home

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("invalid ciphertext must not reach application restore")

    monkeypatch.setattr(recovery, "restore", forbidden)
    with pytest.raises(backup.BackupError):
        backup.workspace_restore(
            tmp_path,
            cipher,
            file_hash(cipher),
            home,
            Path("data/cache/restored"),
            max_plaintext_bytes=1 if kind == "limit" else 1_000_000,
        )
    assert not (tmp_path / "data/cache/restored").exists()
    assert not list((tmp_path / "data/recovery").glob(".encrypted-*"))


def test_hash_is_required_before_decrypt_and_verified_private_copy_defeats_path_swap(
    tmp_path: Path, controlled_keys: list[ControlledKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    key = controlled_keys[0]
    cipher = encrypted(tmp_path, key)
    trusted = file_hash(cipher)
    observed = []

    def decrypt(private_cipher: Path, archive: Path, *args: Any, **kwargs: Any) -> None:
        cipher.unlink()
        cipher.write_bytes(b"attacker replaced the original pathname")
        assert file_hash(private_cipher) == trusted
        observed.append(private_cipher)
        archive.write_bytes(b"CONTROLLED verified plaintext")

    monkeypatch.setattr(backup, "decrypt_archive", decrypt)
    monkeypatch.setattr(recovery, "restore", lambda *args: {"submission_enabled": False})
    with pytest.raises(backup.BackupError, match="trusted SHA"):
        backup.workspace_restore(tmp_path, cipher, "0" * 64, key.home, Path("data/cache/new"))
    assert not observed
    result = backup.workspace_restore(tmp_path, cipher, trusted, key.home, Path("data/cache/new"))
    assert result["decryption_verified"]
    assert observed
    assert not observed[0].exists()


@pytest.mark.parametrize("kind", ["timeout", "exit", "output"])
def test_subprocess_timeout_failure_and_diagnostic_bounds(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = {
        "timeout": "import time; time.sleep(10)",
        "exit": "raise SystemExit(1)",
        "output": "import sys; sys.stderr.write('x'*1000)",
    }[kind]
    monkeypatch.setattr(backup, "MAX_COMMAND_OUTPUT", 100)
    with pytest.raises(backup.BackupError):
        backup._run([sys.executable, "-c", script], timeout_seconds=0.1)


def test_required_gpg_output_bound_is_feature_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup, "_run", lambda *args, **kwargs: b"--encrypt\n--decrypt\n")
    with pytest.raises(backup.BackupError, match="required bounded"):
        backup.preflight_gpg()


def test_publish_no_overwrite_and_concurrent_receipt_cleanup(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    cipher = stage / "archive.gpg"
    cipher.write_bytes(b"CONTROLLED cipher")
    output = tmp_path / "new.gpg"
    receipt = tmp_path / "new.receipt.json"
    receipt.write_text("concurrent receipt")
    with pytest.raises(FileExistsError):
        backup._publish(cipher, output, {}, receipt)
    assert not output.exists()
    assert receipt.read_text() == "concurrent receipt"
    (stage / "receipt.json").unlink()
    output.write_bytes(b"existing evidence")
    with pytest.raises(FileExistsError):
        backup._publish(cipher, output, {}, receipt)
    assert output.read_bytes() == b"existing evidence"


def test_backup_busy_lease_and_disk_refusal_without_partial_cipher(
    tmp_path: Path, controlled_keys: list[ControlledKey], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED application identity")
    workspace = Jobs(tmp_path / "data/cache/research").root
    key = controlled_keys[0]
    output = Path("data/backups/workspace.gpg")
    with workspace_lease(workspace), pytest.raises(BlockingIOError):
        backup.workspace_backup(tmp_path, workspace, output, key.public, key.fingerprint)
    assert not (tmp_path / output).exists()
    assert not list((tmp_path / "data/recovery").glob(".encrypted-*"))
    monkeypatch.setattr(shutil, "disk_usage", lambda path: shutil._ntuple_diskusage(100, 100, 0))
    with pytest.raises(backup.BackupError, match="disk"):
        backup.workspace_backup(tmp_path, workspace, output, key.public, key.fingerprint)
    assert not (tmp_path / output).exists()


def test_private_stage_cleanup_on_failure(tmp_path: Path) -> None:
    def fail_inside_stage() -> None:
        with backup._stage(tmp_path) as stage:
            assert stage.stat().st_mode & 0o777 == 0o700
            raise RuntimeError("CONTROLLED")

    with pytest.raises(RuntimeError, match="CONTROLLED"):
        fail_inside_stage()
    assert not list(tmp_path.glob(".encrypted-*"))


def test_hash_rejects_unsafe_cipher_input_without_reading(tmp_path: Path) -> None:
    source = tmp_path / "real"
    source.write_bytes(b"CONTROLLED")
    linked = tmp_path / "link"
    linked.symlink_to(source)
    with pytest.raises(backup.BackupError, match="symlink"):
        backup._copy_regular(linked, tmp_path / "copied", 100)
    with pytest.raises(backup.BackupError, match="bounded regular"):
        backup._copy_regular(source, tmp_path / "copied", 1)
    assert not (tmp_path / "copied").exists()
