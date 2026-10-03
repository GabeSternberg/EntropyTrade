"""Stored NWS hourly units string.

This module does not open a socket. The 14-period forecast body is not
used. The value counts when it is a non-empty string. A missing or empty
string is skipped and named. Any other value is skipped and named. A unit
is not converted into another scale. The value is not compared to 0.40 or
to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing units"
_OTHER = "units is not a string"


@dataclass(frozen=True)
class NwsHourlyUnits:
    """The stored units string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_hourly_units(root: Path) -> NwsHourlyUnits:
    """Read the stored string. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    value, reason = _units(root / _HOURLY)
    return NwsHourlyUnits(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_hourly_units_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly_units(root)
    if found.traded or found.promoted:
        raise ValueError("the hourly units note must not trade")
    if found.value is None:
        listed = "No units string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly units string is recorded.",
            listed,
            "The 14-period forecast body was not used.",
            "A unit was not converted into another scale.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _units(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get("units")
    if raw is None or raw == "":
        return None, _MISSING
    if not isinstance(raw, str):
        return None, _OTHER
    return raw, None


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
