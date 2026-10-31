"""Real listener/restart/offline restore with clearly CONTROLLED multi-date source data."""

import time
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.api.recovery import restore, snapshot
from entropytrade.domain.time import SimulatedClock
from entropytrade.weather.label_service import LabelService
from tests.integration.forward_validation_fixture import NOW, portal, seed_dates
from tests.integration.test_workbench_listener import listening
from tests.integration.weather_history_retained import REPO


def await_dates(client: httpx.Client, schedule_id: str, status: str) -> dict[str, Any]:
    for _ in range(400):
        value = client.get("/api/weather/schedules/" + schedule_id).json()
        if value.get("counts", {}).get(status) == 12 and value["inflight"] is None:
            return dict(value)
        time.sleep(0.025)
    raise AssertionError(value)


def test_continuous_controlled_listener_transitions_restart_and_offline_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = LabelService.acquire
    phase = ["preliminary"]
    clock = SimulatedClock(NOW)
    calls: list[str] = []

    async def controlled(
        self: LabelService,
        request: dict[str, Any],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        def source(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            return httpx.Response(200, json=portal(req.url.params["date"], phase[0]))

        await original(self, request, httpx.MockTransport(source))

    monkeypatch.setattr(LabelService, "acquire", controlled)
    monkeypatch.setattr("entropytrade.weather.label_schedule.utc_now", clock.now)
    monkeypatch.setattr("entropytrade.weather.label_service.utc_now", clock.now)
    with TemporaryDirectory(prefix="forward-validation-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        root = parent / "workspace"
        initial = seed_dates(root)
        schedule_id = str(uuid4())
        selection = {
            "id": schedule_id,
            "dataset_id": initial["dataset_id"][7:],
            "enabled": True,
            "interval_seconds": 300,
            "batch_dates": 8,
            "follow_retained": True,
        }
        with listening(root, workers=False) as (_, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            assert client.get("/api/weather/schedules").json() == []
            assert client.post("/api/weather/schedules", json=selection).status_code == 403
            assert (
                client.post(
                    "/api/weather/schedules", headers=headers, json={**selection, "enabled": False}
                ).status_code
                == 400
            )
            assert (
                client.post("/api/weather/schedules", headers=headers, json=selection).status_code
                == 202
            )
            preliminary = await_dates(client, schedule_id, "retry")
            assert len(calls) == 12
            assert all(w["attempts"] == 1 for w in preliminary["work"])
            assert (
                client.post(
                    f"/api/weather/schedules/{schedule_id}/pause", json={}, headers=headers
                ).status_code
                == 200
            )
        phase[0] = "official"
        clock.advance(timedelta(seconds=300))
        with listening(root, workers=False) as (_, client):
            headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}
            assert client.get(f"/api/weather/schedules/{schedule_id}").json()["status"] == "paused"
            assert len(calls) == 12
            assert (
                client.post(
                    f"/api/weather/schedules/{schedule_id}/resume", json={}, headers=headers
                ).status_code
                == 200
            )
            official = await_dates(client, schedule_id, "verified")
            assert len(calls) == 24
            assert all(w["attempts"] == 2 for w in official["work"])
            assert (
                client.post(
                    f"/api/weather/schedules/{schedule_id}/pause", json={}, headers=headers
                ).status_code
                == 200
            )
            paused = client.get(f"/api/weather/schedules/{schedule_id}").content
            label_versions = client.get("/api/weather/labels").json()
            evidence = {
                r["batch_version"]: client.get(
                    "/api/weather/labels/" + r["batch_version"][7:]
                ).content
                for r in label_versions
            }
            frozen = client.post("/api/weather/datasets", json={}, headers=headers).json()
            assert frozen["readiness"]["scalar_label_events"] == 12
            assert frozen["readiness"]["status"] == "insufficient_data"
        archive = parent / "snapshot.zip"
        snapshot(REPO, root, archive)
        restored = parent / "restored"
        restore(REPO, archive, restored)
        with listening(restored, workers=False) as (_, client):
            assert client.get(f"/api/weather/schedules/{schedule_id}").content == paused
            for version, body in evidence.items():
                assert client.get("/api/weather/labels/" + version[7:]).content == body
            assert frozen in client.get("/api/weather/datasets").json()
            assert len(calls) == 24
