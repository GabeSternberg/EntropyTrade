"""Point-in-time observations, forecasts and features (spec sections 5 and 28).

Every piece of external information records when it happened (``event_time``), when its
publisher released it (``published_at``), when it could first have been known to us
(``available_at``) and when we stored it (``ingested_at``). The invariant
``published_at <= available_at <= ingested_at`` holds for live and backfilled data alike.

Research and backtests may only use a record at ``decision_time`` if
``available_at <= decision_time``. :func:`select_as_of` is the single primitive that applies
this rule; its output cannot change when records available after ``decision_time`` are added.
"""

from collections.abc import Callable, Hashable, Iterable
from datetime import datetime, timedelta
from typing import Self

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.ids import ContentHash
from entropytrade.domain.numeric import ExactDecimal
from entropytrade.domain.time import UtcDatetime, ensure_utc


class PointInTimeRecord(DomainModel):
    source_id: str = Field(min_length=1)
    revision_id: str | None = None
    event_time: UtcDatetime
    published_at: UtcDatetime | None = None
    available_at: UtcDatetime
    ingested_at: UtcDatetime
    revised_at: UtcDatetime | None = None
    raw_ref: str | None = None
    # raw_ref points back at the immutable raw record (file and offset, or a raw-layer key).

    @model_validator(mode="after")
    def _check_times(self) -> Self:
        if self.published_at is not None and self.published_at > self.available_at:
            raise ValueError("available_at cannot precede published_at")
        if self.available_at > self.ingested_at:
            raise ValueError("available_at cannot be later than ingested_at")
        return self

    def is_known_at(self, decision_time: datetime) -> bool:
        return self.available_at <= ensure_utc(decision_time)


class Forecast(PointInTimeRecord):
    """One forecast vintage. Newer runs are new records, never overwrites."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    run_time: UtcDatetime
    # Model initialisation / issue time of this vintage.
    location_id: str = Field(min_length=1)
    variable: str = Field(min_length=1)
    valid_from: UtcDatetime
    valid_to: UtcDatetime
    value: ExactDecimal
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_forecast(self) -> Self:
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to must not precede valid_from")
        if self.run_time > self.available_at:
            raise ValueError("a forecast cannot be available before its run time")
        return self

    @property
    def lead_time(self) -> timedelta:
        return self.valid_from - self.run_time


class FeatureObservation(PointInTimeRecord):
    feature_name: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    value: ExactDecimal | None = None
    input_manifest_hash: ContentHash | None = None


def _revision_order[T: PointInTimeRecord](record: T) -> tuple[datetime, datetime, str, str]:
    revised = record.revised_at or record.available_at
    return (record.available_at, revised, record.revision_id or "", record.model_dump_json())


def select_as_of[T: PointInTimeRecord, K: Hashable](
    records: Iterable[T],
    decision_time: datetime,
    key: Callable[[T], K],
) -> dict[K, T]:
    """Latest known record per ``key`` among those available at ``decision_time``.

    Ties are broken by ``(available_at, revised_at, revision_id)`` and finally by the record's
    serialised content, so the result is deterministic and independent of input order.
    """
    cutoff = ensure_utc(decision_time)
    latest: dict[K, T] = {}
    for record in records:
        if record.available_at > cutoff:
            continue
        k = key(record)
        current = latest.get(k)
        if current is None or _revision_order(record) > _revision_order(current):
            latest[k] = record
    return latest
