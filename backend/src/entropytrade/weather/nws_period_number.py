"""Distinct NWS hourly period numbers. This module does not open a socket.

A number counts when it is an integer. A boolean is not an integer. A
missing value or a non-integer is skipped and named. A missing number is
not invented. The count is not compared to 0.40 or to 2°F. Nothing is
traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing number"
_OTHER = "number is not an integer"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose number was missing or not an integer."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsPeriodNumber:
    """Distinct period numbers. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[int, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_period_number(root: Path) -> NwsPeriodNumber:
    """Count the stored period numbers. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[int] = []
    skipped: list[SkippedPeriod] = []
    for start, value, reason in _numbers(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(start, reason or _MISSING))
            continue
        found.append(value)
    return NwsPeriodNumber(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_period_number_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_period_number(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the period-number note must not trade")
    if found.values:
        listed = (
            "In ascending order they are " + ", ".join(str(item) for item in found.values) + "."
        )
    else:
        listed = "In ascending order there are no integers."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly period numbers have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} numbers were missing and were not filled in.",
            "A missing number was not invented.",
            "The count was not compared to 0.40 or to 2°F.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _numbers(path: Path) -> tuple[tuple[str, int | None, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, int | None, str | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        raw = period.get("number")
        if raw is None:
            found.append((start, None, _MISSING))
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            found.append((start, None, _OTHER))
            continue
        found.append((start, raw, None))
    return tuple(found)


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
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
