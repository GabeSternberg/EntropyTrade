"""Read-only committed source export and bounded acceptance checks; no Git writes."""

import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


bundle = Path(__file__).resolve().parent
repo = bundle.parents[2]
checkout = repo / ".acceptance-20261026T042230Z"
checks = bundle / "checks.json"
env = {
    "PATH": "/Users/gabriel/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "UV_CACHE_DIR": str(repo / "data/cache/acceptance-20261025T191200Z/uv"),
    "UV_OFFLINE": "1",
    "UV_PYTHON_DOWNLOADS": "never",
    "UV_PYTHON": sys._base_executable,
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "LOKY_MAX_CPU_COUNT": "1",
    "PYTEST_ADDOPTS": "--tb=short",
    "TZ": "UTC",
    "TMPDIR": str(repo / "data/cache/acceptance-20261025T191200Z"),
}


def git_read(*args):
    return subprocess.check_output(["git", *args], cwd=repo, env=env)


def save():
    checks.write_text(json.dumps(receipt, indent=2) + "\n")


if sys.argv[1:] == ["setup"]:
    assert not checkout.exists(), "Never overwrite an earlier export"
    assert not git_read("status", "--porcelain=v1", "--untracked-files=no"), "Tracked tree must be clean"
    commit = git_read("rev-parse", "HEAD").decode().strip()
    tree = git_read("rev-parse", "HEAD^{tree}").decode().strip()
    archive = git_read("archive", "--format=tar", commit)
    checkout.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(checkout, filter="data")
    manifest = {
        p.relative_to(checkout).as_posix(): digest(p)
        for p in checkout.rglob("*") if p.is_file()
    }
    (bundle / "export-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    receipt = {
        "started_at_utc": now(), "commit": commit, "tree": tree,
        "branch": git_read("branch", "--show-current").decode().strip(),
        "method": "Read-only git archive export, no Git checkout, branch, index or ref mutation",
        "checkout": str(checkout.relative_to(repo)),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "tracked_files": len(manifest), "environment": env, "commands": [],
        "limitations": [
            "Clean source export is not the supervisor independent clean-checkout sign-off.",
            "Browser access denied; no browser acceptance is claimed.",
        ],
    }
    commands = [
        ("lock-check", ["uv", "lock", "--check"]),
        ("locked-sync", ["uv", "sync", "--locked"]),
        ("entrypoint-help", ["uv", "run", "--locked", "entropytrade-web", "--help"]),
    ]
elif sys.argv[1:] == ["gates"]:
    receipt = json.loads(checks.read_text())
    manifest = json.loads((bundle / "export-manifest.json").read_text())
    assert receipt["environment"] == env
    assert all(c["exit_code"] == 0 for c in receipt["commands"])
    assert [c["name"] for c in receipt["commands"]] == ["lock-check", "locked-sync", "entrypoint-help"]
    commands = [
        ("make-check", ["make", "check"]),
        ("javascript-syntax", ["node", "--check", "frontend/src/app.js"]),
        ("frontend", ["node", "--test", "frontend/tests/acquisition.test.cjs"]),
    ]
else:
    raise SystemExit("Use setup or gates")

assert all(digest(checkout / name) == expected for name, expected in manifest.items())
save()
for name, command in commands:
    log = bundle / (name + ".log")
    started = now()
    print(f"{started} starting {name}", flush=True)
    timed_out = False
    with log.open("w") as output:
        process = subprocess.Popen(command, cwd=checkout, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            code = 124
    receipt["commands"].append({
        "name": name, "command": command, "started_at_utc": started,
        "finished_at_utc": now(), "exit_code": code, "timeout": timed_out,
        "deadline_seconds": 600, "log": log.name, "sha256": digest(log),
    })
    save()
    print(f"{now()} finished {name}: exit {code}", flush=True)
    if sys.argv[1] == "setup" and code:
        break
receipt["modified_exported_files"] = [
    name for name, expected in manifest.items()
    if not (checkout / name).is_file() or digest(checkout / name) != expected
]
receipt["finished_at_utc"] = now()
save()
assert not receipt["modified_exported_files"], "A committed source file changed"
raise SystemExit(1 if any(c["exit_code"] for c in receipt["commands"]) else 0)
