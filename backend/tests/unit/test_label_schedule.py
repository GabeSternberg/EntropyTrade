"""Durable scheduling software checks. Controlled clocks/HTTP are never empirical history."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.weather.history import build_snapshot, load_snapshot
from entropytrade.weather.label_schedule import Schedule
from entropytrade.weather.label_service import LabelService, batches
from entropytrade.weather.labels import load_batch
from tests.integration.forward_validation_fixture import NOW, portal, seed_dates
from tests.integration.weather_history_retained import SOURCE


@pytest.fixture
def controlled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[LabelService, dict[str, Any], SimulatedClock]:
    clock = SimulatedClock(NOW)
    monkeypatch.setattr("entropytrade.weather.label_schedule.utc_now", clock.now)
    monkeypatch.setattr("entropytrade.weather.label_service.utc_now", clock.now)
    root = tmp_path / "controlled"
    initial = seed_dates(root)
    return LabelService(root), initial, clock


def config(snapshot: dict[str, Any], **changes: object) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "dataset_id": snapshot["dataset_id"][7:],
        "enabled": True,
        "interval_seconds": 300,
        "batch_dates": 8,
        **changes,
    }


def execute(service: LabelService, phase: str = "official") -> list[str]:
    calls = []

    def source(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.host == "weather.com"
        assert "authorization" not in req.headers
        assert "cookie" not in req.headers
        calls.append(req.url.params["date"])
        if phase == "outage":
            return httpx.Response(503, text="CONTROLLED outage")
        return httpx.Response(200, json=portal(req.url.params["date"], phase))

    for request in service.catalog():
        if request["status"] == "queued":
            asyncio.run(service.bounded(request, httpx.MockTransport(source)))
    return calls


def current(service: LabelService, schedule_id: str) -> Schedule:
    return service.scheduler.get(schedule_id)


def test_over_eight_dates_fair_batches_revisions_restarts_and_immutable_snapshots(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    service, initial, clock = controlled
    selection = config(initial)
    schedule_id = selection["id"]
    with pytest.raises(ValueError, match="eight dates"):
        service.create({"id": str(uuid4()), "dataset_id": selection["dataset_id"]})
    before = load_snapshot(service.workspace / "runs/weather-datasets" / selection["dataset_id"])
    assert service.scheduler.catalog() == []
    created = service.scheduler.create(selection)
    assert len(created["work"]) == 12
    assert service.scheduler.create(selection) == created
    service.scheduler.tick()
    assert len(execute(service, "preliminary")) == 8
    service.scheduler.tick()
    # Older pending dates go first rather than being starved by preliminary retries.
    assert len(execute(service, "preliminary")) == 4
    service.scheduler.tick()
    assert all(w.status == "retry" for w in current(service, schedule_id).work)
    assert not execute(service)
    receipts = {p.name: p.read_bytes() for p in batches(service.workspace)}
    clock.advance(timedelta(seconds=300))
    reopened = LabelService(service.workspace)
    reopened.recover()
    reopened.scheduler.tick()
    assert len(execute(reopened)) == 8
    reopened.scheduler.tick()
    assert len(execute(reopened)) == 4
    reopened.scheduler.tick()
    assert all(
        w.status == "verified" and w.attempts == 2 for w in current(reopened, schedule_id).work
    )
    assert all(
        p.read_bytes() == receipts[p.name] for p in batches(service.workspace) if p.name in receipts
    )
    assert (
        load_snapshot(service.workspace / "runs/weather-datasets" / selection["dataset_id"])
        == before
    )
    first_versions = [load_batch(p) for p in batches(service.workspace)]
    assert all(len(b.receipts) <= 8 for b in first_versions)
    clock.advance(timedelta(days=1))
    reopened.scheduler.tick()
    assert len(execute(reopened, "revised")) == 8
    reopened.scheduler.tick()
    assert len(execute(reopened, "revised")) == 4
    reopened.scheduler.tick()
    observations = [
        r["observation"]
        for p in batches(service.workspace)
        for r in load_batch(p).records()
        if r["observation"]
    ]
    assert {int(o["value"]) for o in observations} == {70, 72}
    assert all(o["available_at"] == o["received_at"] for o in observations)
    assert all(o["published_at"] is None for o in observations)
    assert min(o["available_at"] for o in observations if int(o["value"]) == 72) > max(
        o["available_at"] for o in observations if int(o["value"]) == 70
    )


def test_outages_backoff_pause_recovery_and_no_duplicate_request_after_crash(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock], monkeypatch: pytest.MonkeyPatch
) -> None:
    service, initial, clock = controlled
    schedule_id = service.scheduler.create(config(initial))["config"]["id"]
    service.scheduler.tick()
    planned = current(service, schedule_id)
    assert planned.inflight
    # Finish the network work, then lose only the scheduler bookkeeping.
    assert len(execute(service, "outage")) == 8
    reopened = LabelService(service.workspace)
    reopened.recover()
    reopened.scheduler.tick()
    assert len(execute(reopened, "outage")) == 4
    reopened.scheduler.tick()
    failed = current(reopened, schedule_id)
    assert all(w.failures == 1 and w.attempts == 1 for w in failed.work)
    assert len(reopened.catalog()) == 2
    reopened.scheduler.control(schedule_id, "pause")
    clock.advance(timedelta(hours=2))
    reopened.scheduler.tick()
    assert len(reopened.catalog()) == 2
    reopened.scheduler.control(schedule_id, "resume")
    reopened.scheduler.tick()
    assert len(execute(reopened, "outage")) == 8
    reopened.scheduler.tick()
    execute(reopened, "outage")
    reopened.scheduler.tick()
    failed = current(reopened, schedule_id)
    assert all(w.next_at == clock.now() + timedelta(seconds=600) for w in failed.work)
    # Crash after the new durable plan, before request publication.
    clock.advance(timedelta(seconds=600))
    original = reopened.enqueue

    def crash(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise InterruptedError("CONTROLLED crash before enqueue")

    monkeypatch.setattr(reopened, "enqueue", crash)
    reopened.scheduler.tick()
    interrupted = current(reopened, schedule_id)
    assert interrupted.status == "blocked"
    assert interrupted.inflight
    request_id = interrupted.inflight
    monkeypatch.setattr(reopened, "enqueue", original)
    reopened.scheduler.control(schedule_id, "resume")
    reopened.scheduler.tick()
    assert current(reopened, schedule_id).inflight == request_id
    assert reopened.get(request_id)["status"] == "queued"
    reopened.scheduler.tick()
    assert len([r for r in reopened.catalog() if r["id"] == request_id]) == 1
    reopened.scheduler.control(schedule_id, "pause")
    assert reopened.get(request_id)["status"] == "interrupted"


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": False},
        {"enabled": 1},
        {"batch_dates": 9},
        {"interval_seconds": 1},
        {"url": "https://invalid.example"},
        {"follow_retained": "yes"},
    ],
)
def test_optin_budgets_and_scope_fail_closed(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock], change: dict[str, Any]
) -> None:
    service, initial, _ = controlled
    with pytest.raises(ValueError, match=r"opt-in|validation error"):
        service.scheduler.create(config(initial, **change))
    assert service.catalog() == []


def test_protection_added_after_optin_prevents_source_access(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock], monkeypatch: pytest.MonkeyPatch
) -> None:
    service, initial, _ = controlled
    selection = config(initial)
    service.scheduler.create(selection)
    original = service.selection

    def protected(dataset_id: str) -> dict[str, Any]:
        value = original(dataset_id)
        return {
            **value,
            "targets": [{**t, "refusal": "protected label excluded"} for t in value["targets"]],
        }

    monkeypatch.setattr(service, "selection", protected)
    service.scheduler.tick()
    assert execute(service) == []
    service.scheduler.tick()
    assert execute(service) == []
    service.scheduler.tick()
    assert all(w.status == "refused" for w in current(service, selection["id"]).work)


def test_follow_retained_authentic_shadow_discovery_and_offline_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.shadow_history_fixture import seed_authentic

    root = tmp_path / "authentic"
    seed_authentic(root)
    service = LabelService(root)
    first = build_snapshot(root / "runs/weather-datasets", sorted(SOURCE.glob("*/*/public"))[:1])
    clock = SimulatedClock(NOW)
    monkeypatch.setattr("entropytrade.weather.label_schedule.utc_now", clock.now)
    selected = service.scheduler.create(config(first, follow_retained=True))
    assert len(selected["work"]) == 2
    service.scheduler.tick()
    schedule = current(service, selected["config"]["id"])
    assert len(schedule.work) == 2
    assert schedule.discovery_cursor == 1
    assert schedule.inflight
    # This test never executes a new acquisition or changes an authentic receipt clock.
    service.scheduler.control(schedule.config.id, "pause")
    source = list((root / "runs/weather-datasets").glob("[0-9a-f]" * 64))
    assert any(load_snapshot(p)["readiness"].get("shadow_audit") for p in source)
    assert all(
        load_snapshot(p)["identity"]["temporal_boundaries"]
        == first["identity"]["temporal_boundaries"]
        for p in source
    )


def test_corruption_and_symlink_schedule_fail_closed(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    service, initial, _ = controlled
    schedule = service.scheduler.create(config(initial))
    path = service.scheduler.root / (schedule["config"]["id"] + ".json")
    value = json.loads(path.read_bytes())
    value["schedule"]["status"] = "paused"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="digest"):
        service.scheduler.tick()
    assert service.catalog() == []


def test_follow_enrolls_unseen_dates_without_reacquiring_existing_targets(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    service, initial, _ = controlled
    jobs = service.workspace / "runs"
    captures = sorted(jobs.glob("*/public"))
    first_capture = min(
        captures, key=lambda p: json.loads((p / "capture.json").read_text())["decision_time"]
    )
    first = build_snapshot(jobs / "weather-datasets", [first_capture])
    selected = service.scheduler.create(config(first, follow_retained=True))
    schedule_id = selected["config"]["id"]
    assert len(selected["work"]) == 1
    service.scheduler.tick()
    schedule = current(service, schedule_id)
    assert len(schedule.work) == 12
    assert len({t.event_id for w in schedule.work for t in w.targets}) == 12
    assert execute(service)
    service.scheduler.validate()
    assert all(
        load_snapshot(p)["identity"]["temporal_boundaries"]
        == initial["identity"]["temporal_boundaries"]
        for p in (jobs / "weather-datasets").glob("[0-9a-f]" * 64)
    )


def test_active_schedule_shutdown_partial_receipt_and_restart_retry(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock], monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    service, initial, clock = controlled
    selected = service.scheduler.create(config(initial))
    schedule_id = selected["config"]["id"]
    arrived = threading.Event()
    calls: list[str] = []
    original = service.acquire

    async def source(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.params["date"])
        if len(calls) == 2:
            arrived.set()
            await asyncio.Event().wait()
        return httpx.Response(200, json=portal(req.url.params["date"]))

    async def controlled_source(
        request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        await original(request, httpx.MockTransport(source))

    monkeypatch.setattr(service, "acquire", controlled_source)
    service.thread.start()
    try:
        assert arrived.wait(10)
    finally:
        service.close()
    assert not service.thread.is_alive()
    interrupted = next(r for r in service.catalog() if r["status"] == "interrupted")
    assert len(interrupted["receipts"]) == 1
    raw = interrupted["receipts"][0]
    reopened = LabelService(service.workspace)
    reopened.recover()
    reopened.scheduler.tick()
    saved = current(reopened, schedule_id)
    assert sum(w.status == "verified" for w in saved.work) == 1
    assert sum(w.status == "retry" for w in saved.work) == 7
    execute(reopened)
    reopened.scheduler.tick()
    clock.advance(timedelta(seconds=300))
    reopened.scheduler.tick()
    retried = execute(reopened)
    assert calls[0] not in retried
    assert len(retried) == 7
    assert reopened.get(interrupted["id"])["receipts"][0] == raw
    reopened.scheduler.validate()


def test_partition_publication_failure_retains_original_plan_until_explicit_resume(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock], monkeypatch: pytest.MonkeyPatch
) -> None:
    service, initial, _ = controlled
    selected = service.scheduler.create(config(initial))
    schedule_id = selected["config"]["id"]
    original = service.partitions.prepare

    def unavailable(owner: LabelService) -> Path:
        raise OSError("partition publication unavailable")

    monkeypatch.setattr(service.partitions, "prepare", unavailable)
    service.scheduler.tick()
    blocked = current(service, schedule_id)
    assert blocked.status == "blocked"
    assert "partition publication unavailable" in blocked.detail
    assert blocked.inflight
    service.scheduler.tick()
    assert current(service, schedule_id) == blocked
    service.scheduler.control(schedule_id, "pause")
    service.scheduler.tick()
    assert current(service, schedule_id).inflight == blocked.inflight
    monkeypatch.setattr(service.partitions, "prepare", original)
    reopened = LabelService(service.workspace)
    reopened.recover()
    reopened.scheduler.control(schedule_id, "resume")
    reopened.scheduler.tick()
    assert reopened.get(blocked.inflight)["status"] == "queued"
    assert len(reopened.catalog()) == 1


def test_dangling_symlink_schedule_is_never_followed(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    service, initial, _ = controlled
    selected = service.scheduler.create(config(initial))
    path = service.scheduler.root / (selected["config"]["id"] + ".json")
    destination = service.workspace / "untouched.json"
    path.unlink()
    path.symlink_to(destination)
    with pytest.raises(ValueError, match="unsafe"):
        service.scheduler.get(selected["config"]["id"])
    assert not destination.exists()
    assert service.catalog() == []


def datasets(service: LabelService) -> set[Path]:
    return set((service.workspace / "runs/weather-datasets").glob("[0-9a-f]" * 64))


def test_follow_freezes_each_retained_input_into_at_most_one_discovery_dataset(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    """Regression: discovery re-froze the whole growing partition every interval.

    Authentic chained snapshots grew from 243 MB to 331 MB in two cycles because every
    discovery dataset copied every earlier retained cycle again.
    """
    from tests.integration.forward_validation_fixture import add_date

    service, initial, _ = controlled
    created = service.scheduler.create(config(initial, follow_retained=True))
    schedule = current(service, created["config"]["id"])
    first = service.scheduler.discover(schedule)
    assert len(first.discovered) == 12
    assert first.work == schedule.work  # all twelve dates were already enrolled
    before = datasets(service)

    # No new retained input: no new immutable dataset and nothing is copied again.
    again = service.scheduler.discover(first)
    assert datasets(service) == before
    assert again.discovered == first.discovered
    assert again.work == first.work
    assert again.discovery_cursor == first.discovery_cursor

    add_date(service.workspace, 12)
    add_date(service.workspace, 13)
    second = service.scheduler.discover(again)
    new = datasets(service) - before
    assert len(new) == 1
    snapshot = load_snapshot(new.pop())
    assert len(snapshot["identity"]["captures"]) == 2  # only the two new inputs
    assert snapshot["identity"]["selection"]["discovery"] == "incremental"
    assert snapshot["identity"]["selection"]["inputs"] == sorted(second.discovered[12:])
    assert snapshot["identity"]["temporal_boundaries"] == initial["identity"]["temporal_boundaries"]
    assert len(second.discovered) == 14
    assert second.work[: len(first.work)] == first.work  # earlier plans never change
    assert {w.day.isoformat() for w in second.work[len(first.work) :]} == {
        "2026-10-13",
        "2026-10-14",
    }
    # One new input per interval: total frozen copies grow linearly, not quadratically.
    latest, seen = second, datasets(service)
    for n in range(14, 17):
        add_date(service.workspace, n)
        latest = service.scheduler.discover(latest)
    added = datasets(service) - seen
    assert sorted(len(load_snapshot(p)["identity"]["captures"]) for p in added) == [1, 1, 1]
    assert len(latest.discovered) == len(set(latest.discovered)) == 17
    service.scheduler.save(latest)
    service.scheduler.validate()


def test_schedule_saved_before_incremental_discovery_still_verifies(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
) -> None:
    from entropytrade.features.registry import scientific_hash

    service, initial, _ = controlled
    created = service.scheduler.create(config(initial, follow_retained=True))
    path = service.scheduler.root / (created["config"]["id"] + ".json")
    value = json.loads(path.read_bytes())
    del value["schedule"]["discovered"]  # exact shape written by the previous release
    value["digest"] = scientific_hash(value["schedule"])
    path.write_text(json.dumps(value))
    legacy = current(service, created["config"]["id"])
    assert legacy.discovered == ()
    assert len(service.scheduler.discover(legacy).discovered) == 12
    summary = service.scheduler.catalog()[0]
    assert summary["discovered_inputs"] == 0
    assert "discovered" not in summary


def test_discovery_without_targets_advances_but_integrity_failures_still_raise(
    controlled: tuple[LabelService, dict[str, Any], SimulatedClock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from entropytrade.weather import history

    service, initial, _ = controlled
    created = service.scheduler.create(config(initial, follow_retained=True))
    schedule = current(service, created["config"]["id"])

    def empty(*_: object, **__: object) -> dict[str, Any]:
        raise ValueError("No verified weather target dates in retained receipts")

    monkeypatch.setattr(history, "build_snapshot", empty)
    advanced = service.scheduler.discover(schedule)
    assert len(advanced.discovered) == 12
    assert advanced.work == schedule.work
    assert advanced.status == "active"
    assert "no label targets" in advanced.detail

    def corrupt(*_: object, **__: object) -> dict[str, Any]:
        raise ValueError("weather snapshot checksum mismatch")

    monkeypatch.setattr(history, "build_snapshot", corrupt)
    with pytest.raises(ValueError, match="checksum mismatch"):
        service.scheduler.discover(schedule)
