"""One actual credential-free research/shadow subprocess probe; no browser acceptance claim."""

import json
import shutil
from pathlib import Path

from entropytrade.api.jobs import Jobs
from entropytrade.api.worker import execute_job
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore

repo = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent / "actual-probe"
workspace = repo / "data/cache/shadow-actual-probe-20261029"
if workspace.exists() or evidence.exists():
    raise RuntimeError("Use new evidence/workspace paths; existing receipts are immutable")
jobs = Jobs(workspace)
job_id = jobs.create({"idea": "Test forecast_high_f > 70", "family": "weather", "mode": "recorded"})
jobs.update(job_id, "starting", "Actual credential-free recorded research probe")
execute_job(jobs, repo, job_id)
job = jobs.get(job_id)
if not job or job["status"] != "completed":
    raise RuntimeError("Recorded research did not complete")
proposal = next(p for p in job["result"]["proposals"] if p.get("spec"))
store = TrackingStore(jobs)
monitor_id = store.create({"job_id": job_id, "candidate_id": proposal["candidate_id"], "interval_seconds": 60})
claim = store.claim()
if claim is None:
    raise RuntimeError("Monitor could not claim first cycle")
# Actual isolated worker and its normal deadline/environment; no transport/clock overrides.
ShadowRunner(store, repo).execute(*claim)
store.control(monitor_id, "pause")
snapshot = store.get(monitor_id, export=True)
evidence.mkdir()
(evidence / "monitor.json").write_text(json.dumps(snapshot, sort_keys=True, indent=2))
shutil.copytree(workspace, evidence / "workspace")
print(json.dumps({"monitor_id": monitor_id, "status": snapshot["status"],
                  "cycle_status": snapshot["cycles"][0]["status"],
                  "cycle_detail": snapshot["cycles"][0]["detail"],
                  "submission_enabled": False}))
