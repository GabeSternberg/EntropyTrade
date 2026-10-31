"""CONTROLLED rollover/recovery checks. Accelerated receipts prove no elapsed operation."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.api.recovery import validate_database
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.weather.history import build_snapshot, load_snapshot
from entropytrade.weather.label_partitions import LabelPartitions
from entropytrade.weather.label_service import LabelService, batches
from tests.integration.forward_validation_fixture import NOW, portal, seed_dates


@pytest.fixture
def collected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[LabelService, dict[str, Any], SimulatedClock, list[str]]:
    clock = SimulatedClock(NOW)
    for module in ("label_schedule", "label_service", "label_partitions"):
        monkeypatch.setattr(f"entropytrade.weather.{module}.utc_now", clock.now)
    service = LabelService(tmp_path / "controlled")
    initial = seed_dates(service.workspace, count=1)
    calls: list[str] = []

    async def acquire(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        def source(req: httpx.Request) -> httpx.Response:
            calls.append(request["id"])
            if len(calls) == 128:
                return httpx.Response(503, text="CONTROLLED boundary outage")
            return httpx.Response(200, json=portal(req.url.params["date"]))

        await LabelService.acquire(service, request, httpx.MockTransport(source))

    monkeypatch.setattr(service, "acquire", acquire)
    return service, initial, clock, calls


def collect(service: LabelService, initial: dict[str, Any], clock: SimulatedClock) -> str:
    request_id = str(uuid4())
    request = service.create({"id": request_id, "dataset_id": initial["dataset_id"][7:]})
    asyncio.run(service.bounded(request))
    clock.advance(timedelta(days=1))
    return request_id


def test_260_controlled_acquisition_batches_two_rollovers_idempotency_and_frozen_clocks(
    collected: tuple[LabelService, dict[str, Any], SimulatedClock, list[str]],
) -> None:
    service, initial, clock, calls = collected
    ids = [collect(service, initial, clock) for _ in range(260)]
    assert calls == ids
    partitions = service.partitions.catalog()
    assert [p["requests"] for p in partitions] == [128, 128, 4]
    assert [p["status"] for p in partitions] == ["sealed", "sealed", "active"]
    assert len(batches(service.workspace)) == 260
    assert len(service.active_catalog()) == 4
    original = service.get(ids[0])
    assert original["receipts"][0]["received_at"] == NOW.isoformat().replace("+00:00", "Z")
    before = {p: file_hash(p) for p in service.root.rglob("*.json")}
    assert service.create({"id": ids[0], "dataset_id": initial["dataset_id"][7:]}) == original
    assert len(calls) == 260
    with pytest.raises(ValueError, match="sealed"):
        service.save(original)
    stale = {**original, "receipts": []}
    service.finish(stale, "failed", "stale completion")
    assert service.get(ids[0]) == original
    assert service.get(ids[127])["result"]["verified_events"] == 0
    assert service.get(ids[128])["result"]["verified_events"] == 1
    assert all(file_hash(p) == digest for p, digest in before.items())
    reopened = LabelService(service.workspace)
    reopened.recover()
    assert reopened.get(ids[0]) == original
    assert all(file_hash(p) == digest for p, digest in before.items())
    captures = [
        service.workspace / "runs" / j.name / "public"
        for j in (service.workspace / "runs").iterdir()
        if (j / "public").is_dir()
    ]
    frozen = build_snapshot(
        service.workspace / "runs/weather-datasets",
        captures,
        scalar_batches=batches(service.workspace),
    )
    assert len(frozen["identity"]["scalar_label_inputs"]) == 260
    assert frozen["identity"]["temporal_boundaries"] == initial["identity"]["temporal_boundaries"]
    assert frozen["identity"]["protected_events"] == initial["identity"]["protected_events"]
    assert frozen["readiness"]["scalar_label_events"] == 1
    assert frozen["readiness"]["status"] == "insufficient_data"
    load_snapshot(service.workspace / "runs/weather-datasets" / frozen["dataset_id"][7:])
    validate_database(service.workspace)
    # Unpartitioned arbitrary input lists still obey the original reader bound.
    with pytest.raises(ValueError, match="128 inputs"):
        build_snapshot(
            service.workspace / "unused", captures, scalar_batches=list(batches(service.workspace))
        )


def test_seal_crash_then_reconcile_same_schedule_plan_without_duplicate_network(
    collected: tuple[LabelService, dict[str, Any], SimulatedClock, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, initial, clock, calls = collected
    for _ in range(128):
        collect(service, initial, clock)
    schedule_id = str(uuid4())
    service.scheduler.create(
        {"id": schedule_id, "dataset_id": initial["dataset_id"][7:], "enabled": True}
    )
    original = Path.mkdir

    def crash(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name == "00000001":
            raise OSError("CONTROLLED interruption after seal")
        original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", crash)
    service.scheduler.tick()
    blocked = service.scheduler.get(schedule_id)
    assert blocked.status == "blocked"
    assert blocked.inflight
    assert len(calls) == 128
    manifest = (service.root / "partition.json").read_bytes()
    monkeypatch.setattr(Path, "mkdir", original)
    reopened = LabelService(service.workspace)
    reopened.recover()
    assert reopened.active_catalog() == []
    reopened.scheduler.control(schedule_id, "resume")
    reopened.scheduler.tick()
    assert reopened.active_catalog()[0]["id"] == blocked.inflight
    assert (service.root / "partition.json").read_bytes() == manifest
    assert len(calls) == 128
    reopened.cancel(blocked.inflight)
    reopened.scheduler.control(schedule_id, "pause")
    reopened.scheduler.tick()
    cancelled = reopened.get(blocked.inflight)
    assert cancelled["status"] == "interrupted"
    assert cancelled["receipts"] == []
    assert reopened.scheduler.get(schedule_id).inflight is None
    reopened.scheduler.validate()
    validate_database(service.workspace)


@pytest.mark.parametrize("change", ["request", "batch", "extra", "chain", "symlink"])
def test_sealed_corruption_fails_closed(
    collected: tuple[LabelService, dict[str, Any], SimulatedClock, list[str]],
    change: str,
) -> None:
    service, initial, clock, _ = collected
    for _ in range(128):
        collect(service, initial, clock)
    service.create({"id": str(uuid4()), "dataset_id": initial["dataset_id"][7:]})
    if change in {"request", "batch"}:
        path = next(
            (service.root / ("requests" if change == "request" else "batches")).glob("*.json")
        )
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "extra":
        (service.root / "requests" / (str(uuid4()) + ".json")).write_text("{}")
    elif change == "chain":
        path = service.root / "partition.json"
        value = json.loads(path.read_bytes())
        value["previous"] = "sha256:" + "a" * 64
        value["version"] = scientific_hash({k: v for k, v in value.items() if k != "version"})
        path.write_text(json.dumps(value))
    else:
        path = service.root / "partitions/00000001"
        path.rename(path.with_name("moved"))
        path.symlink_to(path.with_name("moved"), target_is_directory=True)
    with pytest.raises(ValueError, match="label partition"):
        LabelService(service.workspace).recover()
    with pytest.raises(ValueError, match="label partition"):
        batches(service.workspace)
    with pytest.raises(ValueError, match="label partition"):
        validate_database(service.workspace)


def test_invalid_partition_selection_and_legacy_readonly_validation(tmp_path: Path) -> None:
    store = LabelPartitions(tmp_path / "unused")
    assert store.catalog()[0]["requests"] == 0
    store.validate()
    assert not store.root.exists()
    for value in ("../", "1", "00000001", "00000000/requests"):
        with pytest.raises(ValueError, match="label partition"):
            store.selected(value)


def test_busy_rollover_keeps_schedule_active_and_reuses_original_plan_after_drain(
    collected: tuple[LabelService, dict[str, Any], SimulatedClock, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, initial, clock, calls = collected
    monkeypatch.setattr("entropytrade.weather.label_partitions.SIZE", 2)
    collect(service, initial, clock)
    pending = service.create({"id": str(uuid4()), "dataset_id": initial["dataset_id"][7:]})
    schedule_id = str(uuid4())
    service.scheduler.create(
        {"id": schedule_id, "dataset_id": initial["dataset_id"][7:], "enabled": True}
    )
    service.scheduler.tick()
    waiting = service.scheduler.get(schedule_id)
    assert waiting.status == "active"
    assert waiting.inflight
    assert "waiting for drain" in waiting.detail
    service.scheduler.tick()
    assert service.scheduler.get(schedule_id).inflight == waiting.inflight
    assert len(calls) == 1
    asyncio.run(service.bounded(pending))
    service.scheduler.tick()
    assert service.active_catalog()[0]["id"] == waiting.inflight
    asyncio.run(service.bounded(service.get(waiting.inflight)))
    service.scheduler.tick()
    assert service.scheduler.get(schedule_id).work[0].status == "verified"
    assert service.scheduler.get(schedule_id).inflight is None
    assert len(calls) == 3
    assert service.partitions.catalog()[0]["status"] == "sealed"


def test_missing_terminal_batch_cannot_be_mistaken_for_unpublished_request(
    collected: tuple[LabelService, dict[str, Any], SimulatedClock, list[str]],
) -> None:
    service, initial, _, calls = collected
    schedule_id = str(uuid4())
    service.scheduler.create(
        {"id": schedule_id, "dataset_id": initial["dataset_id"][7:], "enabled": True}
    )
    service.scheduler.tick()
    planned = service.scheduler.get(schedule_id)
    assert planned.inflight
    request = service.get(planned.inflight)
    asyncio.run(service.bounded(request))
    terminal = service.get(planned.inflight)
    path = service.partitions.locate("requests", planned.inflight)
    original = path.read_bytes()
    service.batch_path(terminal["batch_version"]).unlink()
    with pytest.raises(ValueError, match="batch evidence missing"):
        service.create({"id": planned.inflight, "dataset_id": initial["dataset_id"][7:]})
    with pytest.raises(ValueError, match="batch evidence missing"):
        service.enqueue(planned.inflight, terminal["selection"])
    service.scheduler.tick()
    blocked = service.scheduler.get(schedule_id)
    assert blocked.status == "blocked"
    assert blocked.inflight == planned.inflight
    assert "batch evidence missing" in blocked.detail
    assert calls == [planned.inflight]
    assert path.read_bytes() == original
    assert len(list((service.root / "requests").glob("*.json"))) == 1
    assert not list((service.root / "batches").glob("*.json"))
