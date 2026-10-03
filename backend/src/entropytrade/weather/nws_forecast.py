"""Stored NWS points and forecast bodies. This module does not open a socket.

The forecast is the one URL named by the points body. It is not aligned to
the CLI decision clock. It is not a threshold and it is not a trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_POINTS = Path("nws/points-39.87--75.23.json")
_FORECAST = Path("nws/forecast-phi-48-75.json")
_MANIFEST = Path("nws/forecast.manifest.json")
_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_HOURLY_MANIFEST = Path("nws/hourly.manifest.json")
_POINTS_URL = "https://api.weather.gov/points/39.87,-75.23"
_HOST = "https://api.weather.gov/"


@dataclass(frozen=True)
class NwsForecast:
    """One stored forecast. ``traded`` and ``promoted`` stay false."""

    points_status: int
    forecast_status: int
    forecast_url: str
    grid_id: str
    grid_x: int
    grid_y: int
    periods: int
    first_start: str
    first_temperature: Decimal
    temperature_unit: str
    last_start: str
    traded: bool
    promoted: bool


def load_nws_forecast(root: Path) -> NwsForecast:
    """Read the stored bodies. A missing forecast is not invented."""
    manifest = _object(root / _MANIFEST)
    if manifest.get("points_url") != _POINTS_URL:
        raise ValueError("the NWS points url was changed")
    if manifest.get("points_status") != 200 or manifest.get("forecast_status") != 200:
        raise ValueError("the NWS archive is not HTTP 200")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the NWS archive was traded or promoted")
    forecast_url = _text(manifest.get("forecast_url"), "forecast_url")
    if not forecast_url.startswith(_HOST):
        raise ValueError("the NWS forecast url left the points host")
    points = _object(root / _POINTS)
    named = _text(_mapping(points.get("properties"), "properties").get("forecast"), "forecast")
    if named != forecast_url:
        raise ValueError("the stored forecast is not the points forecast")
    grid = _mapping(points.get("properties"), "properties")
    forecast = _object(root / _FORECAST)
    periods = _sequence(
        _mapping(forecast.get("properties"), "properties").get("periods"), "periods"
    )
    if not periods:
        raise ValueError("the NWS forecast has no periods")
    first = _mapping(periods[0], "period")
    last = _mapping(periods[-1], "period")
    return NwsForecast(
        points_status=200,
        forecast_status=200,
        forecast_url=forecast_url,
        grid_id=_text(grid.get("gridId"), "gridId"),
        grid_x=_int(grid.get("gridX"), "gridX"),
        grid_y=_int(grid.get("gridY"), "gridY"),
        periods=len(periods),
        first_start=_text(first.get("startTime"), "startTime"),
        first_temperature=_decimal(first.get("temperature"), "temperature"),
        temperature_unit=_text(first.get("temperatureUnit"), "temperatureUnit"),
        last_start=_text(last.get("startTime"), "startTime"),
        traded=False,
        promoted=False,
    )


@dataclass(frozen=True)
class NwsHourly:
    """The stored hourly body. ``traded`` and ``promoted`` stay false."""

    http_status: int
    url: str
    periods: int
    null_temperatures: int
    first_start: str
    first_temperature: Decimal
    temperature_unit: str
    last_start: str
    traded: bool
    promoted: bool


def load_nws_hourly(root: Path) -> NwsHourly:
    """Read the hourly body named by the stored points response."""
    manifest = _object(root / _HOURLY_MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith(_HOST):
        raise ValueError("the NWS hourly url left the points host")
    if manifest.get("http_status") != 200:
        raise ValueError("the NWS hourly archive is not HTTP 200")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the NWS hourly archive was traded or promoted")
    points = _object(root / _POINTS)
    named = _text(
        _mapping(points.get("properties"), "properties").get("forecastHourly"),
        "forecastHourly",
    )
    if named != url:
        raise ValueError("the stored hourly url is not the points url")
    forecast = _object(root / _HOURLY)
    periods = _sequence(
        _mapping(forecast.get("properties"), "properties").get("periods"),
        "periods",
    )
    if not periods:
        raise ValueError("the NWS hourly forecast has no periods")
    first = _mapping(periods[0], "period")
    last = _mapping(periods[-1], "period")
    nulls = 0
    for item in periods:
        period = _mapping(item, "period")
        if period.get("temperature") is None:
            nulls += 1
    return NwsHourly(
        http_status=200,
        url=url,
        periods=len(periods),
        null_temperatures=nulls,
        first_start=_text(first.get("startTime"), "startTime"),
        first_temperature=_decimal(first.get("temperature"), "temperature"),
        temperature_unit=_text(first.get("temperatureUnit"), "temperatureUnit"),
        last_start=_text(last.get("startTime"), "startTime"),
        traded=False,
        promoted=False,
    )


def nws_hourly_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly(root)
    if found.traded or found.promoted:
        raise ValueError("the NWS hourly note must not trade")
    return " ".join(
        (
            "The Philadelphia NWS hourly archive stores",
            f"{found.periods} periods.",
            f"{found.null_temperatures} temperatures are null.",
            f"The first period starts at {found.first_start}.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def nws_forecast_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast(root)
    if found.traded or found.promoted:
        raise ValueError("the NWS note must not trade")
    return " ".join(
        (
            "The Philadelphia NWS archive stores the points response and one forecast.",
            f"The forecast has {found.periods} periods.",
            f"The first period starts at {found.first_start}.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


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


def _int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} is not an integer")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
