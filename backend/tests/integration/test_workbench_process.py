"""Real isolated workers, including model replay and process termination; no wire fixtures."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from entropytrade.api.jobs import TERMINAL, Jobs
from entropytrade.api.runner import Runner
from entropytrade.data.sources import file_hash

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def workspace() -> Iterator[Path]:
    cache = REPO / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="workbench-integration-", dir=cache) as name:
        yield Path(name)


def await_job(jobs: Jobs, job_id: str, *, stage: str | None = None) -> dict[str, Any]:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        assert job is not None
        if job["status"] in TERMINAL or (
            stage is not None and any(e["stage"] == stage for e in job["events"])
        ):
            return job
        time.sleep(0.05)
    pytest.fail(f"Worker did not reach {stage or 'a terminal status'}: {jobs.get(job_id)}")


@pytest.mark.parametrize("mode", ["recorded", "synthetic"])
def test_real_subprocess_saves_checksums_and_protected_review(workspace: Path, mode: str) -> None:
    jobs = Jobs(workspace)
    job_id = jobs.create({"idea": "Test revision_f > 1", "family": "weather", "mode": mode})
    runner = Runner(jobs, REPO)
    runner.start()
    try:
        job = await_job(jobs, job_id)
    finally:
        runner.close()
    assert not runner.thread.is_alive()
    assert job["status"] == "completed", job["detail"]
    review = job["result"]
    run = workspace / "runs" / job_id
    assert json.loads((run / "review.json").read_text()) == review
    assert not review["final_holdout_evaluated"]
    assert {e["stage"] for e in job["events"]} >= {"queued", "starting", "completed"}
    assert review["artifacts"]
    for artifact in review["artifacts"]:
        path = run / "workflow" / artifact["path"]
        assert path.is_file()
        assert file_hash(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["bytes"]
    if mode == "recorded":
        assert review["data_kind"] == "real"
        assert review["coverage"]["scalar_label_events"] == 0
        assert not review["probabilities"]
        assert all(
            not c["tested"] and c["forecast_metrics"] is None and not c["scenarios"]
            for c in review["candidates"]
        )
    else:
        assert review["data_kind"] == "synthetic"
        assert review["reasoning"] == "offline_mock"
        assert review["probabilities"]
        used = {p for c in review["candidates"] for p in c.get("prediction_ids", [])}
        assert all(
            p["split"] == "validation" and p["prediction_id"] in used
            for p in review["probabilities"]
        )
        control = next(c for c in review["candidates"] if c["candidate_id"] == "negative-control")
        assert len(control["scenarios"]) == 3
        assert all(s["fill_count"] == 0 for s in control["scenarios"])


@pytest.mark.parametrize("action", ["cancel", "shutdown", "timeout"])
def test_real_worker_termination_and_restart_cannot_publish_a_late_result(
    workspace: Path, action: str
) -> None:
    jobs = Jobs(workspace)
    job_id = jobs.create(
        {"idea": "Cancellation integration", "family": "weather", "mode": "synthetic"}
    )
    # A zero budget still starts a real child, then exercises the production kill/wait path.
    runner = Runner(jobs, REPO, timeout=0 if action == "timeout" else 600)
    runner.start()
    try:
        if action == "timeout":
            job = await_job(jobs, job_id)
            assert job["status"] == "failed"
            assert "wall-time budget" in job["detail"]
        else:
            # Creating the run directory proves the actual worker entered execute_job.
            deadline = time.monotonic() + 30
            while not (workspace / "runs" / job_id).is_dir():
                assert time.monotonic() < deadline, jobs.get(job_id)
                assert jobs.get(job_id)["status"] not in TERMINAL  # type: ignore[index]
                time.sleep(0.02)
            if action == "cancel":
                assert jobs.update(
                    job_id, "cancelled", "Integration cancellation", status="cancelled"
                )
                # Completion of a following job proves cancellation reaped the active child
                # and released the sole worker slot, independently of server shutdown.
                following = jobs.create(
                    {"idea": "After cancellation", "family": "weather", "mode": "recorded"}
                )
                assert await_job(jobs, following)["status"] == "completed"
            runner.close()
            job = await_job(jobs, job_id)
            assert job["status"] == ("cancelled" if action == "cancel" else "interrupted")
    finally:
        runner.close()
    assert not runner.thread.is_alive()
    assert job["result"] is None
    assert not (workspace / "runs" / job_id / "review.json").exists()
    assert not jobs.update(job_id, "late", "Must remain terminal", status="completed", result={})
    queued = jobs.create({"idea": "Pending at restart", "family": "weather", "mode": "recorded"})
    reopened = Jobs(workspace)
    reopened.recover()
    assert reopened.get(job_id)["status"] == job["status"]  # type: ignore[index]
    assert reopened.get(queued)["status"] == "interrupted"  # type: ignore[index]
    assert len(reopened.history()) == (3 if action == "cancel" else 2)
