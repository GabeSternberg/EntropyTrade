"""Distinct NWS forecast-period temperatures. This module does not open a socket.

The hourly body is not used. A temperature counts when it is a number in
degrees Fahrenheit. A null is skipped and named. The count is not
compared to 0.40 and it is not a threshold. Nothing is traded.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_NULL = "null temperature"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose temperature was null."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsForecastTemperatures:
    """Distinct temperatures. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[Decimal, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_forecast_temperatures(root: Path) -> NwsForecastTemperatures:
    """Count the stored temperatures. A missing value is not invented."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    if forecast.temperature_unit != "F":
        raise ValueError("the NWS temperature unit was changed")
    found: list[Decimal] = []
    skipped: list[SkippedPeriod] = []
    for start, value in _periods(root / _FORECAST):
        if value is None:
            skipped.append(SkippedPeriod(start, _NULL))
            continue
        found.append(value)
    distinct = tuple(sorted(set(found)))
    return NwsForecastTemperatures(
        periods=len(found) + len(skipped),
        values=distinct,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_forecast_temperatures_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_temperatures(root)
    if found.traded or found.promoted or not found.values:
        raise ValueError("the NWS temperature note must not trade")
    smallest = format(found.values[0], "f")
    largest = format(found.values[-1], "f")
    return " ".join(
        (
            "The stored Philadelphia NWS forecast temperatures have",
            f"{len(found.values)} distinct values.",
            f"The smallest is {smallest} and the largest is {largest}.",
            f"{len(found.skipped)} temperatures were null and were not filled in.",
            "The hourly body was not used.",
            "The count was not compared to 0.40.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _periods(path: Path) -> tuple[tuple[str, Decimal | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, Decimal | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        if _text(period.get("temperatureUnit"), "temperatureUnit") != "F":
            raise ValueError("the NWS temperature unit was changed")
        raw = period.get("temperature")
        if raw is None:
            found.append((start, None))
            continue
        found.append((start, _decimal(raw, "temperature")))
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
