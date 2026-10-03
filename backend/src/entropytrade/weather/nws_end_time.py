"""Distinct NWS hourly end times. This module does not open a socket.

An end time counts when it is a non-empty string. A missing or empty
string is skipped and named. A duration is not computed from startTime.
A string is not rewritten. The count is not compared to 0.40 or to 2°F.
Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing end time"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose end time was missing or empty."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsEndTime:
    """Distinct end times. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[str, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_end_time(root: Path) -> NwsEndTime:
    """Count the stored end times. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[str] = []
    skipped: list[SkippedPeriod] = []
    for start, value in _ends(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(start, _MISSING))
            continue
        found.append(value)
    return NwsEndTime(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_end_time_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_end_time(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the end-time note must not trade")
    if found.values:
        listed = f"In alphabetical order they are {', '.join(found.values)}."
    else:
        listed = "In alphabetical order there are no strings."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly end times have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} end times were missing and were not filled in.",
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


def _ends(path: Path) -> tuple[tuple[str, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, str | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        raw = period.get("endTime")
        if raw is None or raw == "":
            found.append((start, None))
            continue
        if not isinstance(raw, str):
            raise ValueError("an end time is not text")
        found.append((start, raw))
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
