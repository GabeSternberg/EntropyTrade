"""CONTROLLED local copied-ciphertext drill, not a physical/offsite acceptance claim.

Run from the repository with PYTHONPATH=backend/src:backend. All keys and evidence are
synthetic, confined to a private TemporaryDirectory and removed after the drill.
"""
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from entropytrade.data.sources import file_hash
from entropytrade.operations.backup import workspace_backup, workspace_restore
from entropytrade.research.recovery import validate_research
from tests.research_paper_support import paper_fixture


def main() -> None:
    gpg, gpgconf = shutil.which("gpg"), shutil.which("gpgconf")
    assert gpg and gpgconf
    with TemporaryDirectory(prefix="et-key-") as temporary:
        root = Path(temporary)
        home = root / "offline-key"
        home.mkdir(mode=0o700)
        # Explicit controlled test input, never a user credential or a CLI argument.
        password = b"CONTROLLED-temporary-recovery-passphrase"

        def command(*arguments: str, data: bytes | None = None) -> bytes:
            return subprocess.run(
                [gpg, "--no-options", "--homedir", str(home), "--batch", *arguments],
                input=data, capture_output=True, check=True, timeout=30,
            ).stdout

        def stop_agent() -> None:
            subprocess.run(
                [gpgconf, "--homedir", str(home), "--kill", "gpg-agent"],
                capture_output=True, check=True, timeout=30,
            )

        try:
            specification = (
                b"Key-Type: eddsa\nKey-Curve: Ed25519\nKey-Usage: cert\n"
                b"Subkey-Type: ecdh\nSubkey-Curve: Curve25519\nSubkey-Usage: encrypt\n"
                b"Name-Real: CONTROLLED protected recovery\n"
                b"Name-Email: controlled@example.invalid\nExpire-Date: 1d\nPassphrase: "
                + password + b"\n%commit\n"
            )
            command("--pinentry-mode", "loopback", "--generate-key", data=specification)
            listing = command("--with-colons", "--list-keys").decode()
            fingerprint = next(row.split(":")[9] for row in listing.splitlines() if row.startswith("fpr:"))
            public = root / "recipient.asc"
            public.write_bytes(command("--armor", "--export", fingerprint))
            repo = root / "research"
            repo.mkdir()
            for name in ("pyproject.toml", "uv.lock"):
                (repo / name).write_text("CONTROLLED application identity")
            workspace = repo / "data/cache/source"
            paper_fixture(workspace)
            immutable = {
                str(p.relative_to(workspace)): file_hash(p)
                for p in workspace.rglob("*")
                if p.is_file() and ".sqlite" not in p.name and not p.name.endswith(".lock")
            }
            output = repo / "data/backups/protected.gpg"
            receipt = workspace_backup(repo, workspace, output, public, fingerprint)
            copied = root / "controlled-download.gpg"
            shutil.copyfile(output, copied)
            assert file_hash(copied) == receipt["ciphertext_sha256"]
            stop_agent()  # key generation must not supply the cache used by this proof
            # A controlled stdin loopback prompt stands in for the operator's interactive
            # pinentry. This tests subsequent cache reuse, not a real terminal/UI prompt.
            command(
                "--pinentry-mode", "loopback", "--passphrase-fd", "0",
                "--max-output", "3221225472", "--yes", "--output", "/dev/null",
                "--decrypt", str(copied), data=password + b"\n",
            )
            destination = repo / "data/cache/restored"
            result = workspace_restore(repo, copied, receipt["ciphertext_sha256"], home, destination)
            assert result["decryption_verified"] is True
            assert result["submission_enabled"] is False
            counts = validate_research(destination)
            assert counts == {"jobs": 1, "datasets": 2, "features": 3, "experiments": 1}
            assert all(file_hash(destination / path) == digest for path, digest in immutable.items())
            record = {
                "status": "passed", "data_kind": "synthetic", "gpg": command("--version").decode().splitlines()[0],
                "passphrase_protected_key": True, "generation_agent_stopped_before_unlock": True,
                "controlled_stdin_unlock_then_production_noninteractive_cache_reuse": True,
                "actual_interactive_pinentry_tested": False, "counts": counts,
                "immutable_hashes_equal": True, "ciphertext_hash_checked_before_unlock": True,
                "offsite_transfer_tested": False, "windows_configured": False,
                "collector_accessed": False, "submission_enabled": False,
            }
            Path("data/cache/deployment-checks/protected-key-drill.json").write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps(record))
        finally:
            stop_agent()


if __name__ == "__main__":
    main()
