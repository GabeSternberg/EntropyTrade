"""Distinct NWS hourly dew points. This module does not open a socket.

The value is ``dewpoint.value`` when it is a number. A missing object
or a null is skipped and named. The unit is not converted. The count
is not compared to 0.40. Nothing is traded.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing dew point"
_NULL = "null dew point"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose dew point was missing or null."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsDewPoint:
    """Distinct dew points. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[Decimal, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_dew_point(root: Path) -> NwsDewPoint:
    """Count the stored dew points. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[Decimal] = []
    skipped: list[SkippedPeriod] = []
    for start, value, reason in _dew_point(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(start, reason))
            continue
        found.append(value)
    return NwsDewPoint(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_dew_point_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_dew_point(root)
    if found.traded or found.promoted:
        raise ValueError("the dew-point note must not trade")
    if found.values:
        span = (
            f"The smallest is {format(found.values[0], 'f')}"
            f" and the largest is {format(found.values[-1], 'f')}."
        )
    else:
        span = "No numeric dew point was stored."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly dew-point values have",
            f"{len(found.values)} distinct values.",
            span,
            f"{len(found.skipped)} values were missing or null and were not filled in.",
            "The unit was not converted.",
            "The count was not compared to 0.40.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _dew_point(path: Path) -> tuple[tuple[str, Decimal | None, str], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, Decimal | None, str]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        raw = period.get("dewpoint")
        if raw is None:
            found.append((start, None, _MISSING))
            continue
        dewpoint = _mapping(raw, "dewpoint")
        value = dewpoint.get("value")
        if value is None:
            found.append((start, None, _NULL))
            continue
        found.append((start, _decimal(value, "dewpoint"), ""))
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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
