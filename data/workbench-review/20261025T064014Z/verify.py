"""Retained driver for this verification attempt; no browser success is inferred here.

Run with .venv/bin/python from the checkout. Uses actual isolated workers, public GETs,
and the unchanged required suite. It never merges, pushes or accesses credentials.
"""

import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from entropytrade.api.jobs import TERMINAL, Jobs
from entropytrade.api.runner import Runner
from entropytrade.data.sources import file_hash

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
WORKSPACE = REPO / "data/cache/workbench-verification-20261025T064014Z"
RECEIPT = {"started_at": datetime.now(UTC).isoformat(), "commands": [], "runs": []}


def save():
    (ROOT / "receipt.json").write_text(json.dumps(RECEIPT, indent=2, sort_keys=True) + "\n")


def check(name, command, timeout=600):
    start = datetime.now(UTC).isoformat()
    before = time.monotonic()
    try:
        completed = subprocess.run(
            command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, check=False,
        )
        output, code = completed.stdout, completed.returncode
    except subprocess.TimeoutExpired as exc:
        output, code = (exc.stdout or b"") + b"\nVerification command timed out.\n", None
    (ROOT / f"{name}.log").write_bytes(output)
    RECEIPT["commands"].append({
        "name": name, "command": command, "started_at": start,
        "finished_at": datetime.now(UTC).isoformat(), "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - before, 3),
        "log": f"{name}.log", "sha256": file_hash(ROOT / f"{name}.log"),
    })
    save()
    print(f"{name}: exit {code}", flush=True)


check("lock-check", ["uv", "lock", "--check"])
check("dependency-sync", ["uv", "sync", "--locked"])
check("entrypoint-help", [str(REPO / ".venv/bin/entropytrade-web"), "--help"])
check("listener-launch", [
    str(REPO / ".venv/bin/entropytrade-web"), "--port", "43128",
    "--workspace", str(WORKSPACE),
], timeout=5)
check("make-check", [
    "/usr/bin/env", "UV_CACHE_DIR=data/cache/uv-verification", "UV_OFFLINE=1",
    "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "LOKY_MAX_CPU_COUNT=1",
    "PYTEST_ADDOPTS=--tb=short", "make", "check",
])
check("javascript-syntax", ["node", "--check", "frontend/src/app.js"])
check("diff-check", ["git", "diff", "--check"])

jobs = Jobs(WORKSPACE)
for label, family, mode, idea in (
    ("recorded-weather", "weather", "recorded", "Test revision_f >= 1.25 and hours_to_close < 8"),
    ("synthetic-weather", "weather", "synthetic", "Verify protected synthetic model replay"),
    ("public-weather", "weather", "public", "Research forecast_high_f > 70"),
    ("public-bitcoin", "bitcoin", "public", "Research spot_minus_floor_usd > 1000"),
):
    started = datetime.now(UTC).isoformat()
    job_id = jobs.create({"idea": idea, "family": family, "mode": mode})
    runner = Runner(jobs, REPO)
    runner.start()
    try:
        deadline = time.monotonic() + 610
        while time.monotonic() < deadline:
            job = jobs.get(job_id)
            if job["status"] in TERMINAL:
                break
            time.sleep(0.1)
        else:
            raise TimeoutError(f"Verification job exceeded its deadline: {label}")
    finally:
        runner.close()
    destination = ROOT / label
    destination.mkdir()
    (destination / "job.json").write_text(json.dumps(job, sort_keys=True, indent=2) + "\n")
    record = {
        "label": label, "job_id": job_id, "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(), "status": job["status"],
        "detail": job["detail"], "browser_verified": False,
    }
    if job["result"] is not None:
        run = WORKSPACE / "runs" / job_id
        review = job["result"]
        assert not review["final_holdout_evaluated"]
        assert review["data_kind"] == ("synthetic" if mode == "synthetic" else "real")
        for artifact in review["artifacts"]:
            path = run / "workflow" / artifact["path"]
            assert file_hash(path) == artifact["sha256"], path
            assert path.stat().st_size == artifact["bytes"], path
        shutil.copy2(run / "review.json", destination / "review.json")
        (destination / "report.txt").write_text(review["report"])
        if (run / "public").is_dir():
            shutil.copytree(run / "public", destination / "public")
        record.update({
            "data_kind": review["data_kind"], "reasoning": review["reasoning"],
            "probability_count": review["probability_count"],
            "artifact_hashes_verified": len(review["artifacts"]),
            "candidate_statuses": [c["status"] for c in review["candidates"]],
            "final_holdout_evaluated": review["final_holdout_evaluated"],
        })
        if mode != "synthetic":
            assert not review["probabilities"]
            assert all(c["forecast_metrics"] is None and not c["scenarios"] for c in review["candidates"])
    RECEIPT["runs"].append(record)
    save()
    print(f"{label}: {job['status']}", flush=True)
RECEIPT["finished_at"] = datetime.now(UTC).isoformat()
save()
