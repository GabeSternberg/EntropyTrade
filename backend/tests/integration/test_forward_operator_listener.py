"""Forward operator against the real listener API with CONTROLLED retained inputs.

Source responses come from a mock transport, so no public request is made. This checks the
operator against the actual schedule/partition/monitor response shapes rather than fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest

from entropytrade.operations.forward import ensure_monitor, ensure_schedule, summarize
from entropytrade.weather.label_service import LabelService
from tests.integration.forward_validation_fixture import portal, seed_dates
from tests.integration.test_workbench_listener import listening
from tests.integration.weather_history_retained import REPO


class ClientApi:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.headers = {"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]}

    def get(self, path: str) -> Any:
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, body: dict[str, Any]) -> Any:
        response = self.client.post(path, json=body, headers=self.headers)
        response.raise_for_status()
        return response.json()


def test_operator_schedule_lifecycle_on_real_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    original = LabelService.acquire

    async def controlled(
        self: LabelService,
        request: dict[str, Any],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        def source(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=portal(req.url.params["date"], "preliminary"))

        await original(self, request, httpx.MockTransport(source))

    monkeypatch.setattr(LabelService, "acquire", controlled)
    started = datetime.now(UTC)
    with TemporaryDirectory(prefix="forward-operator-", dir=REPO / "data/cache") as name:
        root = Path(name) / "workspace"
        seed_dates(root, count=3)
        with listening(root, workers=False) as (_, client):
            api = ClientApi(client)
            created = ensure_schedule(api, 3600)
            assert created["action"] == "schedule_created"
            assert created["follow_retained"] is True
            schedule = api.get("/api/weather/schedules/" + created["schedule_id"])
            assert schedule["config"]["dataset_id"] == created["dataset_id"]
            assert schedule["config"]["interval_seconds"] == 3600
            assert schedule["status"] == "active"
            assert schedule["controls"][0]["action"] == "opt_in"

            assert ensure_schedule(api, 3600) == {
                "action": "schedule_kept",
                "schedule_id": created["schedule_id"],
            }
            api.post(f"/api/weather/schedules/{created['schedule_id']}/pause", {})
            review = ensure_schedule(api, 3600)
            assert review["action"] == "operator_review_required"
            assert review["schedules"] == [{"id": created["schedule_id"], "status": "paused"}]
            # Still paused: the operator did not resume it.
            assert api.get("/api/weather/schedules")[0]["status"] == "paused"

            # Seeded CONTROLLED monitors are left alone; none is resumed or replaced.
            monitors = api.get("/api/monitors")
            if monitors and all(m["status"] != "active" for m in monitors):
                assert ensure_monitor(api, 600)["action"] == "operator_review_required"

            summary = summarize(api, started)
            assert summary["schedules"][0]["id"] == created["schedule_id"]
            assert summary["schedules"][0]["status"] == "paused"
            assert summary["retained_inputs"]["total_inputs"] > 0
            assert summary["submission_enabled"] is False
