"""Durable, Actions-independent chain of verified forward-collection workspace snapshots.

The GitHub workflow keeps the canonical chain in seven-day artifacts, so a stalled runner
(issue #28) eventually loses evidence. This driver runs the same bounded read-only collection
on any machine with public egress (a laptop, server or self-hosted runner) and keeps every
verified snapshot as a permanent, hash-linked link in a local directory:

    <chain>/links/000001/{workspace.zip,workspace.sha256,lineage.txt,manifest.json,...}
    <chain>/HEAD            # "<seq> sha256:<archive hash>", replaced atomically

Every file of a link is hashed in its ``manifest.json``; each link's lineage records the
previous link's archive and manifest hashes, so no file of any link can change unnoticed.

``import-actions`` adopts the newest Actions ``forward-workspace`` artifact (checksum,
head-lineage and restore verified) as link 1 without altering its bytes, so the canonical
lineage continues. ``run`` restores the head into a fresh work directory, collects, snapshots
and publishes the next link. Links are never rewritten or deleted. Nothing here reads
credentials or enables submissions; the collection step is the existing
``entropytrade.operations.forward``.

    python -m entropytrade.operations.local_chain import-actions --chain data/cache/chain \
        --artifact-dir /path/to/downloaded --source-run 42288775503
    python -m entropytrade.operations.local_chain run --chain data/cache/chain --seconds 540
    python -m entropytrade.operations.local_chain verify --chain data/cache/chain

The chain directory must be a subdirectory of the repository's ``data/cache`` (the recovery
workspace boundary).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.api.recovery import confined, restore, snapshot
from entropytrade.api.workspace import workspace_path

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

SCHEMA = "entropytrade-local-chain-v1"
SNAPSHOT_FILES = ("workspace.zip", "workspace.sha256", "lineage.txt")
MANIFEST = "manifest.json"


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


def _check_chain_path(repo: Path, chain: Path) -> Path:
    """Refuse a chain outside data/cache before any collection work starts."""
    try:
        return workspace_path(repo, confined(repo, chain))
    except ValueError as exc:
        raise ChainError(f"chain directory refused: {exc}") from exc


def _fsync(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _links(chain: Path) -> list[Path]:
    root = chain / "links"
    if not root.is_dir():
        return []
    names = sorted(p.name for p in root.iterdir() if not p.name.startswith("."))
    if names != [f"{i:06d}" for i in range(1, len(names) + 1)]:
        raise ChainError("links are not a contiguous 000001.. sequence")
    return [root / n for n in names]


def _write_manifest(stage: Path) -> None:
    names = sorted(p.name for p in stage.iterdir() if p.is_file() and p.name != MANIFEST)
    files = {name: sha256_file(stage / name) for name in names}
    (stage / MANIFEST).write_text(
        json.dumps({"schema": SCHEMA, "files": files}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _check_link(link: Path) -> tuple[str, str]:
    """Verify every file of one link; return (archive hash, manifest hash)."""
    for name in (*SNAPSHOT_FILES, MANIFEST):
        if not (link / name).is_file():
            raise ChainError(f"{link.name}: missing {name}")
    expected = (link / "workspace.sha256").read_text(encoding="utf-8").strip()
    actual = sha256_file(link / "workspace.zip")
    if expected != actual:
        raise ChainError(f"{link.name}: snapshot checksum mismatch ({expected} != {actual})")
    try:
        listed = json.loads((link / MANIFEST).read_text(encoding="utf-8"))["files"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ChainError(f"{link.name}: unreadable manifest") from exc
    present = {p.name for p in link.iterdir() if p.name != MANIFEST}
    if not isinstance(listed, dict) or set(listed) != present:
        raise ChainError(f"{link.name}: files differ from the manifest")
    for name, digest in listed.items():
        if sha256_file(link / name) != digest:
            raise ChainError(f"{link.name}: {name} checksum mismatch")
    return actual, sha256_file(link / MANIFEST)


def _verify_links(links: list[Path]) -> tuple[str, list[dict[str, str]]]:
    previous = previous_manifest = ""
    lineages = []
    for index, link in enumerate(links, start=1):
        digest, manifest = _check_link(link)
        lineage = read_lineage(link / "lineage.txt")
        if index > 1 and (
            lineage.get("previous_sha256") != previous
            or lineage.get("previous_manifest_sha256") != previous_manifest
            or lineage.get("seq") != str(index)
        ):
            raise ChainError(f"{link.name}: previous hashes do not match link {index - 1}")
        previous, previous_manifest = digest, manifest
        lineages.append(lineage)
    return previous, lineages


def verify(chain: Path) -> dict[str, Any]:
    """Check every link's files, the previous-hash links and the HEAD pointer."""
    links = _links(chain)
    previous, _ = _verify_links(links)
    head = chain / "HEAD"
    if links:
        if not head.is_file() or head.read_text(encoding="utf-8").strip() != (
            f"{len(links)} {previous}"
        ):
            raise ChainError("HEAD does not point at the newest verified link")
    elif head.exists():
        raise ChainError("HEAD exists but there are no links")
    return {"schema": SCHEMA, "links": len(links), "head_sha256": previous or None}


