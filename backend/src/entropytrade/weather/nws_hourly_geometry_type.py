"""Stored NWS hourly geometry type string.

This module does not open a socket. The 14-period forecast body is not
used. Coordinates are not read. The polygon is not snapped to a model
grid. The value counts when it is a non-empty string. A missing geometry
is skipped and named. A missing or empty type is skipped and named. Any
other value is skipped and named. The string is not rewritten into
another word. The string is not compared to 0.40 or to 2°F. Nothing is
traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing geometry"
_TYPE = "missing geometry type"
_OTHER = "geometry type is not a string"


@dataclass(frozen=True)
class NwsHourlyGeometryType:
    """The stored geometry type. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_hourly_geometry_type(root: Path) -> NwsHourlyGeometryType:
    """Read the stored string. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    value, reason = _geometry_type(root / _HOURLY)
    return NwsHourlyGeometryType(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_hourly_geometry_type_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly_geometry_type(root)
    if found.traded or found.promoted:
        raise ValueError("the hourly geometry-type note must not trade")
    if found.value is None:
        listed = "No geometry type string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly geometry type string is recorded.",
            listed,
            "The 14-period forecast body was not used.",
            "Coordinates were not read.",
            "The NWS polygon was not snapped to the HRRR/ECMWF/ensemble grid.",
            "The string was not rewritten into another word.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _geometry_type(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    raw = body.get("geometry")
    if raw is None:
        return None, _MISSING
    geometry = _mapping(raw, "geometry")
    kind = geometry.get("type")
    if kind is None or kind == "":
        return None, _TYPE
    if not isinstance(kind, str):
        return None, _OTHER
    return kind, None


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
        if key == "coordinates":
            continue
        mapped[key] = item
    return mapped
