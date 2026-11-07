"""Durable, Actions-independent chain of verified forward-collection workspace snapshots.

The GitHub workflow keeps the canonical chain in seven-day artifacts, so a stalled runner
(issue #28) eventually loses evidence. This driver runs the same bounded read-only collection
on any machine with public egress (a laptop, server or self-hosted runner) and keeps every
verified snapshot as a permanent, hash-linked link in a local directory:

    <chain>/links/000001/{workspace.zip,workspace.sha256,lineage.txt,summary.json,...}
    <chain>/HEAD            # "<seq> sha256:<archive hash>", replaced atomically

``import-actions`` adopts the newest Actions ``forward-workspace`` artifact (checksum and
restore verified) as link 1 without altering it, so the canonical lineage continues. ``run``
restores the head into a fresh work directory, collects, snapshots and publishes the next
link. Links are never rewritten or deleted. Nothing here reads credentials or enables
submissions; the collection step is the existing ``entropytrade.operations.forward``.

    python -m entropytrade.operations.local_chain import-actions --chain data/cache/chain \
        --artifact-dir /path/to/downloaded --source-run 42288775503
    python -m entropytrade.operations.local_chain run --chain data/cache/chain --seconds 540
    python -m entropytrade.operations.local_chain verify --chain data/cache/chain

The chain directory must be inside the repository (recovery refuses outside paths).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.api.recovery import restore, snapshot

if TYPE_CHECKING:
    from collections.abc import Callable

SCHEMA = "entropytrade-local-chain-v1"
SNAPSHOT_FILES = ("workspace.zip", "workspace.sha256", "lineage.txt")
OPTIONAL_FILES = ("runway-ledger.jsonl", "summary.json", "server.log", "fee-capture.json")


class ChainError(RuntimeError):
    """The chain is inconsistent or an operation was refused (fail closed)."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def read_lineage(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key] = value
    return out


def _links(chain: Path) -> list[Path]:
    root = chain / "links"
    if not root.is_dir():
        return []
    names = sorted(p.name for p in root.iterdir() if not p.name.startswith("."))
    if names != [f"{i:06d}" for i in range(1, len(names) + 1)]:
        raise ChainError("links are not a contiguous 000001.. sequence")
    return [root / n for n in names]


def _check_link(link: Path) -> str:
    """Verify one link's archive against its recorded checksum; return the checksum."""
    for name in SNAPSHOT_FILES:
        if not (link / name).is_file():
            raise ChainError(f"{link.name}: missing {name}")
    expected = (link / "workspace.sha256").read_text(encoding="utf-8").strip()
    actual = sha256_file(link / "workspace.zip")
    if expected != actual:
        raise ChainError(f"{link.name}: snapshot checksum mismatch ({expected} != {actual})")
    return actual


def verify(chain: Path) -> dict[str, Any]:
    """Check every link's checksum, the previous-hash links and the HEAD pointer."""
    links = _links(chain)
    previous = ""
    for index, link in enumerate(links, start=1):
        digest = _check_link(link)
        lineage = read_lineage(link / "lineage.txt")
        if index > 1 and lineage.get("previous_sha256") != previous:
            raise ChainError(f"{link.name}: previous_sha256 does not match link {index - 1}")
        previous = digest
    head = chain / "HEAD"
    if links:
        if not head.is_file() or head.read_text(encoding="utf-8").strip() != (
            f"{len(links)} {previous}"
        ):
            raise ChainError("HEAD does not point at the newest verified link")
    elif head.exists():
        raise ChainError("HEAD exists but there are no links")
    return {"schema": SCHEMA, "links": len(links), "head_sha256": previous or None}


def _lock(chain: Path) -> Any:
    chain.mkdir(parents=True, exist_ok=True)
    handle = (chain / ".lock").open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise ChainError("another local-chain operation holds the chain lock") from exc
    return handle


def _publish(chain: Path, stage: Path, seq: int, digest: str) -> Path:
    """Atomically make ``stage`` link ``seq`` and advance HEAD. Never replaces a link."""
    target = chain / "links" / f"{seq:06d}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ChainError(f"link {seq:06d} already exists")
    stage.rename(target)
    temporary = chain / ".HEAD.tmp"
    temporary.write_text(f"{seq} {digest}\n", encoding="utf-8")
    temporary.replace(chain / "HEAD")
    return target


