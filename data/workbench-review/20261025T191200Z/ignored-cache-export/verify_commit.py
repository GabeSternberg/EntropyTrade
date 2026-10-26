"""Read-only commit export and locked acceptance checks; never mutates Git state."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


repo = Path(__file__).resolve().parents[3]
bundle = Path(__file__).resolve().parent
checkout = repo / "data/cache/acceptance-20261025T191200Z/checkout-cached"
assert not checkout.exists(), "Use a fresh export; never overwrite an earlier acceptance run"
status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=repo).decode()
assert not status, "Tracked source must be clean before export"
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip()
tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repo).decode().strip()
archive = subprocess.check_output(["git", "archive", "--format=tar", commit], cwd=repo)
checkout.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(checkout, filter="data")
files = {p.relative_to(checkout).as_posix(): digest(p) for p in checkout.rglob("*") if p.is_file()}
(bundle / "export-manifest.json").write_text(json.dumps(files, indent=2, sort_keys=True) + "\n")
receipt = {
    "started_at": now(), "commit": commit, "tree": tree,
    "source_status_before_export": "tracked tree clean; only this new evidence directory untracked",
    "method": "git archive read-only export, no checkout/branch/index/ref mutation",
    "checkout": str(checkout.relative_to(repo)),
    "archive_sha256": hashlib.sha256(archive).hexdigest(),
    "tracked_files": len(files), "commands": [],
    "limitations": ["A clean source export is not a supervisor-created independent Git checkout.",
                    "Browser acceptance blocked; no browser evidence is claimed."],
}
env = {
    "PATH": "/Users/gabriel/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "UV_CACHE_DIR": str(repo / "data/cache/acceptance-20261025T191200Z/uv"),
    "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never",
    "UV_PYTHON": sys._base_executable,
    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "LOKY_MAX_CPU_COUNT": "1",
    "PYTEST_ADDOPTS": "--tb=short", "TZ": "UTC",
    "TMPDIR": str(repo / "data/cache/acceptance-20261025T191200Z"),
}
receipt["environment"] = env


def save():
    (bundle / "checks.json").write_text(json.dumps(receipt, indent=2) + "\n")


save()
for name, command in [
    ("lock-check", ["uv", "lock", "--check"]),
    ("dependency-sync", ["uv", "sync", "--locked"]),
    ("entrypoint-help", ["uv", "run", "--locked", "entropytrade-web", "--help"]),
    ("make-check", ["make", "check"]),
    ("javascript-syntax", ["node", "--check", "frontend/src/app.js"]),
    ("frontend-check", ["node", "--test", "frontend/tests/acquisition.test.cjs"]),
]:
    started = now()
    log = bundle / (name + ".log")
    print(f"{started} starting {name}", flush=True)
    with log.open("w") as output:
        result = subprocess.run(command, cwd=checkout, env=env, stdout=output, stderr=subprocess.STDOUT)
    receipt["commands"].append({"name": name, "command": command, "cwd": str(checkout.relative_to(repo)),
                                "started_at": started, "finished_at": now(), "exit_code": result.returncode,
                                "log": log.name, "sha256": digest(log)})
    save()
    print(f"{now()} finished {name}: exit {result.returncode}", flush=True)
    if name == "dependency-sync" and result.returncode:
        break
receipt["modified_exported_files"] = [name for name, expected in files.items()
                                      if not (checkout / name).is_file() or digest(checkout / name) != expected]
receipt["finished_at"] = now()
save()
assert not receipt["modified_exported_files"], "Verification changed an exported committed file"
