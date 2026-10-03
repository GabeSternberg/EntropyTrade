"""Distinct NWS hourly wind-speed strings. This module does not open a socket.

A speed counts when it is a non-empty string. A missing or empty
speed is skipped and named. A string is not parsed into a number.
The count is not compared to 0.40. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing wind speed"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose speed was missing or empty."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsWindSpeed:
    """Distinct speed strings. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[str, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_wind_speed(root: Path) -> NwsWindSpeed:
    """Count the stored speed strings. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[str] = []
    skipped: list[SkippedPeriod] = []
    for start, value in _speeds(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(start, _MISSING))
            continue
        found.append(value)
    return NwsWindSpeed(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_wind_speed_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_wind_speed(root)
    if found.traded or found.promoted or not found.values:
        raise ValueError("the wind-speed note must not trade")
    listed = ", ".join(found.values)
    return " ".join(
        (
            "The stored Philadelphia NWS hourly wind-speed strings have",
            f"{len(found.values)} distinct values.",
            f"In alphabetical order they are {listed}.",
            f"{len(found.skipped)} speeds were missing and were not filled in.",
            "A string was not parsed into a number.",
            "The count was not compared to 0.40.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _speeds(path: Path) -> tuple[tuple[str, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, str | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        raw = period.get("windSpeed")
        if raw is None or raw == "":
            found.append((start, None))
            continue
        if not isinstance(raw, str):
            raise ValueError("a wind speed is not text")
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
