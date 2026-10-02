"""UTC-aware timestamps and injectable clocks.

Internally every timestamp is a timezone-aware ``datetime`` normalised to UTC. Naive datetimes
are rejected at every model boundary so they can never be compared against aware ones.
Code that needs "now" takes a :class:`Clock` so backtests can replay time deterministically.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol, runtime_checkable

from pydantic import AfterValidator


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` converted to UTC, rejecting naive datetimes."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime is not allowed; attach an explicit timezone")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]
"""Pydantic field type: timezone-aware datetime, normalised to UTC."""


def utc_now() -> datetime:
    """Wall-clock time in UTC. Prefer an injected :class:`Clock` in testable code."""
    return datetime.now(UTC)


@runtime_checkable
class Clock(Protocol):
    """Source of the current time."""

    def now(self) -> datetime:
        """Return the current time as a UTC-aware datetime."""
        ...


class SystemClock:
    """Wall-clock time. Never used by the backtester."""

    def now(self) -> datetime:
        return utc_now()


class SimulatedClock:
    """Deterministic clock for backtests and tests. Time can only move forward."""

    def __init__(self, start: datetime) -> None:
        self._now = ensure_utc(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            raise ValueError("a simulated clock cannot move backwards")
        self._now = self._now + delta
        return self._now

    def advance_to(self, moment: datetime) -> datetime:
        target = ensure_utc(moment)
        if target < self._now:
            raise ValueError("a simulated clock cannot move backwards")
        self._now = target
        return self._now
