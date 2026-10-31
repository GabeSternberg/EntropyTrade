"""Actual-loop failures with CONTROLLED sources/clocks; never empirical history evidence."""

import base64
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.api.recovery import validate_database
from entropytrade.domain.time import SimulatedClock
from entropytrade.weather.history import load_snapshot
from entropytrade.weather.label_service import LabelService, batches
from entropytrade.weather.labels import load_batch
from tests.integration.forward_validation_fixture import NOW, portal, seed_dates
from tests.unit.test_label_lifecycle import assert_released


@pytest.mark.parametrize("failure", ["acquisition", "second_receipt_save"])
def test_loop_failure_retains_persisted_receipt_through_reconciliation_restart_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    clock = SimulatedClock(NOW)
    monkeypatch.setattr("entropytrade.weather.label_service.utc_now", clock.now)
    monkeypatch.setattr("entropytrade.weather.label_schedule.utc_now", clock.now)
    service = LabelService(tmp_path / "controlled")
    initial = seed_dates(service.workspace, count=2)
    schedule_id = str(uuid4())
    service.scheduler.create(
        {
            "id": schedule_id,
            "dataset_id": initial["dataset_id"][7:],
            "enabled": True,
            "interval_seconds": 300,
            "batch_dates": 8,
        }
    )
    calls: list[str] = []
    first: dict[str, Any] = {}
    bodies: list[bytes] = []
    failed_saves: list[str] = []
    waits: list[float] = []
    acquire, save = service.acquire, service.save

    def source(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.host == "weather.com"
        assert "authorization" not in req.headers
        assert "cookie" not in req.headers
        calls.append(req.url.params["date"])
        if len(calls) == 2:
            current = service.catalog()[0]
            assert current["status"] == "running"
            assert len(current["receipts"]) == 1
            first.update(current)
            clock.advance(timedelta(seconds=1))
            if failure == "acquisition":
                raise ValueError("CONTROLLED acquisition error after durable first receipt")
        response = httpx.Response(200, json=portal(req.url.params["date"]))
        bodies.append(response.content)
        return response

    async def controlled(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        await acquire(request, httpx.MockTransport(source))

    def transient_save(request: dict[str, Any]) -> None:
        if (
            failure == "second_receipt_save"
            and request["status"] == "running"
            and len(request["receipts"]) == 2
            and not failed_saves
        ):
            failed_saves.append(request["id"])
            raise OSError("CONTROLLED transient second-receipt save error")
        save(request)

    def end_iteration(seconds: float) -> bool:
        waits.append(seconds)
        service.stop.set()
        return True

    monkeypatch.setattr(service, "acquire", controlled)
    monkeypatch.setattr(service, "save", transient_save)
    monkeypatch.setattr(service.stop, "wait", end_iteration)
    # Exercise selection, bounded ownership, real receipt persistence and loop-level
    # exception finalization, rather than finishing a hand-built partial request.
    service.loop()
    assert waits == [0.2]
    assert calls == ["2026-10-01", "2026-10-02"]
    assert bool(failed_saves) == (failure == "second_receipt_save")
    assert len(service.catalog()) == 1
    failed = service.get(first["id"])
    assert failed["status"] == "failed"
    assert failed["detail"].startswith("ValueError" if failure == "acquisition" else "OSError")
    assert failed["created_at"] == first["created_at"]
    assert failed["selection"] == first["selection"]
    assert failed["receipts"] == first["receipts"]
    assert base64.b64decode(failed["receipts"][0]["body_base64"]) == bodies[0]
    assert failed["result"]["verified_events"] == failed["result"]["refused_events"] == 1
    assert_released(service)

    request_path = service.root / "requests" / (first["id"] + ".json")
    batch_path = service.batch_path(failed["batch_version"])
    batch = load_batch(batch_path)
    assert batch.receipts[0].body() == bodies[0]
    assert batch.receipts[0].received_at == NOW
    observation = batch.summary()["records"][0]["observation"]
    assert observation["available_at"] == observation["received_at"]
    assert observation["published_at"] is observation["revised_at"] is None
    before = request_path.read_bytes(), batch_path.read_bytes()
    service.scheduler.tick()
    reconciled = service.scheduler.get(schedule_id)
    assert reconciled.inflight is None
    assert [(w.day.isoformat(), w.status) for w in reconciled.work] == [
        ("2026-10-01", "verified"),
        ("2026-10-02", "retry"),
    ]
    assert all(
        w.last_request == first["id"] and w.last_batch == failed["batch_version"]
        for w in reconciled.work
    )
    schedule_path = service.scheduler.root / (schedule_id + ".json")
    schedule_before = schedule_path.read_bytes()
    assert (request_path.read_bytes(), batch_path.read_bytes()) == before

    reopened = LabelService(service.workspace)
    reopened.recover()
    reopened.scheduler.tick()
    reopened.scheduler.validate()
    assert reopened.get(first["id"]) == failed
    assert reopened.scheduler.get(schedule_id) == reconciled
    assert batches(service.workspace) == [batch_path]
    assert validate_database(service.workspace)["jobs"] == 2
    assert (request_path.read_bytes(), batch_path.read_bytes()) == before
    assert schedule_path.read_bytes() == schedule_before
    assert len(reopened.catalog()) == 1
    assert len(calls) == 2
    assert (
        load_snapshot(service.workspace / "runs/weather-datasets" / initial["dataset_id"][7:])
        == initial
    )


@pytest.mark.parametrize("terminal", ["completed", "failed", "interrupted"])
def test_loop_error_cannot_replace_terminal_request_or_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    service = LabelService(tmp_path / "controlled")
    initial = seed_dates(service.workspace, count=1)
    queued = service.create({"id": str(uuid4()), "dataset_id": initial["dataset_id"][7:]})
    before: list[tuple[Path, bytes]] = []

    async def complete_then_raise(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        service.finish(request, terminal, "CONTROLLED terminal evidence before late error")
        finished = service.get(request["id"])
        before.extend(
            (path, path.read_bytes())
            for path in (
                service.root / "requests" / (request["id"] + ".json"),
                service.batch_path(finished["batch_version"]),
            )
        )
        raise ValueError("CONTROLLED late acquisition error")

    def end_iteration(seconds: float) -> bool:
        service.stop.set()
        return True

    monkeypatch.setattr(service, "acquire", complete_then_raise)
    monkeypatch.setattr(service.stop, "wait", end_iteration)
    service.loop()
    assert service.get(queued["id"])["status"] == terminal
    assert len(before) == 2
    assert all(path.read_bytes() == raw for path, raw in before)
    assert len(list((service.root / "batches").glob("*.json"))) == 1
    assert_released(service)
