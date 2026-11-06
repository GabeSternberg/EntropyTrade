"""Authentic retained receipts through actual localhost, ordinary workers and restore."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.api.workspace import workspace_path
from entropytrade.operations.forward import footprint
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO, await_job
from tests.integration.weather_history_retained import seed_retained


def test_retained_weather_selection_downloads_cancellation_restart_and_restore() -> None:
    with TemporaryDirectory(prefix="weather-history-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        root = parent / "workspace"
        seed_retained(root)
        with listening(root) as (server, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            assert client.get("/api/weather/datasets").json() == []
            assert client.post("/api/weather/datasets", json={}).status_code == 403
            frozen = client.post("/api/weather/datasets", json={}, headers=headers)
            assert frozen.status_code == 201, frozen.text
            dataset = frozen.json()
            assert dataset["readiness"]["scalar_label_events"] == 0
            assert client.post("/api/weather/datasets", json={}, headers=headers).json() == dataset
            request = {
                "idea": "Test forecast_high_f > 60",
                "family": "weather",
                "mode": "weather_history",
                "dataset_id": dataset["dataset_id"].removeprefix("sha256:"),
            }
            created = client.post("/api/jobs", json=request, headers=headers)
            assert created.status_code == 202, created.text
            job_id = created.json()["id"]
            job = await_job(server.jobs, job_id)
            assert job["status"] == "completed", job
            result = job["result"]
            assert result["weather_history"]["dataset_id"] == dataset["dataset_id"]
            assert result["coverage"]["independent_events"] == 4
            assert result["probabilities"] == []
            assert result["candidates"]
            assert all(
                c["status"] == "INSUFFICIENT_DATA" and not c["tested"] and not c["scenarios"]
                for c in result["candidates"]
            )
            assert not result["final_holdout_evaluated"]
            review = client.get(f"/api/jobs/{job_id}/review").content
            report = client.get(f"/api/jobs/{job_id}/report").content
        # Pending and cancelled runs retain the same frozen snapshot reference.
        jobs = Jobs(root)
        pending = jobs.create(request)
        cancelled = jobs.create(request)
        jobs.update(cancelled, "cancelled", "Cancelled by user", status="cancelled")
        with listening(root, workers=False) as (_, client):
            assert client.get(f"/api/jobs/{pending}").json()["status"] == "interrupted"
            assert client.get(f"/api/jobs/{cancelled}").json()["status"] == "cancelled"
            assert client.get(f"/api/jobs/{job_id}/review").content == review
            assert client.get(f"/api/jobs/{job_id}/report").content == report
            assert client.get("/api/weather/datasets").json() == [dataset]
        archive = parent / "snapshot.zip"
        snapshot(REPO, root, archive)
        # The frozen dataset copies authentic shadow receipts byte for byte; the archive
        # stores each distinct content once and the restore still expands every path.
        size = footprint(root)
        with ZipFile(archive) as bundle:
            files = json.loads(bundle.read("manifest.json"))["files"]
            members = len(bundle.namelist()) - 1
        dataset_bytes = size["areas"]["runs/weather-datasets"]
        assert members == len({f["sha256"] for f in files}) < len(files)
        assert size["distinct_bytes"] <= size["bytes"] - dataset_bytes // 2
        restored = workspace_path(REPO, parent / "restored")
        restore(REPO, archive, restored)
        assert footprint(restored)["areas"] == size["areas"]
        with listening(restored, workers=False) as (_, client):
            assert client.get("/api/weather/datasets").json() == [dataset]
            assert client.get(f"/api/jobs/{job_id}/review").content == review
            assert client.get(f"/api/jobs/{job_id}/report").content == report
