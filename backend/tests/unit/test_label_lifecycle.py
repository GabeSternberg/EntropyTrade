"""Barrier-controlled cancellation interleavings; controlled sources are not market evidence."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.weather.label_service import LabelService
from tests.integration.forward_validation_fixture import portal, seed_dates


@pytest.fixture
def scheduled(tmp_path: Path) -> tuple[LabelService, str, str]:
    service = LabelService(tmp_path / "controlled")
    snapshot = seed_dates(service.workspace, count=2)
    schedule = service.scheduler.create(
        {
            "id": str(uuid4()),
            "dataset_id": snapshot["dataset_id"][7:],
            "enabled": True,
            "interval_seconds": 300,
            "batch_dates": 8,
        }
    )
    service.scheduler.tick()
    request = service.catalog()[0]
    assert request["status"] == "queued"
    return service, schedule["config"]["id"], request["id"]


def evidence(service: LabelService, request_id: str) -> tuple[bytes, bytes]:
    request = service.get(request_id)
    assert request["status"] == "interrupted"
    return (
        (service.root / "requests" / (request_id + ".json")).read_bytes(),
        service.batch_path(request["batch_version"]).read_bytes(),
    )


def assert_released(service: LabelService) -> None:
    assert service.active_request is None
    assert service.active_task is None
    assert service.active_loop is None
    assert not service.cancel_requested


@pytest.mark.parametrize("terminal", ["interrupted", "completed", "failed"])
def test_queued_selection_cannot_start_after_durable_completion(
    scheduled: tuple[LabelService, str, str], monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    service, schedule_id, request_id = scheduled
    selected, resume = threading.Barrier(2), threading.Barrier(2)
    starts: list[str] = []

    async def unexpected(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        starts.append(request["id"])
        service.finish(request, "completed", "Stale worker must not replace durable evidence")

    monkeypatch.setattr(service, "acquire", unexpected)

    def worker() -> None:
        stale = service.catalog()[0]
        selected.wait(timeout=10)
        resume.wait(timeout=10)
        asyncio.run(service.bounded(stale))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            selected.wait(timeout=10)
            if terminal == "interrupted":
                service.scheduler.control(schedule_id, "pause")
            else:
                service.finish(service.get(request_id), terminal, "CONTROLLED prior completion")
            path = service.root / "requests" / (request_id + ".json")
            before = path.read_bytes()
            batch = service.batch_path(service.get(request_id)["batch_version"])
            batch_before = batch.read_bytes()
        finally:
            resume.wait(timeout=10)
        future.result(timeout=10)
    assert starts == []
    assert path.read_bytes() == before
    assert batch.read_bytes() == batch_before
    assert len(service.catalog()) == len(list((service.root / "batches").glob("*.json"))) == 1
    assert_released(service)


@pytest.mark.parametrize("action", ["pause", "shutdown"])
def test_cancellation_between_active_registration_and_acquisition_start(
    scheduled: tuple[LabelService, str, str], monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    service, schedule_id, request_id = scheduled
    registered, resume = threading.Barrier(2), threading.Barrier(2)
    calls: list[str] = []
    original = service.acquire

    def source(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=portal(request.url.params["date"]))

    async def before_start(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        registered.wait(timeout=10)
        resume.wait(timeout=10)
        # No asyncio yield: a scheduled task.cancel callback cannot protect this gap.
        await original(request, httpx.MockTransport(source))

    monkeypatch.setattr(service, "acquire", before_start)
    stale = service.get(request_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: asyncio.run(service.bounded(stale)))
        try:
            registered.wait(timeout=10)
            with service.lock:
                assert service.active_request == request_id
                assert service.active_task is not None
                assert service.active_loop is not None
                assert service.get(request_id)["status"] == "running"
            if action == "pause":
                service.scheduler.control(schedule_id, "pause")
            else:
                service.close()
            assert service.cancel_requested
        finally:
            resume.wait(timeout=10)
        future.result(timeout=10)
    assert calls == []
    interrupted = service.get(request_id)
    assert interrupted["receipts"] == []
    before = evidence(service, request_id)
    service.cancel(request_id)
    # Replaying an old queue selection and late completion cannot change terminal bytes.
    asyncio.run(service.bounded(stale))
    service.finish(stale, "completed", "CONTROLLED late completion")
    service.recover()
    assert evidence(service, request_id) == before
    assert_released(service)


def test_repeated_claim_cannot_replace_running_ownership(
    scheduled: tuple[LabelService, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, request_id = scheduled
    original = service.acquire
    calls: list[str] = []

    def source(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=portal(request.url.params["date"]))

    async def claimed(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        owner = service.active_task
        await service.bounded(request)
        assert service.active_task is owner is asyncio.current_task()
        await original(request, httpx.MockTransport(source))

    monkeypatch.setattr(service, "acquire", claimed)
    asyncio.run(service.bounded(service.get(request_id)))
    assert service.get(request_id)["status"] == "completed"
    assert len(calls) == 2
    assert_released(service)
