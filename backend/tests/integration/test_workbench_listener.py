"""Actual loopback HTTP plus isolated workers. Listener denial must fail, never skip."""

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest

from entropytrade.api.server import WorkbenchServer
from tests.integration.test_workbench_process import REPO, await_job


@pytest.fixture
def workspace() -> Iterator[Path]:
    cache = REPO / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="workbench-listener-", dir=cache) as name:
        yield Path(name)


@contextmanager
def listening(
    workspace: Path, *, workers: bool = True, shadow_workers: bool = False
) -> Iterator[tuple[WorkbenchServer, httpx.Client]]:
    with WorkbenchServer(REPO, workspace, port=0) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        thread.start()
        if workers:
            server.runner.start()
        if shadow_workers:
            server.shadow.start()
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False, timeout=10
            ) as client:
                yield server, client
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert not thread.is_alive()
    assert not server.runner.thread.is_alive()
    assert not server.shadow.thread.is_alive()


@pytest.mark.parametrize("mode", ["recorded", "synthetic"])
def test_listener_to_real_worker_review_and_downloads_survive_restart(
    workspace: Path, mode: str
) -> None:
    with listening(workspace) as (server, client):
        catalog = client.get("/api/catalog").json()
        assert not catalog["submission_enabled"]
        assert not catalog["provider_enabled"]
        assert client.post("/api/jobs", json={}).status_code == 403
        assert client.get("/api/catalog", headers={"Host": "attacker.invalid"}).status_code == 403
        for path in (
            "/",
            "/app.js",
            "/style.css",
            "/ui.js",
            "/demo-data.js",
            "/shell.js",
            "/views-research.js",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert response.content
            assert response.headers["x-content-type-options"] == "nosniff"
        response = client.post(
            "/api/jobs",
            json={"idea": "Test forecast revision", "family": "weather", "mode": mode},
            headers={"X-EntropyTrade-CSRF": catalog["csrf_token"]},
        )
        assert response.status_code == 202
        job_id = response.json()["id"]
        job = await_job(server.jobs, job_id)
        assert job["status"] == "completed", job["detail"]
        assert client.get(f"/api/jobs/{job_id}").json() == job
        review = client.get(f"/api/jobs/{job_id}/review")
        report = client.get(f"/api/jobs/{job_id}/report")
        assert review.status_code == report.status_code == 200
        assert review.json() == job["result"]
        assert report.text == job["result"]["report"]
        assert not review.json()["final_holdout_evaluated"]
        assert review.json()["data_kind"] == ("synthetic" if mode == "synthetic" else "real")
        assert (
            json.loads((workspace / "runs" / job_id / "review.json").read_text()) == review.json()
        )
    with listening(workspace) as (_, client):
        assert client.get("/api/jobs").json()[0]["id"] == job_id
        assert client.get(f"/api/jobs/{job_id}/review").json() == review.json()
        assert client.get(f"/api/jobs/{job_id}/report").content == report.content


def test_listener_cancellation_lock_and_restart_history(workspace: Path) -> None:
    with listening(workspace, workers=False) as (server, client):
        with pytest.raises(BlockingIOError):
            WorkbenchServer(REPO, workspace, port=0)
        headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
        request = {"idea": "Cancel pending research", "family": "weather", "mode": "recorded"}
        cancelled = client.post("/api/jobs", json=request, headers=headers).json()["id"]
        pending = client.post("/api/jobs", json=request, headers=headers).json()["id"]
        response = client.post(f"/api/jobs/{cancelled}/cancel", json={}, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"cancelled": True}
        assert not server.jobs.update(cancelled, "late", "Late result", status="completed")
        assert client.get(f"/api/jobs/{cancelled}").json()["status"] == "cancelled"
    with listening(workspace, workers=False) as (_, client):
        rows = {row["id"]: row for row in client.get("/api/jobs").json()}
        assert rows[cancelled]["status"] == "cancelled"
        assert rows[pending]["status"] == "interrupted"
        assert client.get(f"/api/jobs/{pending}/review").json() is None
        # Restart rotates the server token; an earlier page cannot submit stale writes.
        assert client.post("/api/jobs", json=request, headers=headers).status_code == 403
