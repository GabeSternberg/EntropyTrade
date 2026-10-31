"""Opt-in, bounded forward-label backlog over immutable research and shadow evidence.

The worker plans durably before enqueueing. Recovery reconciles the same request ID;
completed receipts are never fetched again to repair a bookkeeping interruption.
"""

import json
from collections import Counter
from contextlib import suppress
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from entropytrade.api.jobs import identifier
from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import UtcDatetime, utc_now
from entropytrade.features.registry import scientific_hash
from entropytrade.weather.labels import LabelTarget

if TYPE_CHECKING:
    from entropytrade.weather.label_service import LabelService


class ScheduleConfig(DomainModel):
    id: str
    dataset_id: str
    enabled: Literal[True]
    interval_seconds: int = Field(default=21600, strict=True, ge=300, le=86400)
    batch_dates: int = Field(default=8, strict=True, ge=1, le=8)
    follow_retained: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def check(self) -> "ScheduleConfig":
        from entropytrade.weather.history import snapshot_id

        identifier(self.id)
        snapshot_id(self.dataset_id)
        return self


class DateWork(DomainModel):
    key: str
    dataset_id: str
    day: date
    targets: tuple[LabelTarget, ...] = Field(min_length=1, max_length=2048)
    status: Literal["pending", "retry", "verified", "refused"] = "pending"
    next_at: UtcDatetime
    attempts: int = Field(default=0, ge=0)
    failures: int = Field(default=0, ge=0)
    last_request: str | None = None
    last_batch: str | None = None
    detail: str = "Waiting for completed local day"

    @model_validator(mode="after")
    def check(self) -> "DateWork":
        if self.key != scientific_hash(
            [
                self.dataset_id,
                self.day.isoformat(),
                [t.model_dump(mode="json") for t in self.targets],
            ]
        ):
            raise ValueError("schedule date selection identity mismatch")
        if any(t.target_date != self.day for t in self.targets):
            raise ValueError("schedule date/target mismatch")
        return self


class Schedule(DomainModel):
    schema_version: Literal["weather-label-schedule-v1"] = "weather-label-schedule-v1"
    config: ScheduleConfig
    status: Literal["active", "paused", "blocked"] = "active"
    created_at: UtcDatetime
    updated_at: UtcDatetime
    next_discovery: UtcDatetime
    discovery_cursor: int = Field(default=0, ge=0)
    work: tuple[DateWork, ...] = Field(default=(), max_length=2048)
    sequence: int = Field(default=0, ge=0)
    inflight: str | None = None
    inflight_keys: tuple[str, ...] = Field(default=(), max_length=8)
    detail: str = "Explicitly enabled read-only forward validation"
    controls: tuple[dict[str, Any], ...] = Field(default=(), max_length=4096)

    @model_validator(mode="after")
    def check(self) -> "Schedule":
        keys = {w.key for w in self.work}
        if len(keys) != len(self.work) or not set(self.inflight_keys) <= keys:
            raise ValueError("duplicate or unknown schedule work")
        if sum(len(w.targets) for w in self.work) > 2048:
            raise ValueError("schedule exceeds 2048 target budget; operator partition required")
        if len(set(self.inflight_keys)) != len(self.inflight_keys):
            raise ValueError("duplicate schedule plan dates")
        if bool(self.inflight) != bool(self.inflight_keys):
            raise ValueError("incomplete schedule request plan")
        if self.inflight:
            identifier(self.inflight)
        return self


