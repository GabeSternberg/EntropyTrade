"""Real listener, controlled source replay, CSRF and portable offline label evidence."""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.api.recovery import restore, snapshot
from entropytrade.api.workspace import workspace_path
from entropytrade.weather.label_service import LabelService
from tests.integration.test_workbench_listener import listening
from tests.integration.weather_history_retained import REPO, seed_retained
from tests.unit.test_weather_labels import receipt


def test_label_acquisition_status_refusals_dataset_restart_and_offline_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = LabelService.acquire
    calls: list[str] = []

    async def controlled(
        self: LabelService,
        request: dict[str, Any],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        def source(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            return httpx.Response(
                200,
                content=receipt(req.url.params["date"]).body(),
                headers={"content-type": "application/json"},
            )

        await original(self, request, httpx.MockTransport(source))

    monkeypatch.setattr(LabelService, "acquire", controlled)
    with TemporaryDirectory(prefix="weather-labels-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        root = parent / "workspace"
        seed_retained(root)
        with listening(root, workers=False) as (_, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            old = client.post("/api/weather/datasets", headers=headers, json={}).json()
            request = {"id": str(uuid4()), "dataset_id": old["dataset_id"][7:]}
            assert client.post("/api/weather/labels", json=request).status_code == 403
            assert (
                client.post(
                    "/api/weather/labels",
                    headers=headers,
                    json={**request, "url": "https://invalid.example"},
                ).status_code
                == 400
            )
            assert (
                client.post("/api/weather/labels", headers=headers, json=request).status_code == 202
            )
            for _ in range(300):
                acquisition = client.get("/api/weather/labels").json()[0]
                if acquisition["status"] == "completed":
                    break
                time.sleep(0.02)
            assert acquisition["status"] == "completed", acquisition
            assert acquisition["result"]["verified_events"] == 2
            assert acquisition["result"]["refused_events"] == 2
            assert (
                client.post("/api/weather/labels", headers=headers, json=request).json()
                == acquisition
            )
            assert len(calls) == 2
            version = acquisition["batch_version"][7:]
            evidence = client.get("/api/weather/labels/" + version).content
            updated = client.post("/api/weather/datasets", headers=headers, json={}).json()
            assert updated["readiness"]["scalar_label_events"] == 2
            assert updated["readiness"]["label_acquisition"][0]["receipts"]
            assert client.get("/api/weather/labels/../jobs.sqlite").status_code != 200
        with listening(root, workers=False) as (_, client):
            assert client.get("/api/weather/labels").json() == [acquisition]
            assert client.get("/api/weather/labels/" + version).content == evidence
            assert len(calls) == 2
        archive = parent / "snapshot.zip"
        snapshot(REPO, root, archive)
        restored = workspace_path(REPO, parent / "restored")
        restore(REPO, archive, restored)
        with listening(restored, workers=False) as (_, client):
            assert client.get("/api/weather/labels/" + version).content == evidence
            assert client.get("/api/weather/labels").json() == [acquisition]
            datasets = client.get("/api/weather/datasets").json()
            assert updated in datasets
            assert old in datasets
            assert len(calls) == 2
            assert json.loads(evidence)["source_dataset"] == old["dataset_id"]
