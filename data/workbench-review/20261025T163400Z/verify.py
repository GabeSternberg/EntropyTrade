"""Retained driver for this verification attempt; no browser success is inferred here.

Run with .venv/bin/python from the checkout and the installed server already listening.
Uses actual HTTP submissions, isolated workers and public GETs. Run the unchanged
required suite separately. It never stages, commits, merges, pushes or accesses credentials.
"""

import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from entropytrade.api.jobs import TERMINAL
from entropytrade.data.sources import file_hash

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
WORKSPACE = REPO / "data/cache" / ("workbench-browser-review-" + ROOT.name)
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


check("javascript-syntax", ["node", "--check", "frontend/src/app.js"])
check("frontend-check", ["node", "--test", "frontend/tests/acquisition.test.cjs"])
check("diff-check", ["git", "diff", "--check"])

client = httpx.Client(base_url="http://127.0.0.1:43128", trust_env=False, timeout=10)
catalog = client.get("/api/catalog")
catalog.raise_for_status()
assert not catalog.json()["submission_enabled"]
assert not catalog.json()["provider_enabled"]
headers = {"X-EntropyTrade-CSRF": catalog.json()["csrf_token"]}
for label, family, mode, idea in (
    ("recorded-weather", "weather", "recorded", "Test revision_f >= 1.25 and hours_to_close < 8"),
    ("synthetic-weather", "weather", "synthetic", "Verify protected synthetic model replay"),
    ("public-weather", "weather", "public", "Research forecast_high_f > 70"),
    ("public-bitcoin", "bitcoin", "public", "Research spot_minus_floor_usd > 1000"),
):
    started = datetime.now(UTC).isoformat()
    response = client.post("/api/jobs", json={"idea": idea, "family": family, "mode": mode}, headers=headers)
    response.raise_for_status()
    job_id = response.json()["id"]
    deadline = time.monotonic() + 610
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job["status"] in TERMINAL:
            break
        time.sleep(0.2)
    else:
        raise TimeoutError(f"Verification job exceeded its deadline: {label}")
    destination = ROOT / label
    destination.mkdir()
    (destination / "job.json").write_text(json.dumps(job, sort_keys=True, indent=2) + "\n")
    record = {
        "label": label, "job_id": job_id, "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(), "status": job["status"],
        "detail": job["detail"], "browser_verified": False,
        "submission": "actual loopback HTTP; not a browser interaction",
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
        exported_review = client.get(f"/api/jobs/{job_id}/review")
        exported_report = client.get(f"/api/jobs/{job_id}/report")
        exported_review.raise_for_status()
        exported_report.raise_for_status()
        assert exported_review.json() == review
        assert exported_report.content == review["report"].encode()
        (destination / "http-review.json").write_bytes(exported_review.content)
        (destination / "http-report.txt").write_bytes(exported_report.content)
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