class LabelScheduler:
    def __init__(self, service: "LabelService") -> None:
        self.service = service
        self.root = service.root / "schedules"

    def get(self, schedule_id: str) -> Schedule:
        path = self.root / (identifier(schedule_id) + ".json")
        if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > 8_000_000:
            raise ValueError("unsafe weather label schedule")
        value = json.loads(path.read_bytes())
        schedule = Schedule.model_validate(value["schedule"])
        if (
            schedule.config.id != schedule_id
            or scientific_hash(value["schedule"]) != value["digest"]
        ):
            raise ValueError("weather label schedule digest/identity mismatch")
        return schedule

    def save(self, schedule: Schedule) -> Schedule:
        from entropytrade.weather.label_service import atomic

        value = schedule.model_dump(mode="json")
        atomic(
            self.root / (schedule.config.id + ".json"),
            {"schedule": value, "digest": scientific_hash(value)},
        )
        return schedule

    def catalog(self) -> list[dict[str, Any]]:
        with self.service.lock:
            if self.root.is_symlink():
                raise ValueError("schedule directory cannot be a symlink")
            return [self.summary(self.get(p.stem)) for p in sorted(self.root.glob("*.json"))]

    def validate(self) -> None:
        """Offline provenance validation; never enqueue, discover or change clocks."""
        selections: dict[str, dict[str, Any]] = {}
        for row in self.catalog():
            schedule = self.get(row["config"]["id"])
            for work in schedule.work:
                if work.dataset_id not in selections:
                    selections[work.dataset_id] = self.service.selection(work.dataset_id)
                allowed = {
                    scientific_hash({k: v for k, v in t.items() if k != "refusal"})
                    for t in selections[work.dataset_id]["targets"]
                }
                if any(
                    scientific_hash(t.model_dump(mode="json", exclude={"refusal"})) not in allowed
                    for t in work.targets
                ):
                    raise ValueError("schedule target differs from immutable source dataset")
                if work.last_request:
                    request = self.service.get(work.last_request)
                    if request["batch_version"] != work.last_batch or not work.last_batch:
                        raise ValueError("schedule completion batch evidence mismatch")
                    actual = {
                        scientific_hash({k: v for k, v in r["target"].items() if k != "refusal"})
                        for r in request["result"]["records"]
                    }
                    expected = {
                        scientific_hash(t.model_dump(mode="json", exclude={"refusal"}))
                        for t in work.targets
                    }
                    if (
                        request["selection"]["dataset_id"] != work.dataset_id
                        or not expected <= actual
                    ):
                        raise ValueError("schedule completion targets mismatch")
            if schedule.inflight:
                with suppress(FileNotFoundError):
                    request = self.service.get(schedule.inflight)
                    planned = [w for w in schedule.work if w.key in schedule.inflight_keys]
                    expected = {t.event_id for w in planned for t in w.targets}
                    if request["selection"]["dataset_id"] != planned[0].dataset_id or expected != {
                        t["event_id"] for t in request["selection"]["targets"]
                    }:
                        raise ValueError("schedule durable plan/request mismatch")

    @staticmethod
    def summary(schedule: Schedule) -> dict[str, Any]:
        return {
            **schedule.model_dump(mode="json"),
            "counts": dict(Counter(w.status for w in schedule.work)),
            "submission_enabled": False,
            "limitation": "Receipt-time labels only; insufficient-data and frozen model gates "
            "remain enforced.",
        }

    def enroll(self, schedule: Schedule, dataset_id: str) -> Schedule:
        selection = self.service.selection(dataset_id)
        known = {
            scientific_hash(t.model_dump(mode="json", exclude={"refusal"}))
            for w in schedule.work
            for t in w.targets
        }
        grouped: dict[date, list[LabelTarget]] = {}
        for value in selection["targets"]:
            target = LabelTarget.model_validate(value)
            if scientific_hash(target.model_dump(mode="json", exclude={"refusal"})) not in known:
                grouped.setdefault(target.target_date, []).append(target)
        work = list(schedule.work)
        for day, members in sorted(grouped.items()):
            selected = tuple(members)
            complete = max(
                datetime.combine(day + timedelta(days=1), datetime.min.time(), ZoneInfo(t.timezone))
                for t in selected
            )
            refused = all(t.refusal for t in selected)
            work.append(
                DateWork(
                    key=scientific_hash(
                        [dataset_id, day.isoformat(), [t.model_dump(mode="json") for t in selected]]
                    ),
                    dataset_id=dataset_id,
                    day=day,
                    targets=selected,
                    next_at=max(utc_now(), complete),
                    status="refused" if refused else "pending",
                    detail="; ".join(sorted({t.refusal for t in selected if t.refusal}))
                    if refused
                    else "Waiting for source receipt",
                )
            )
        return schedule.revalidated(work=tuple(work))

    def create(self, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("enabled") is not True:
            raise ValueError("explicit enabled=true opt-in required")
        config = ScheduleConfig.model_validate(value)
        with self.service.lock:
            path = self.root / (config.id + ".json")
            if path.exists():
                previous = self.get(config.id)
                if previous.config != config:
                    raise ValueError("schedule ID already belongs to another configuration")
                return self.summary(previous)
            if len(self.catalog()) >= 8:
                raise ValueError("eight schedule budget reached")
            now = utc_now()
            schedule = Schedule(
                config=config,
                created_at=now,
                updated_at=now,
                next_discovery=now,
                controls=({"action": "opt_in", "at": now.isoformat()},),
            )
            return self.summary(self.save(self.enroll(schedule, config.dataset_id)))

    def control(self, schedule_id: str, action: str) -> dict[str, Any]:
        if action not in {"pause", "resume"}:
            raise ValueError("unknown schedule control")
        with self.service.lock:
            schedule = self.get(schedule_id)
            status = "paused" if action == "pause" else "active"
            if schedule.status != status:
                now = utc_now()
                schedule = self.save(
                    schedule.revalidated(
                        status=status,
                        updated_at=now,
                        detail="Operator " + action,
                        controls=(*schedule.controls, {"action": action, "at": now.isoformat()}),
                    )
                )
            if action == "pause" and schedule.inflight:
                with suppress(FileNotFoundError):
                    self.service.cancel(schedule.inflight)
            return self.summary(schedule)

    def discover(self, schedule: Schedule) -> Schedule:
        """One bounded retained public/shadow partition per interval; never collect markets."""
        from entropytrade.api.jobs import Jobs
        from entropytrade.tracking.history import anchor, catalog, selected_inputs
        from entropytrade.weather.history import build_snapshot
        from entropytrade.weather.label_service import batches

        if not self.service.snapshot_lock.acquire(blocking=False):
            return schedule  # A user freeze owns the shared snapshot writer; retry later.
        try:
            jobs = Jobs(self.service.workspace)
            partitions = catalog(jobs)["partitions"]
            if not partitions:
                return schedule.revalidated(
                    next_discovery=utc_now() + timedelta(seconds=schedule.config.interval_seconds)
                )
            partition = partitions[schedule.discovery_cursor % len(partitions)]["partition_id"]
            captures, outcomes, protected = selected_inputs(jobs, partition, partition)
            snapshot = build_snapshot(
                jobs.root / "runs/weather-datasets",
                captures,
                outcome_roots=outcomes,
                protected_events=protected,
                frozen_anchor=anchor(jobs),
                scalar_batches=batches(jobs.root),
                selection={"partition_id": partition},
            )
            return self.enroll(schedule, snapshot["dataset_id"][7:]).revalidated(
                discovery_cursor=schedule.discovery_cursor + 1,
                next_discovery=utc_now() + timedelta(seconds=schedule.config.interval_seconds),
            )
        finally:
            self.service.snapshot_lock.release()

    def reconcile(self, schedule: Schedule) -> Schedule:
        if schedule.inflight is None:
            return schedule
        try:
            request = self.service.get(schedule.inflight)
        except FileNotFoundError:
            if schedule.status != "active":
                return schedule  # Keep the original unpublished plan through pause/block/restart.
            # Crash between plan publication and enqueue: reuse the same identity.
            chosen = [w for w in schedule.work if w.key in schedule.inflight_keys]
            current = self.service.selection(chosen[0].dataset_id)
            by_event = {t["event_id"]: t for t in current["targets"]}
            selected = []
            for work in chosen:
                for target in work.targets:
                    actual = by_event.get(target.event_id)
                    if actual is None or actual["rules_hashes"] != list(target.rules_hashes):
                        raise ValueError(
                            "scheduled contract rules changed; review selection"
                        ) from None
                    selected.append(actual)
            request = self.service.enqueue(schedule.inflight, {**current, "targets": selected})
        if request["status"] in {"queued", "running"}:
            return schedule
        now = utc_now()
        records = request["result"]["records"]
        work_items = []
        for work in schedule.work:
            if work.key not in schedule.inflight_keys:
                work_items.append(work)
                continue
            relevant = [r for r in records if r["target"]["target_date"] == work.day.isoformat()]
            verified = bool(relevant) and all(r["observation"] is not None for r in relevant)
            refused = bool(relevant) and all(r["target"]["refusal"] for r in relevant)
            failures = 0 if verified else work.failures + 1
            delay = (
                max(86400, schedule.config.interval_seconds)
                if verified
                else min(86400, schedule.config.interval_seconds * 2 ** min(failures - 1, 8))
            )
            work_items.append(
                work.revalidated(
                    status="verified" if verified else "refused" if refused else "retry",
                    failures=failures,
                    next_at=now + timedelta(seconds=delay),
                    last_request=request["id"],
                    last_batch=request["batch_version"],
                    detail="Official labels retained; revision check scheduled"
                    if verified
                    else "; ".join(sorted({r["refusal"] for r in relevant if r["refusal"]}))
                    or request["detail"],
                )
            )
        return schedule.revalidated(
            work=tuple(work_items),
            inflight=None,
            inflight_keys=(),
            updated_at=now,
            detail="Batch reconciled; original receipt clocks retained",
        )

    def advance(self, schedule: Schedule) -> Schedule:
        reconciled = self.reconcile(schedule)
        if reconciled != schedule:
            self.save(reconciled)
        schedule = reconciled
        if schedule.status != "active" or schedule.inflight:
            return schedule
        now = utc_now()
        if schedule.config.follow_retained and now >= schedule.next_discovery:
            schedule = self.save(self.discover(schedule))
        due = sorted(
            (w for w in schedule.work if w.status != "refused" and w.next_at <= now),
            key=lambda w: (w.next_at, w.attempts, w.day, w.key),
        )
        if not due:
            return schedule
        selected = [w for w in due if w.dataset_id == due[0].dataset_id][
            : schedule.config.batch_dates
        ]
        # Publish the plan before the request. A crash cannot mint a second batch ID.
        sequence = schedule.sequence + 1
        request_id = str(
            uuid5(NAMESPACE_URL, f"entropytrade-label:{schedule.config.id}:{sequence}")
        )
        keys = tuple(w.key for w in selected)
        schedule = self.save(
            schedule.revalidated(
                sequence=sequence,
                inflight=request_id,
                inflight_keys=keys,
                updated_at=now,
                work=tuple(
                    w.revalidated(attempts=w.attempts + 1) if w.key in keys else w
                    for w in schedule.work
                ),
                detail=f"Acquiring bounded batch of {len(keys)} dates",
            )
        )
        return self.save(self.reconcile(schedule))

    def tick(self) -> None:
        with self.service.lock:
            for row in self.catalog():
                schedule = self.get(row["config"]["id"])
                try:
                    self.advance(schedule)
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    # Preserve the latest plan, including any request already durably published.
                    current = self.get(schedule.config.id)
                    self.save(
                        current.revalidated(
                            status="blocked",
                            updated_at=utc_now(),
                            detail=type(exc).__name__ + ": " + str(exc),
                        )
                    )
