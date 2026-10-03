"""Stored NWS forecast elevation.

This module does not open a socket. The hourly body is not used. A missing
value is skipped and named. A non-empty string is recorded as stored. An
object records an integer or JSON number as unrounded decimal text and a
unit code when it is a non-empty string. A boolean is not a number. The
number is not converted. A unit is not invented. The number is not
compared to 0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_MISSING = "missing elevation"
_UNIT = "missing elevation unit"
_VALUE = "missing elevation value"
_NUMBER = "elevation value is not a number"
_SHAPE = "elevation is not a string or object"


@dataclass(frozen=True)
class NwsForecastElevation:
    """The stored elevation. ``traded`` and ``promoted`` stay false."""

    text: str | None
    number: str | None
    unit: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_forecast_elevation(root: Path) -> NwsForecastElevation:
    """Read the stored elevation. A missing value is not invented."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    text, number, unit, reason = _elevation(root / _FORECAST)
    return NwsForecastElevation(
        text=text,
        number=number,
        unit=unit,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_forecast_elevation_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_elevation(root)
    if found.traded or found.promoted:
        raise ValueError("the elevation note must not trade")
    if found.text is not None:
        listed = f"The stored string is {found.text}."
    elif found.number is not None and found.unit is not None:
        listed = f"The stored number is {found.number} and the stored unit is {found.unit}."
    else:
        listed = "No elevation was stored."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast elevation is recorded.",
            listed,
            "The hourly body was not used.",
            "The number was not converted.",
            "A unit was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _elevation(path: Path) -> tuple[str | None, str | None, str | None, str | None]:
    body = _object(path)
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get("elevation")
    if raw is None or raw == "":
        return None, None, None, _MISSING
    if isinstance(raw, str):
        return raw, None, None, None
    if not isinstance(raw, dict):
        return None, None, None, _SHAPE
    item = _mapping(raw, "elevation")
    raw_value = item.get("value")
    if raw_value is None:
        return None, None, None, _VALUE
    number = _number(raw_value)
    if number is None:
        return None, None, None, _NUMBER
    unit = item.get("unitCode")
    if unit is None or unit == "" or not isinstance(unit, str):
        return None, number, None, _UNIT
    return None, number, unit, None


def _number(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        return None
    return format(Decimal(value), "f")


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
