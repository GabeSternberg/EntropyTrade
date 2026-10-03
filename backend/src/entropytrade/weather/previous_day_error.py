"""Previous-day temperature error from two stored series. No socket.

The error is the observed daily maximum minus the previous-day daily
maximum. Grid points are not snapped together. This module does not add a
threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.observed_temperature import load_observed_temperature

_PREVIOUS = Path("open-meteo/previous-runs.json")
_FIELD = "temperature_2m_previous_day1"
_MISSING_OBSERVED = "missing from the observed series"
_MISSING_PREVIOUS = "missing from the previous-day series"
_TIMESTAMPS = "timestamps differ"
_NULL = "an hour is null"


@dataclass(frozen=True)
class DayError:
    """One eligible date. The error is not a trading threshold."""

    day: str
    observed_max: Decimal
    previous_max: Decimal
    error: Decimal


@dataclass(frozen=True)
class SkippedDay:
    """A date that failed the written eligibility rule."""

    day: str
    reason: str


@dataclass(frozen=True)
class PreviousDayErrors:
    """Eligible days and named skips. ``traded`` and ``promoted`` stay false."""

    errors: tuple[DayError, ...]
    skipped: tuple[SkippedDay, ...]
    observed_latitude: Decimal
    observed_longitude: Decimal
    previous_latitude: Decimal
    previous_longitude: Decimal
    traded: bool
    promoted: bool


def load_previous_day_errors(root: Path) -> PreviousDayErrors:
    """Apply the written rule to the two stored bodies."""
    observed = load_observed_temperature(root)
    if observed.traded or observed.promoted:
        raise ValueError("the observed-temperature archive was traded")
    previous = _object(root / _PREVIOUS)
    hourly = _mapping(previous.get("hourly"), "hourly")
    times = _times(hourly.get("time"))
    values = _values(hourly.get(_FIELD), len(times))
    observed_days = _by_day(observed.times, observed.values)
    previous_days = _by_day(times, values)
    errors: list[DayError] = []
    skipped: list[SkippedDay] = []
    for day in sorted(set(observed_days) | set(previous_days)):
        if day not in observed_days:
            skipped.append(SkippedDay(day, _MISSING_OBSERVED))
            continue
        if day not in previous_days:
            skipped.append(SkippedDay(day, _MISSING_PREVIOUS))
            continue
        observed_hours = observed_days[day]
        previous_hours = previous_days[day]
        if set(observed_hours) != set(previous_hours):
            skipped.append(SkippedDay(day, _TIMESTAMPS))
            continue
        if _null(observed_hours) or _null(previous_hours):
            skipped.append(SkippedDay(day, _NULL))
            continue
        observed_max = _maximum(observed_hours)
        previous_max = _maximum(previous_hours)
        errors.append(
            DayError(
                day=day,
                observed_max=observed_max,
                previous_max=previous_max,
                error=observed_max - previous_max,
            )
        )
    return PreviousDayErrors(
        errors=tuple(errors),
        skipped=tuple(skipped),
        observed_latitude=observed.response_latitude,
        observed_longitude=observed.response_longitude,
        previous_latitude=_decimal(previous.get("latitude"), "latitude"),
        previous_longitude=_decimal(previous.get("longitude"), "longitude"),
        traded=False,
        promoted=False,
    )


def previous_day_error_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_previous_day_errors(root)
    if found.traded or found.promoted:
        raise ValueError("the previous-day error note must not trade")
    return " ".join(
        (
            "The Philadelphia previous-day error record has",
            f"{len(found.errors)} eligible days and {len(found.skipped)} skipped days.",
            "The error is the observed daily maximum minus the previous-day daily maximum.",
            "The grid points were not snapped together.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _by_day(
    times: tuple[str, ...], values: tuple[Decimal | None, ...]
) -> dict[str, dict[str, Decimal | None]]:
    found: dict[str, dict[str, Decimal | None]] = {}
    for stamp, value in zip(times, values, strict=True):
        hours = found.setdefault(stamp[:10], {})
        if stamp in hours:
            raise ValueError("a timestamp is repeated")
        hours[stamp] = value
    return found


def _null(hours: dict[str, Decimal | None]) -> bool:
    return any(item is None for item in hours.values())


def _maximum(hours: dict[str, Decimal | None]) -> Decimal:
    found: list[Decimal] = []
    for item in hours.values():
        if item is None:
            raise ValueError("a null hour has no maximum")
        found.append(item)
    return max(found)


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or len(item) < 10:
            raise ValueError("a previous-day hour is not text")
        found.append(item)
    if not found:
        raise ValueError("the previous-day series is empty")
    return tuple(found)


def _values(value: object, hours: int) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, _FIELD)
    if len(rows) != hours:
        raise ValueError("previous-day hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, _FIELD))
    return tuple(found)


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return _mapping(payload, path.name)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} has a non-string key")
        mapped[key] = item
    return mapped


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not a list")
    return tuple(value)


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
