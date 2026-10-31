"""Real listener and ordinary worker over explicitly CONTROLLED sufficient-data receipts."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tests.integration.cohort_fixture import seed_cohort
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO, await_job


def test_cohort_api_validation_and_existing_research_experiment_pipeline() -> None:
    with TemporaryDirectory(prefix="cohort-listener-", dir=REPO / "data/cache") as name:
        root = Path(name) / "workspace"
        seed_cohort(root)
        with listening(root) as (server, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            ids = [
                p["partition_id"]
                for p in client.get("/api/weather/partitions").json()["partitions"]
            ]
            invalids: tuple[dict[str, Any], ...] = (
                {"partition_ids": []},
                {"partition_ids": ids * 2},
                {"partition_ids": ids, "partition_id": ids[0]},
                {"partition_ids": ids, "outcome_partition_ids": []},
                {"partition_ids": ["a" * 64]},
                {"partition_ids": ids, "path": str(root)},
                {"outcome_partition_ids": ids},
                {"partition_ids": ids, "outcome_partition_ids": None},
            )
            for invalid in invalids:
                assert (
                    client.post("/api/weather/datasets", json=invalid, headers=headers).status_code
                    == 400
                )
            response = client.post(
                "/api/weather/datasets", json={"partition_ids": ids}, headers=headers
            )
            assert response.status_code == 201, response.text
            selected = response.json()
            assert len(selected["readiness"]["cohort"]["batches"]) == 2
            assert selected["readiness"]["status"] == "ready_for_model_gates"
            created = client.post(
                "/api/jobs",
                headers=headers,
                json={
                    "idea": "Test forecast_high_f > 60",
                    "family": "weather",
                    "mode": "weather_history",
                    "dataset_id": selected["dataset_id"].removeprefix("sha256:"),
                },
            )
            assert created.status_code == 202, created.text
            job = await_job(server.jobs, created.json()["id"])
            assert job["status"] == "completed", job
            review = job["result"]
            assert review["probability_count"] > 0
            assert all(
                c["status"] == "INSUFFICIENT_DATA" and not c["scenarios"] and not c["tested"]
                for c in review["candidates"]
            )
            assert any(
                c["forecast_metrics"] and c["forecast_metrics"]["status"] == "evaluated"
                for c in review["candidates"]
            )
            assert any(
                "sized books" in reason for c in review["candidates"] for reason in c["reasons"]
            )
            assert all(p["split"] == "validation" for p in review["probabilities"])
            assert not review["final_holdout_evaluated"]
