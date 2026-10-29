"""Populated history through real localhost/worker. Controlled software evidence only."""

import json
import os
import shutil
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.families.bitcoin_history import history_data
from tests.integration.bitcoin_history_fixture import (
    DATES,
    LABEL,
    PARTITION,
    RECEIVED,
    add_capture,
    seed_workspace,
)
from tests.integration.test_workbench_listener import listening


@pytest.fixture(name="workspace")
def history_workspace() -> Iterator[Path]:
    cache = Path(__file__).resolve().parents[3] / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="bitcoin-history-listener-", dir=cache) as name:
        yield Path(name)


def completed_history(client: httpx.Client) -> tuple[str, dict[str, Any], bytes, bytes]:
    catalog = client.get("/api/catalog").json()
    assert not catalog["submission_enabled"]
    assert not catalog["provider_enabled"]
    response = client.post(
        "/api/jobs",
        json={"idea": "Test scaled_moneyness > 0", "family": "bitcoin", "mode": "history"},
        headers={"X-EntropyTrade-CSRF": catalog["csrf_token"]},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    deadline = monotonic() + 60
    while True:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            break
        assert monotonic() < deadline, job
        sleep(0.05)
    assert job["status"] == "completed", job
    assert {e["stage"] for e in job["events"]} >= {
        "queued",
        "starting",
        "reconciling",
        "research",
        "experiments",
        "completed",
    }
    review = client.get(f"/api/jobs/{job_id}/review")
    report = client.get(f"/api/jobs/{job_id}/report")
    assert review.status_code == report.status_code == 200
    assert review.json() == job["result"]
    assert report.text == job["result"]["report"]
    # The page's download attribute supplies filenames; the API supplies typed bytes.
    assert review.headers["content-type"] == "application/json"
    assert report.headers["content-type"] == "text/plain; charset=utf-8"
    return job_id, job, review.content, report.content


def verify_review(workspace: Path, job_id: str, job: dict[str, Any], captures: int) -> None:
    review = job["result"]
    history = review["bitcoin_history"]
    assert history["partition"] == PARTITION
    assert history["capture_count"] == captures
    assert history["retained_events"] == history["retained_dates"] == 3
    assert history["protected_events"] == 1
    reconciliation = history["reconciliation"]
    assert reconciliation["fetch_enabled"]
    assert reconciliation["requested"] == reconciliation["deferred"] == 0
    assert reconciliation["failures"] == []
    assert reconciliation["retained_receipts"] == len(reconciliation["receipts"]) == 3
    assert {r["received_at"] for r in reconciliation["receipts"]} == {RECEIVED.isoformat()}
    assert not review["final_holdout_evaluated"]
    assert review["probability_count"] == 0
    assert review["probabilities"] == []
    assert len(review["candidates"]) == 2
    assert all(
        c["status"] == "INSUFFICIENT_DATA"
        and not c["tested"]
        and c["forecast_metrics"] is None
        and c["scenarios"] == []
        for c in review["candidates"]
    )
    assert "received before fit cutoff" in json.dumps(review["candidates"])
    run = workspace / "runs" / job_id
    assert json.loads((run / "review.json").read_text()) == review
    data = history_data(run / "history")
    assert len(data.samples) == 3
    assert len(data.protected_events) == 1
    assert {s.decision_time for s in data.samples} == set(DATES)
    assert all(
        s.outcome_available_at == RECEIVED and not s.rules_known and s.book is None
        for s in data.samples
    )
    for artifact in review["artifacts"]:
        path = run / "workflow" / artifact["path"]
        assert file_hash(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["bytes"]
    assert "trading backtests and returns remain blocked" in review["report"]


def test_populated_history_discovery_worker_downloads_and_restart(workspace: Path) -> None:
    seed = seed_workspace(workspace)
    with listening(workspace) as (_, client):
        first_id, first, first_json, first_report = completed_history(client)
        verify_review(workspace, first_id, first, 3)
    # New polling evidence must not move the original event decision or frozen split.
    add_capture(Jobs(workspace), DATES[0] + timedelta(minutes=30))
    with listening(workspace) as (_, client):
        assert client.get(f"/api/jobs/{first_id}").json() == first
        assert client.get(f"/api/jobs/{first_id}/review").content == first_json
        assert client.get(f"/api/jobs/{first_id}/report").content == first_report
        second_id, second, second_json, second_report = completed_history(client)
        verify_review(workspace, second_id, second, 4)
    with listening(workspace) as (_, client):
        rows = {row["id"]: row for row in client.get("/api/jobs").json()}
        for job_id, job, review, report in (
            (first_id, first, first_json, first_report),
            (second_id, second, second_json, second_report),
        ):
            assert rows[job_id]["status"] == "completed"
            assert client.get(f"/api/jobs/{job_id}").json() == job
            assert client.get(f"/api/jobs/{job_id}/review").content == review
            assert client.get(f"/api/jobs/{job_id}/report").content == report
    # Optional durable bundle for an acceptance run. Ordinary pytest leaves no evidence copy.
    if destination := os.environ.get("ENTROPYTRADE_HISTORY_EVIDENCE"):
        root = Path(destination).resolve()
        repo = Path(__file__).resolve().parents[3]
        assert root.is_relative_to(repo / "data/bitcoin-history-review")
        root.mkdir(parents=True, exist_ok=False)
        shutil.copytree(workspace, root / "workspace")
        for prefix, review, report in (
            ("first", first_json, first_report),
            ("second", second_json, second_report),
        ):
            (root / f"{prefix}-review.json").write_bytes(review)
            (root / f"{prefix}-report.txt").write_bytes(report)
        (root / "receipt.json").write_text(
            json.dumps(
                {
                    "evidence": LABEL,
                    "status": "passed",
                    "seed": seed,
                    "jobs": [first_id, second_id],
                    "listener": "actual ephemeral loopback HTTP",
                    "worker": "unmodified Runner subprocess",
                    "restarts": 2,
                    "browser_interaction": False,
                    "empirical_performance": False,
                },
                indent=2,
            )
            + "\n"
        )
