"""Distinct NWS forecast-period icon strings. This module does not open a socket.

The hourly body is not used. An icon counts when it is a non-empty string.
A missing or empty string is skipped and named. An icon is not fetched. A
string is not rewritten into another word. The count is not compared to
0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_MISSING = "missing icon"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose icon was missing or empty."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsForecastIcon:
    """Distinct icon strings. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[str, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_forecast_icon(root: Path) -> NwsForecastIcon:
    """Count the stored icon strings. A missing value is not invented."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    found: list[str] = []
    skipped: list[SkippedPeriod] = []
    for start, value in _icons(root / _FORECAST):
        if value is None:
            skipped.append(SkippedPeriod(start, _MISSING))
            continue
        found.append(value)
    return NwsForecastIcon(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_forecast_icon_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_icon(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the forecast icon note must not trade")
    if found.values:
        listed = f"In alphabetical order they are {', '.join(found.values)}."
    else:
        listed = "In alphabetical order there are no strings."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast period icon strings have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} icons were missing and were not filled in.",
            "The hourly body was not used.",
            "An icon was not fetched.",
            "A string was not rewritten into another word.",
            "The count was not compared to 0.40 or to 2°F.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _icons(path: Path) -> tuple[tuple[str, str | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, str | None]] = []
    for index, item in enumerate(periods, start=1):
        period = _mapping(item, "period")
        start = period.get("startTime")
        label = start if isinstance(start, str) and start != "" else f"period {index}"
        raw = period.get("icon")
        if raw is None or raw == "":
            found.append((label, None))
            continue
        if not isinstance(raw, str):
            raise ValueError("an icon is not text")
        found.append((label, raw))
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
