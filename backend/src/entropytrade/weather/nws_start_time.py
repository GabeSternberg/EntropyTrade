"""Distinct NWS hourly start times. This module does not open a socket.

A start time counts when it is a non-empty string. A missing or empty
string is skipped and named. A duration is not computed. A string is not
rewritten. The count is not compared to 0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing start time"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose start time was missing or empty."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsStartTime:
    """Distinct start times. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[str, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_start_time(root: Path) -> NwsStartTime:
    """Count the stored start times. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[str] = []
    skipped: list[SkippedPeriod] = []
    for label, value in _starts(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(label, _MISSING))
            continue
        found.append(value)
    return NwsStartTime(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_start_time_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_start_time(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the start-time note must not trade")
    if found.values:
        listed = f"In alphabetical order they are {', '.join(found.values)}."
    else:
        listed = "In alphabetical order there are no strings."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly start times have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} start times were missing and were not filled in.",
            "A duration was not computed.",
            "A string was not rewritten.",
            "The count was not compared to 0.40 or to 2°F.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _starts(path: Path) -> tuple[tuple[str, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, str | None]] = []
    for index, item in enumerate(periods, start=1):
        period = _mapping(item, "period")
        raw = period.get("startTime")
        if raw is None or raw == "":
            found.append((_label(period, index), None))
            continue
        if not isinstance(raw, str):
            raise ValueError("a start time is not text")
        found.append((raw, raw))
    return tuple(found)


def _label(period: dict[str, object], index: int) -> str:
    number = period.get("number")
    if isinstance(number, int) and not isinstance(number, bool):
        return f"period {number}"
    return f"period {index}"


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
