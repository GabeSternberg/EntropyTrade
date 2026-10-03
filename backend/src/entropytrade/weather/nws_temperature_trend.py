"""Distinct NWS hourly temperature trends. This module does not open a socket.

A trend counts when it is a non-empty string. A missing or empty string
is skipped and named. A trend is not rewritten into another word. The
count is not compared to 0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing temperature trend"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose temperature trend was missing or empty."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsTemperatureTrend:
    """Distinct temperature trends. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[str, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_temperature_trend(root: Path) -> NwsTemperatureTrend:
    """Count the stored temperature trends. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    found: list[str] = []
    skipped: list[SkippedPeriod] = []
    for start, value in _trends(root / _HOURLY):
        if value is None:
            skipped.append(SkippedPeriod(start, _MISSING))
            continue
        found.append(value)
    return NwsTemperatureTrend(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_temperature_trend_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_temperature_trend(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the temperature-trend note must not trade")
    if found.values:
        listed = f"In alphabetical order they are {', '.join(found.values)}."
    else:
        listed = "In alphabetical order there are no strings."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly temperature trends have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} trends were missing and were not filled in.",
            "A trend was not rewritten into another word.",
            "The count was not compared to 0.40 or to 2°F.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _trends(path: Path) -> tuple[tuple[str, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, str | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        raw = period.get("temperatureTrend")
        if raw is None or raw == "":
            found.append((start, None))
            continue
        if not isinstance(raw, str):
            raise ValueError("a temperature trend is not text")
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
