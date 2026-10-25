"""Actual denied-network failure evidence under the ordinary sandbox, not browser QA."""
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from entropytrade.api.jobs import Jobs, TERMINAL
from entropytrade.api.runner import Runner
from entropytrade.data.sources import file_hash

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
WORKSPACE = REPO / "data/cache" / ("workbench-failure-" + ROOT.name)
started = datetime.now(UTC).isoformat()
jobs = Jobs(WORKSPACE)
job_id = jobs.create({"idea": "Research Bitcoin spot; actual network failure presentation check", "family": "bitcoin", "mode": "public"})
runner = Runner(jobs, REPO)
runner.start()
try:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        if job["status"] in TERMINAL:
            break
        time.sleep(0.1)
    else:
        raise TimeoutError(job_id)
finally:
    runner.close()
assert job["status"] == "completed", job
review = job["result"]
summary = review["acquisition"]
assert summary["status"] == "incomplete", summary
assert summary["failure_count"] > 0
assert summary["headline"] in review["report"]
assert all(message in review["report"] for message in summary["failure_summaries"])
assert not review["probabilities"] and not review["final_holdout_evaluated"]
assert all(c["forecast_metrics"] is None and not c["scenarios"] for c in review["candidates"])
source = WORKSPACE / "runs" / job_id
destination = ROOT / "blocked-network-bitcoin"
destination.mkdir()
for name in ("review.json",):
    shutil.copy2(source / name, destination / name)
shutil.copytree(source / "public", destination / "public")
(destination / "job.json").write_text(json.dumps(job, indent=2) + "\n")
(destination / "report.txt").write_text(review["report"])
for artifact in review["artifacts"]:
    path = source / "workflow" / artifact["path"]
    assert file_hash(path) == artifact["sha256"]
    assert path.stat().st_size == artifact["bytes"]
receipt_path = ROOT / "receipt.json"
receipt = json.loads(receipt_path.read_text())
receipt["runs"].append({
    "label": destination.name, "job_id": job_id, "started_at": started,
    "finished_at": datetime.now(UTC).isoformat(), "status": job["status"],
    "detail": job["detail"], "browser_verified": False,
    "submission": "isolated worker under ordinary network-restricted sandbox; not a browser or HTTP submission",
    "workspace": str(WORKSPACE.relative_to(REPO)),
    "data_kind": review["data_kind"], "reasoning": review["reasoning"],
    "probability_count": review["probability_count"],
    "artifact_hashes_verified": len(review["artifacts"]),
    "candidate_statuses": [c["status"] for c in review["candidates"]],
    "final_holdout_evaluated": review["final_holdout_evaluated"],
})
receipt["finished_at"] = datetime.now(UTC).isoformat()
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(summary["counts"])