def _write_head(chain: Path, seq: int, digest: str) -> None:
    temporary = chain / ".HEAD.tmp"
    temporary.write_text(f"{seq} {digest}\n", encoding="utf-8")
    _fsync(temporary)
    temporary.replace(chain / "HEAD")
    _fsync(chain)


def _roll_head_forward(chain: Path, links: list[Path]) -> bool:
    """Finish a publish interrupted between the link rename and the HEAD update.

    Only advances HEAD by exactly one link, and only after every link (including the new
    one) verified. Never rewrites or removes a link.
    """
    head = chain / "HEAD"
    if len(links) < 1:
        return False
    newest, _ = _verify_links(links)
    expected_previous = ""
    if len(links) > 1:
        expected_previous = _check_link(links[-2])[0]
    current = head.read_text(encoding="utf-8").strip() if head.is_file() else ""
    lagging = f"{len(links) - 1} {expected_previous}" if len(links) > 1 else ""
    if current == f"{len(links)} {newest}" or current != lagging:
        return False
    _write_head(chain, len(links), newest)
    return True


def _lock(chain: Path, *, shared: bool = False) -> Any:
    chain.mkdir(parents=True, exist_ok=True)
    handle = (chain / ".lock").open("a")
    try:
        fcntl.flock(handle, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise ChainError("another local-chain operation holds the chain lock") from exc
    return handle


def _publish(chain: Path, stage: Path, seq: int, digest: str) -> Path:
    """Durably make ``stage`` link ``seq`` and advance HEAD. Never replaces a link."""
    target = chain / "links" / f"{seq:06d}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ChainError(f"link {seq:06d} already exists")
    _write_manifest(stage)
    for item in stage.iterdir():
        _fsync(item)
    _fsync(stage)
    stage.rename(target)
    _fsync(target.parent)
    _write_head(chain, seq, digest)
    return target


def import_actions(
    repo: Path,
    chain: Path,
    artifact_dir: Path,
    source_run: str,
    source_branch: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Adopt a downloaded Actions ``forward-workspace`` head artifact as link 1 (verified)."""
    if not source_run.isdigit():
        raise ChainError("--source-run must be a numeric run ID")
    chain = _check_chain_path(repo, chain)
    handle = _lock(chain)
    try:
        if _links(chain):
            raise ChainError("chain already has links; import-actions only seeds an empty chain")
        for name in ("workspace.zip", "workspace.sha256", "lineage.txt"):
            if not (artifact_dir / name).is_file():
                raise ChainError(f"artifact is missing {name}")
        original = read_lineage(artifact_dir / "lineage.txt")
        # Only a canonical chain head may seed the chain; a push trial never may.
        if original.get("chain") != "head" or original.get("event") == "push":
            raise ChainError("artifact lineage is not a forward-workspace chain head")
        if original.get("run_id") != source_run:
            raise ChainError(
                f"artifact lineage run_id {original.get('run_id')!r} != --source-run {source_run}"
            )
        branch = original.get("branch", "")
        if source_branch is not None and source_branch != branch:
            raise ChainError(f"artifact lineage branch {branch!r} != --source-branch")
        expected = (artifact_dir / "workspace.sha256").read_text(encoding="utf-8").strip()
        digest = sha256_file(artifact_dir / "workspace.zip")
        if expected != digest:
            raise ChainError(f"artifact checksum mismatch ({expected} != {digest})")
        stage = chain / f".stage-{os.getpid()}"
        if stage.exists():
            raise ChainError("stale staging directory; remove it after inspection")
        stage.mkdir()
        try:
            shutil.copy2(artifact_dir / "workspace.zip", stage / "workspace.zip")
            shutil.copy2(artifact_dir / "workspace.sha256", stage / "workspace.sha256")
            # The artifact's own lineage files are retained byte-for-byte.
            shutil.copy2(artifact_dir / "lineage.txt", stage / "source-lineage.txt")
            for name in ("previous-lineage.txt", "runway-ledger.jsonl"):
                if (artifact_dir / name).is_file():
                    shutil.copy2(artifact_dir / name, stage / name)
            if sha256_file(stage / "workspace.zip") != digest:
                raise ChainError("archive changed while it was copied")
            # The restore proves the archive is readable and compatible with this commit.
            probe = chain / f".probe-{os.getpid()}"
            try:
                restore(repo, stage / "workspace.zip", probe)
            finally:
                shutil.rmtree(probe, ignore_errors=True)
            lines = [
                "seq=1",
                f"run_id={source_run}",
                f"imported_from_run={source_run}",
                f"imported_from_branch={branch}",
                f"imported_from_commit={original.get('commit', '')}",
                f"imported_at={clock().isoformat()}",
                "chain=head",
                "origin=github-actions-artifact",
                "source_lineage=source-lineage.txt",
            ]
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
            (out / "fee-capture.log").write_text(
                f"exit_code={fees.returncode}\n{fees.stderr}", encoding="utf-8"
            )
        return code

    return collect


def code_provenance(repo: Path) -> list[str]:
    """Which code collected: git commit, whether the tree was dirty, lock/project hashes."""

    def git(*args: str) -> str:
        try:
            done = subprocess.run(  # noqa: S603
                ["git", *args],  # noqa: S607
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return ""
        return done.stdout.strip()

    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--untracked-files=no") if commit else ""
    lines = [f"commit={commit}", f"worktree_dirty={'true' if dirty else 'false'}"]
    for key, name in (("uv_lock", "uv.lock"), ("pyproject", "pyproject.toml")):
        path = repo / name
        lines.append(f"{key}={sha256_file(path) if path.is_file() else ''}")
    lines.append(f"python={sys.version.split()[0]}")
    return lines


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
    if not 60 <= seconds <= 5 * 3600:
        raise ChainError("seconds must be 60-18000")
    chain = _check_chain_path(repo, chain)
    collector = collector or subprocess_collector(repo)
    handle = _lock(chain)
    try:
        links = _links(chain)
        lineages: list[dict[str, str]] = []
        if links:
            if fresh:
                raise ChainError("--fresh is refused on a chain that already has links")
            _roll_head_forward(chain, links)
            verify(chain)  # fail closed on any tampering before extending
            _, lineages = _verify_links(links)
        elif not fresh:
            raise ChainError(
                "empty chain: import-actions a verified snapshot, or pass --fresh to start "
                "a new chain deliberately"
            )
        started = clock()
        run_id = "local-" + started.strftime("%Y%m%dT%H%M%SZ")
        if any(item.get("run_id") == run_id for item in lineages):
            raise ChainError(f"run_id {run_id} already exists in the chain")
        for item in lineages:
            earlier = item.get("started_at")
            if earlier and datetime.fromisoformat(earlier) >= started:
                raise ChainError("clock is not later than an earlier link's started_at")
        seq = len(links) + 1
        stage = chain / f".stage-{os.getpid()}"
        work = chain / f".work-{os.getpid()}"
        if stage.exists() or work.exists():
            raise ChainError("stale staging/work directory; inspect and remove it")
        stage.mkdir()
        published = False
        try:
            previous_sha = previous_manifest = previous_run = ""
            ledger_in: Path | None = None
            if links:
                head = links[-1]
                previous_sha, previous_manifest = _check_link(head)
                previous_run = lineages[-1].get("run_id", "")
                restore(repo, head / "workspace.zip", work)
                if (head / "runway-ledger.jsonl").is_file():
                    ledger_in = head / "runway-ledger.jsonl"
            code = collector(work, stage, seconds, ledger_in, run_id)
            if not (work / "jobs.sqlite").is_file():
                raise ChainError("collection produced no workspace; nothing to snapshot")
            receipt = snapshot(repo, work, stage / "workspace.zip")
            (stage / "snapshot.json").write_text(
                json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
            )
            digest = sha256_file(stage / "workspace.zip")
            (stage / "workspace.sha256").write_text(digest + "\n", encoding="utf-8")
            lineage = [
                f"run_id={run_id}",
                f"seq={seq}",
                "event=local",
                "chain=head",
                f"started_at={started.isoformat()}",
                f"finished_at={datetime.now(UTC).isoformat()}",
                f"previous_seq={seq - 1}",
                f"previous_run_id={previous_run}",
                f"previous_sha256={previous_sha}",
                f"previous_manifest_sha256={previous_manifest}",
                f"collector_exit_code={code}",
                *code_provenance(repo),
            ]
            (stage / "lineage.txt").write_text("\n".join(lineage) + "\n", encoding="utf-8")
            _publish(chain, stage, seq, digest)
            published = True
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        finally:
            if published or not (work / "jobs.sqlite").is_file():
                shutil.rmtree(work, ignore_errors=True)
            else:
                # Collected evidence is never discarded: keep it for operator inspection.
                work.rename(chain / f".failed-{run_id}-{os.getpid()}")
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


def _terminate(signum: int, _frame: FrameType | None) -> None:
    # Raising lets subprocess.run kill the collector child and every cleanup run.
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("import-actions", "run", "verify"):
        item = sub.add_parser(name)
        item.add_argument("--chain", type=Path, required=True)
        if name == "import-actions":
            item.add_argument("--artifact-dir", type=Path, required=True)
            item.add_argument("--source-run", required=True)
            item.add_argument("--source-branch", default=None)
        if name == "run":
            item.add_argument("--seconds", type=int, default=540)
            item.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, _terminate)
    repo = Path(__file__).resolve().parents[4]
    chain = args.chain if args.chain.is_absolute() else repo / args.chain
    try:
        if args.action == "verify":
            handle = _lock(chain, shared=True)
            try:
                result = verify(chain)
            finally:
                handle.close()
        elif args.action == "import-actions":
            result = import_actions(
                repo, chain, args.artifact_dir.absolute(), args.source_run, args.source_branch
            )
        else:
            result = run(repo, chain, args.seconds, fresh=args.fresh)
    except (ChainError, ValueError, OSError) as exc:
        parser.exit(1, f"Local chain refused: {exc}\n")
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    if result.get("collector_exit_code"):
        sys.exit(1)


if __name__ == "__main__":
    main()