def import_actions(
    repo: Path, chain: Path, artifact_dir: Path, source_run: str, source_branch: str = "main"
) -> dict[str, Any]:
    """Adopt a downloaded Actions ``forward-workspace`` artifact as link 1 (verified)."""
    if not source_run.isdigit():
        raise ChainError("--source-run must be a numeric run ID")
    handle = _lock(chain)
    try:
        if _links(chain):
            raise ChainError("chain already has links; import-actions only seeds an empty chain")
        for name in ("workspace.zip", "workspace.sha256"):
            if not (artifact_dir / name).is_file():
                raise ChainError(f"artifact is missing {name}")
        expected = (artifact_dir / "workspace.sha256").read_text(encoding="utf-8").strip()
        digest = sha256_file(artifact_dir / "workspace.zip")
        if expected != digest:
            raise ChainError(f"artifact checksum mismatch ({expected} != {digest})")
        stage = chain / f".stage-{os.getpid()}"
        if stage.exists():
            raise ChainError("stale staging directory; remove it after inspection")
        stage.mkdir()
        try:
            for name in ("workspace.zip", "workspace.sha256", "runway-ledger.jsonl"):
                if (artifact_dir / name).is_file():
                    shutil.copy2(artifact_dir / name, stage / name)
            # The restore proves the archive is readable and compatible with this commit.
            probe = chain / f".probe-{os.getpid()}"
            try:
                restore(repo, stage / "workspace.zip", probe)
            finally:
                shutil.rmtree(probe, ignore_errors=True)
            original = artifact_dir / "lineage.txt"
            lines = [
                f"imported_from_run={source_run}",
                f"imported_from_branch={source_branch}",
                f"imported_at={datetime.now(UTC).isoformat()}",
                "chain=head",
                "origin=github-actions-artifact",
            ]
            if original.is_file():
                lines += ["original_lineage_begin"]
                lines += ["# " + line for line in original.read_text(encoding="utf-8").splitlines()]
                lines += ["original_lineage_end"]
            (stage / "lineage.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            _publish(chain, stage, 1, digest)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        return {"schema": SCHEMA, "action": "import-actions", "seq": 1, "sha256": digest}
    finally:
        handle.close()


def subprocess_collector(repo: Path) -> Callable[..., int]:
    """Run the existing bounded collector and fee capture as separate processes."""

    def collect(
        workspace: Path, out: Path, seconds: int, ledger_in: Path | None, run_id: str
    ) -> int:
        cmd = [
            sys.executable,
            "-m",
            "entropytrade.operations.forward",
            "--workspace",
            str(workspace),
            "--seconds",
            str(seconds),
            "--summary",
            str(out / "summary.json"),
            "--log",
            str(out / "server.log"),
            "--ledger-out",
            str(out / "runway-ledger.jsonl"),
            "--run-id",
            run_id,
        ]
        if ledger_in is not None:
            cmd += ["--ledger-in", str(ledger_in)]
        code = subprocess.run(cmd, cwd=repo, check=False).returncode  # noqa: S603
        if (workspace / "jobs.sqlite").is_file():
            fees = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "entropytrade.execution.fee_admin",
                    "--workspace",
                    str(workspace),
                    "--capture-due",
                    "schedule",
                    "rounding",
                ],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            (out / "fee-capture.json").write_text(fees.stdout, encoding="utf-8")
        return code

    return collect


def run(
    repo: Path,
    chain: Path,
    seconds: int,
    *,
    fresh: bool = False,
    collector: Callable[..., int] | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Restore the head, collect for a bounded window, snapshot and publish the next link."""
    collector = collector or subprocess_collector(repo)
    handle = _lock(chain)
    try:
        links = _links(chain)
        if links:
            if fresh:
                raise ChainError("--fresh is refused on a chain that already has links")
            verify(chain)  # fail closed on any tampering before extending
        elif not fresh:
            raise ChainError(
                "empty chain: import-actions a verified snapshot, or pass --fresh to start "
                "a new chain deliberately"
            )
        started = clock()
        run_id = "local-" + started.strftime("%Y%m%dT%H%M%SZ")
        seq = len(links) + 1
        stage = chain / f".stage-{os.getpid()}"
        work = chain / f".work-{os.getpid()}"
        if stage.exists() or work.exists():
            raise ChainError("stale staging/work directory; inspect and remove it")
        stage.mkdir()
        try:
            previous_sha = ""
            ledger_in: Path | None = None
            if links:
                head = links[-1]
                previous_sha = _check_link(head)
                restore(repo, head / "workspace.zip", work)
                if (head / "runway-ledger.jsonl").is_file():
                    ledger_in = head / "runway-ledger.jsonl"
            code = collector(work, stage, seconds, ledger_in, run_id)
            if not (work / "jobs.sqlite").is_file():
                raise ChainError("collection produced no workspace; nothing to snapshot")
            snapshot(repo, work, stage / "workspace.zip")
            digest = sha256_file(stage / "workspace.zip")
            (stage / "workspace.sha256").write_text(digest + "\n", encoding="utf-8")
            lock = repo / "uv.lock"
            lineage = [
                f"run_id={run_id}",
                f"seq={seq}",
                "event=local",
                "chain=head",
                f"started_at={started.isoformat()}",
                f"previous_seq={seq - 1}",
                f"previous_sha256={previous_sha}",
                f"collector_exit_code={code}",
                f"uv_lock=sha256:{sha256_file(lock)[7:]}" if lock.is_file() else "uv_lock=",
            ]
            (stage / "lineage.txt").write_text("\n".join(lineage) + "\n", encoding="utf-8")
            _publish(chain, stage, seq, digest)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return {
            "schema": SCHEMA,
            "action": "run",
            "seq": seq,
            "sha256": digest,
            "collector_exit_code": code,
            "submission_enabled": False,
        }
    finally:
        handle.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("import-actions", "run", "verify"):
        item = sub.add_parser(name)
        item.add_argument("--chain", type=Path, required=True)
        if name == "import-actions":
            item.add_argument("--artifact-dir", type=Path, required=True)
            item.add_argument("--source-run", required=True)
            item.add_argument("--source-branch", default="main")
        if name == "run":
            item.add_argument("--seconds", type=int, default=540)
            item.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    chain = args.chain if args.chain.is_absolute() else repo / args.chain
    try:
        if args.action == "verify":
            result = verify(chain)
        elif args.action == "import-actions":
            result = import_actions(
                repo, chain, args.artifact_dir, args.source_run, args.source_branch
            )
        else:
            if not 60 <= args.seconds <= 5 * 3600:
                parser.error("--seconds must be 60-18000")
            result = run(repo, chain, args.seconds, fresh=args.fresh)
    except (ChainError, ValueError, OSError) as exc:
        parser.exit(1, f"Local chain refused: {exc}\n")
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    if result.get("collector_exit_code"):
        sys.exit(1)


if __name__ == "__main__":
    main()
