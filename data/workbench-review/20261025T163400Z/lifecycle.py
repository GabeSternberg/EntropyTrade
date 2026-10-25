"""Actual local HTTP lifecycle evidence; deliberately not browser acceptance."""
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
client = httpx.Client(base_url="http://127.0.0.1:43128", trust_env=False, timeout=10)
headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
receipt_path = ROOT / "http-lifecycle.json"


def now():
    return datetime.now(UTC).isoformat()


def get(job_id):
    response = client.get(f"/api/jobs/{job_id}")
    response.raise_for_status()
    return response.json()


def submit(idea, mode):
    response = client.post("/api/jobs", headers=headers, json={"idea": idea, "family": "weather", "mode": mode})
    response.raise_for_status()
    return response.json()["id"]


def wait(job_id, predicate):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = get(job_id)
        if predicate(job):
            return job
        time.sleep(0.05)
    raise TimeoutError(job_id)


def exports():
    result = []
    for run in json.loads((ROOT / "receipt.json").read_text())["runs"]:
        row = {"job_id": run["job_id"], "label": run["label"], "browser_download": False}
        for suffix in ("review", "report"):
            response = client.get(f"/api/jobs/{run['job_id']}/{suffix}")
            response.raise_for_status()
            extension = "json" if suffix == "review" else "txt"
            saved = ROOT / run["label"] / f"http-{suffix}.{extension}"
            assert response.content == saved.read_bytes()
            row[suffix + "_sha256"] = hashlib.sha256(response.content).hexdigest()
        result.append(row)
    return result


if sys.argv[1] == "before":
    receipt = {"started_at": now(), "browser_verified": False, "before_restart_exports": exports()}
    cancelled = submit("HTTP acceptance: cancel active synthetic fitting", "synthetic")
    active = wait(cancelled, lambda j: j["events"][-1]["stage"] == "modeling")
    response = client.post(f"/api/jobs/{cancelled}/cancel", json={}, headers=headers)
    response.raise_for_status()
    assert response.json() == {"cancelled": True}
    receipt["cancelled_while_active"] = {"observed_at": now(), "before": active, "after": get(cancelled)}
    replacement = submit("HTTP acceptance: recorded run after active cancellation", "recorded")
    completed = wait(replacement, lambda j: j["status"] in {"completed", "failed"})
    assert completed["status"] == "completed", completed
    assert get(cancelled)["status"] == "cancelled"
    receipt["slot_reuse"] = {"job_id": replacement, "status": completed["status"], "observed_at": now()}
    interrupted = submit("HTTP acceptance: interrupt active synthetic fitting", "synthetic")
    active = wait(interrupted, lambda j: j["events"][-1]["stage"] == "modeling")
    pending = submit("HTTP acceptance: pending request during shutdown", "recorded")
    assert get(pending)["status"] == "queued"
    receipt["restart_active_id"] = interrupted
    receipt["restart_pending_id"] = pending
    receipt["before_shutdown"] = {"observed_at": now(), "active": active, "pending": get(pending)}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print("Active and pending jobs ready for server shutdown", flush=True)
elif sys.argv[1] == "after":
    receipt = json.loads(receipt_path.read_text())
    receipt["after_restart"] = {}
    for key in ("restart_active_id", "restart_pending_id"):
        job = get(receipt[key])
        assert job["status"] == "interrupted", job
        receipt["after_restart"][key] = job
    receipt["after_restart_exports"] = exports()
    assert receipt["before_restart_exports"] == receipt["after_restart_exports"]
    receipt["finished_at"] = now()
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print("Cancellation, slot reuse, interruption and unchanged HTTP exports verified", flush=True)
else:
    raise ValueError("expected before or after")
