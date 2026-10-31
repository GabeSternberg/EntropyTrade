"""Actual localhost/worker acceptance; CONTROLLED sources, not browser or empirical evidence."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from entropytrade.api.recovery import restore, snapshot
from tests.integration.shadow_history_fixture import seed_sustained
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO, await_job


def test_sustained_partition_research_downloads_and_offline_listener_restore() -> None:
    with TemporaryDirectory(prefix="shadow-history-http-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        root = parent / "workspace"
        seed_sustained(root)
        with listening(root) as (server, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            catalog = client.get("/api/weather/partitions").json()
            assert catalog["total_inputs"] == 130
            ids = [p["partition_id"] for p in catalog["partitions"]]
            assert client.post("/api/weather/datasets", json={}, headers=headers).status_code == 400
            assert (
                client.post("/api/weather/datasets", json={"partition_id": ids[0]}).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/weather/datasets", json={"partition_id": "../x"}, headers=headers
                ).status_code
                == 400
            )
            selected = {"partition_id": ids[0], "outcome_partition_id": ids[1]}
            frozen = client.post("/api/weather/datasets", json=selected, headers=headers)
            assert frozen.status_code == 201, frozen.text
            dataset = frozen.json()
            assert dataset["readiness"]["shadow_audit"]["labelled_samples"] == 128
            assert dataset["readiness"]["shadow_audit"]["sized_books"] == 128
            assert dataset["readiness"]["scalar_label_events"] == 0
            created = client.post(
                "/api/jobs",
                headers=headers,
                json={
                    "idea": "Test forecast_high_f > 60",
                    "family": "weather",
                    "mode": "weather_history",
                    "dataset_id": dataset["dataset_id"].removeprefix("sha256:"),
                },
            )
            assert created.status_code == 202, created.text
            job_id = created.json()["id"]
            job = await_job(server.jobs, job_id)
            assert job["status"] == "completed", job
            result = job["result"]
            assert not result["final_holdout_evaluated"]
            assert result["probability_count"] == 0
            assert all(not c["tested"] and not c["scenarios"] for c in result["candidates"])
            saved = {
                route: client.get(f"/api/jobs/{job_id}/{route}").content
                for route in ("review", "report", "shadow-inputs")
            }
            projection = json.loads(saved["shadow-inputs"])
            assert len(projection["cycles"]) == 128
            assert all(c["original_replay_verified"] for c in projection["cycles"])
            assert all(
                d["intent"] is None for c in projection["cycles"] for d in c["saved_decisions"]
            )
            download = root / "runs" / job_id / "workflow/shadow-replay.json"
            download.write_bytes(b"tampered")
            assert client.get(f"/api/jobs/{job_id}/shadow-inputs").status_code == 409
            download.write_bytes(saved["shadow-inputs"])
        archive = parent / "offline.zip"
        snapshot(REPO, root, archive)
        restored = parent / "restored"
        restore(REPO, archive, restored)
        with listening(restored, workers=False) as (_, client):
            assert client.get("/api/weather/partitions").json() == catalog
            assert client.get("/api/weather/datasets").json() == [dataset]
            for route, expected in saved.items():
                assert client.get(f"/api/jobs/{job_id}/{route}").content == expected
