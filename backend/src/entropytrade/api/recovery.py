"""Offline, bounded, checksummed workspace snapshot/restore. Never loads executable models."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo

from entropytrade.api.jobs import identifier, timestamp, validate_request
from entropytrade.api.workspace import workspace_lease, workspace_path
from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import StrategySpec
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather

SCHEMA = "entropytrade-workspace-v1"
MAX_FILES = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_BYTES = 2 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
TABLES = {
    "jobs": "id request status created_at updated_at detail result",
    "events": "sequence job_id at stage detail",
    "monitors": (
        "id job_id candidate_id family spec spec_hash status interval_seconds next_at "
        "created_at failures model_binding"
    ),
    "shadow_cycles": "id monitor_id sequence status started_at finished_at detail result digest",
    "shadow_events": "sequence monitor_id at action",
    "shadow_contracts": "monitor_id ticker market last_attempt outcome",
}
RUNTIME = {
    ".writer.lock",
    "jobs.sqlite-wal",
    "jobs.sqlite-shm",
    "registry.sqlite-wal",
    "registry.sqlite-shm",
    "matplotlib",
}


def validate_registry(root: Path, reviews: list[dict[str, Any]]) -> None:
    path = root / "registry.sqlite"
    if not path.is_file():
        if reviews:
            raise ValueError("research workspace is missing its lineage registry")
        return
    db = sqlite3.connect(path.as_uri() + "?mode=ro")
    try:
        db.execute("PRAGMA trusted_schema=OFF")
        tables = {
            "strategy_experiments",
            "agent_hypotheses",
            "agent_research_runs",
            "probability_runs",
            "probability_models",
            "probability_predictions",
            "specs",
            "states",
            "verdicts",
            "backtests",
            "transitions",
        }
        if set(db.execute("SELECT type, name FROM sqlite_master WHERE type != 'index'")) != {
            ("table", t) for t in tables
        } or [r[0] for r in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ValueError("corrupt or unsupported lineage registry")
        for review in reviews:
            if (
                review.get("status") != "research_failed"
                and not db.execute(
                    "SELECT 1 FROM strategy_experiments WHERE experiment_id=?",
                    (review["experiment_id"],),
                ).fetchone()
            ) or not db.execute(
                "SELECT 1 FROM agent_research_runs WHERE run_id=?", (review["research_run"],)
            ).fetchone():
                raise ValueError("research result is missing registry lineage")
    finally:
        db.close()


def backup_database(source: Path, target: Path) -> None:
    original = sqlite3.connect(source.as_uri() + "?mode=ro")
    copied = sqlite3.connect(target)
    try:
        original.backup(copied)
        copied.execute("PRAGMA journal_mode=DELETE")
    finally:
        copied.close()
        original.close()


def confined(repo: Path, path: Path) -> Path:
    """Reject links, including parent links, before reading any workspace/archive bytes."""
    root = repo.absolute()
    path = path.absolute()
    if not path.is_relative_to(root) or ".." in path.parts:
        raise ValueError("recovery paths must stay within this repository")
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("recovery paths must not contain symlinks")
    return path


def relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(p in {".", ".."} for p in path.parts)
        or str(path) != value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError("unsafe snapshot member path")
    return value


def application(repo: Path) -> dict[str, str]:
    return {name: file_hash(repo / name) for name in ("pyproject.toml", "uv.lock")}


def check_artifacts(root: Path, artifacts: list[dict[str, Any]]) -> None:
    seen = set()
    for item in artifacts:
        name = relative(item["path"])
        if name in seen:
            raise ValueError("duplicate evidence artifact")
        seen.add(name)
        path = root / name
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != item["bytes"]
            or file_hash(path) != item["sha256"]
        ):
            raise ValueError("missing or corrupt evidence artifact: " + name)


def validate_database(root: Path) -> dict[str, int]:
    """Read-only schema, references and content validation; no migration or clock changes."""
    db = sqlite3.connect((root / "jobs.sqlite").as_uri() + "?mode=ro")
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA trusted_schema=OFF")
        objects = db.execute(
            "SELECT type, name FROM sqlite_master WHERE type != 'index'"
        ).fetchall()
        if {(r["type"], r["name"]) for r in objects} != {("table", t) for t in TABLES}:
            raise ValueError("unsupported or incomplete workspace database schema")
        for table, columns in TABLES.items():
            if [r[1] for r in db.execute(f"PRAGMA table_info({table})")] != columns.split():
                raise ValueError("unsupported workspace database columns")
        if [r[0] for r in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ValueError("corrupt workspace database")
        jobs = {identifier(r["id"]): dict(r) for r in db.execute("SELECT * FROM jobs")}
        reviews = []
        for job_id, job in jobs.items():
            validate_request(json.loads(job["request"]), stored=True)
            if job["status"] not in {
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            }:
                raise ValueError("invalid restored job state")
            if job["status"] == "completed" and job["result"] is None:
                raise ValueError("completed job has no result")
            if job["result"] is not None:
                result = json.loads(job["result"])
                check_artifacts(root / "runs" / job_id / "workflow", result.get("artifacts", []))
                if result.get("schema") == "workbench-review-v1":
                    reviews.append(result)
                    review = root / "runs" / job_id / "review.json"
                    if not review.is_file() or json.loads(review.read_text()) != result:
                        raise ValueError("missing or inconsistent research review")
        validate_registry(root, reviews)
        monitors = {identifier(r["id"]): dict(r) for r in db.execute("SELECT * FROM monitors")}
        for monitor in monitors.values():
            if monitor["job_id"] not in jobs or monitor["status"] not in {"active", "paused"}:
                raise ValueError("invalid restored monitor reference/state")
            spec = StrategySpec.model_validate_json(monitor["spec"])
            if spec.spec_hash() != monitor["spec_hash"]:
                raise ValueError("restored strategy hash mismatch")
            if monitor["model_binding"] is None:
                # The store's legacy migration leaves SQL NULL unbound. Preserve it;
                # scoring still refuses it, and recovery must never freeze a model.
                continue
            binding = json.loads(monitor["model_binding"])
            if not isinstance(binding, dict):
                raise ValueError("invalid restored model binding")
            if scientific_hash(
                {k: v for k, v in binding.items() if k != "binding_hash"}
            ) != binding.get("binding_hash"):
                raise ValueError("restored model binding hash mismatch")
            if binding["status"] == "bound":
                model = FrozenWeather.model_validate(binding["snapshot"])
                if (
                    model.data_kind != "real"
                    or spec.model_ref is None
                    or model.model_hash != spec.model_ref.version
                    or model.family != spec.model_ref.family
                ):
                    raise ValueError("restored model reference mismatch")
            elif binding["status"] != "blocked" or binding["snapshot"] is not None:
                raise ValueError("invalid restored model binding")
        sequences: dict[str, list[int]] = {m: [] for m in monitors}
        for row in db.execute("SELECT * FROM shadow_cycles ORDER BY sequence"):
            monitor_id, cycle_id = row["monitor_id"], identifier(row["id"])
            if monitor_id not in monitors or row["status"] not in {
                "running",
                "completed",
                "failed",
                "interrupted",
            }:
                raise ValueError("invalid restored cycle reference/state")
            sequences[monitor_id].append(row["sequence"])
            if row["status"] in {"completed", "failed"} and row["result"] is None:
                raise ValueError("finished cycle has no result")
            if row["result"] is not None:
                result = json.loads(row["result"])
                if (
                    scientific_hash(result) != row["digest"]
                    or result["submission_enabled"] is not False
                ):
                    raise ValueError("restored cycle digest/safety mismatch")
                cycle = root / "shadow" / monitor_id / cycle_id
                check_artifacts(cycle, result["artifacts"])
                result_file = cycle / "result.json"
                if row["status"] == "completed" and not result_file.is_file():
                    raise ValueError("completed cycle is missing result bytes")
                if result_file.is_file() and json.loads(result_file.read_text()) != result:
                    raise ValueError("cycle result disagrees with database")
        if any(seq != list(range(1, len(seq) + 1)) for seq in sequences.values()):
            raise ValueError("incomplete cycle sequence")
        for table, field, references in (
            ("events", "job_id", jobs),
            ("shadow_events", "monitor_id", monitors),
            ("shadow_contracts", "monitor_id", monitors),
        ):
            if any(r[0] not in references for r in db.execute(f"SELECT {field} FROM {table}")):  # noqa: S608 - fixed names
                raise ValueError("orphaned workspace evidence")
        return {
            "jobs": len(jobs),
            "monitors": len(monitors),
            "cycles": sum(map(len, sequences.values())),
        }
    finally:
        db.close()


def inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    total = 0
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or not (path.is_dir() or stat.S_ISREG(path.stat().st_mode)):
            raise ValueError("workspace contains a link or special file")
        if path.is_dir():
            if len(directories) >= MAX_FILES:
                raise ValueError("workspace exceeds directory budget")
            directories.append(name)
            continue
        size = path.stat().st_size
        total += size
        if len(files) >= MAX_FILES or size > MAX_FILE_BYTES or total > MAX_BYTES:
            raise ValueError("workspace exceeds snapshot size budget")
        files.append({"path": name, "bytes": size, "sha256": file_hash(path)})
    return files, directories


@contextmanager
def snapshot_lease(repo: Path, workspace: Path, archive: Path) -> Iterator[dict[str, Any]]:
    """Snapshot an existing source and retain its lease through the caller's inspection.

    No application store may be opened before entering this context. Keeping the lease
    here lets offline verification inspect/compare the same source without reacquiring it.
    """
    root = workspace_path(repo, confined(repo, workspace))
    archive = confined(repo, archive)
    if archive.is_relative_to(root) or archive.exists():
        raise ValueError("snapshot requires a new archive outside the workspace")
    if not root.is_dir() or not (root / "jobs.sqlite").is_file():
        raise ValueError("workspace has no database")
    confined(repo, root / "jobs.sqlite")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with workspace_lease(root), TemporaryDirectory(prefix=".snapshot-", dir=archive.parent) as name:
        stage = Path(name)
        payload = stage / "payload"
        payload.mkdir()
        # Maintenance holds the same lease as the server. Capture WAL consistently and
        # copy all authoritative data, including opaque model bytes, without loading them.
        for child in root.iterdir():
            if child.is_symlink():
                raise ValueError("workspace contains a symlink")
            if child.name in RUNTIME or child.name in {"jobs.sqlite", "registry.sqlite"}:
                continue
            if child.name not in {"runs", "shadow"} or not child.is_dir():
                raise ValueError("unexpected workspace entry: " + child.name)
            inventory(child)  # reject nested links/special files before copying
            shutil.copytree(child, payload / child.name)
        backup_database(root / "jobs.sqlite", payload / "jobs.sqlite")
        if (root / "registry.sqlite").is_file():
            backup_database(root / "registry.sqlite", payload / "registry.sqlite")
        counts = validate_database(payload)
        files, directories = inventory(payload)
        manifest = {
            "schema": SCHEMA,
            "created_at": timestamp(),
            "application": application(repo),
            "files": files,
            "directories": directories,
            "counts": counts,
            "submission_enabled": False,
        }
        temporary = stage / "workspace.zip"
        encoded_manifest = json.dumps(manifest, sort_keys=True)
        if len(encoded_manifest.encode()) > MAX_MANIFEST_BYTES:
            raise ValueError("workspace exceeds snapshot manifest budget")
        with ZipFile(temporary, "w") as bundle:
            bundle.writestr("manifest.json", encoded_manifest)
            for item in files:
                bundle.write(payload / item["path"], "files/" + item["path"])
        temporary.chmod(0o600)
        os.link(temporary, archive)  # publish without replacing any existing evidence
        yield {
            "archive": str(archive),
            "sha256": file_hash(archive),
            **counts,
            "submission_enabled": False,
        }


def snapshot(repo: Path, workspace: Path, archive: Path) -> dict[str, Any]:
    with snapshot_lease(repo, workspace, archive) as receipt:
        return receipt


def unpack(repo: Path, archive: Path, stage: Path) -> dict[str, Any]:
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or len(names) > MAX_FILES + 1:
            raise ValueError("duplicate/excessive snapshot members")
        for member in members:
            relative(member.filename)
            mode = member.external_attr >> 16
            if (
                member.is_dir()
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                or member.flag_bits & 1
            ):
                raise ValueError("snapshot members must be unencrypted regular files")
        if (
            "manifest.json" not in names
            or bundle.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES
        ):
            raise ValueError("missing/oversized snapshot manifest")
        manifest = json.loads(bundle.read("manifest.json"))
        if (
            manifest["schema"] != SCHEMA
            or manifest["application"] != application(repo)
            or manifest["submission_enabled"] is not False
        ):
            raise ValueError("unsupported snapshot schema/application/safety")
        files = manifest["files"]
        for item in files:
            parts = PurePosixPath(relative(item["path"])).parts
            if parts not in {("jobs.sqlite",), ("registry.sqlite",)} and (
                len(parts) < 2 or parts[0] not in {"runs", "shadow"}
            ):
                raise ValueError("unexpected snapshot workspace entry")
        expected = {"files/" + relative(f["path"]) for f in files}
        if (
            len(files) > MAX_FILES
            or len(expected) != len(files)
            or set(names) != expected | {"manifest.json"}
        ):
            raise ValueError("incomplete snapshot member inventory")
        total = 0
        for item in files:
            info: ZipInfo = bundle.getinfo("files/" + item["path"])
            size = item["bytes"]
            total += info.file_size
            if (
                type(size) is not int
                or size < 0
                or size != info.file_size
                or size > MAX_FILE_BYTES
                or total > MAX_BYTES
            ):
                raise ValueError("snapshot exceeds size budget or has invalid sizes")
        directories = manifest["directories"]
        if not isinstance(directories, list) or len(directories) > MAX_FILES:
            raise ValueError("snapshot exceeds directory budget")
        for directory in directories:
            if PurePosixPath(relative(directory)).parts[0] not in {"runs", "shadow"}:
                raise ValueError("unexpected snapshot directory")
            (stage / relative(directory)).mkdir(parents=True, exist_ok=True)
        for item in files:
            path = stage / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with bundle.open("files/" + item["path"]) as source, path.open("xb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
                    digest.update(chunk)
            path.chmod(0o600)
            if "sha256:" + digest.hexdigest() != item["sha256"]:
                raise ValueError("snapshot checksum mismatch: " + item["path"])
        counts = validate_database(stage)
        if counts != manifest["counts"]:
            raise ValueError("snapshot database counts mismatch")
        return counts


def restore(repo: Path, archive: Path, workspace: Path) -> dict[str, Any]:
    archive = confined(repo, archive)
    destination = workspace_path(repo, confined(repo, workspace))
    if destination.exists():
        raise ValueError("restore requires a new workspace; existing data is never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".restore-", dir=destination.parent) as name:
        stage = Path(name) / "workspace"
        stage.mkdir(mode=0o700)
        try:
            counts = unpack(repo, archive, stage)
        except (BadZipFile, sqlite3.Error, KeyError, TypeError, UnicodeError, OSError) as exc:
            raise ValueError("invalid or incomplete snapshot: " + type(exc).__name__) from exc
        # No database recovery occurs until normal server startup; paused states and
        # every original timestamp remain untouched. Never fit/promote on restore.
        if destination.exists():
            raise ValueError("restore destination appeared during verification")
        stage.rename(destination)
    return {
        "workspace": str(destination),
        "archive_sha256": file_hash(archive),
        **counts,
        "submission_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "restore"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    try:
        result = (snapshot if args.action == "snapshot" else restore)(
            repo, workspace=args.workspace, archive=args.archive
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Recovery refused: {exc}\n")
    print(json.dumps(result, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
