"""Count of stored NWS forecast coordinate positions.

This module does not open a socket. The hourly body is not used. A
position counts when it is a list of JSON numbers. A boolean is not a
number. A longitude and a latitude are not recorded. A position is not
snapped to a model grid. The count is not compared to 0.40 or to 2°F.
Nothing is traded.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_MISSING = "missing coordinates"


@dataclass(frozen=True)
class NwsForecastCoordinateCount:
    """Position and ring counts. ``traded`` and ``promoted`` stay false."""

    rings: int
    positions: int
    skipped: int
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_forecast_coordinate_count(root: Path) -> NwsForecastCoordinateCount:
    """Count positions. A coordinate number is not kept."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    rings, positions, skipped, reason = _counts(root / _FORECAST)
    return NwsForecastCoordinateCount(
        rings=rings,
        positions=positions,
        skipped=skipped,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_forecast_coordinate_count_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_coordinate_count(root)
    if found.traded or found.promoted:
        raise ValueError("the coordinate-count note must not trade")
    return " ".join(
        (
            "The stored Philadelphia NWS forecast coordinate positions are counted.",
            f"{found.rings} rings were stored.",
            f"{found.positions} positions were lists of numbers.",
            f"{found.skipped} positions were not lists of numbers.",
            "The hourly body was not used.",
            "A longitude was not recorded.",
            "A latitude was not recorded.",
            "The NWS polygon was not snapped to the HRRR/ECMWF/ensemble grid.",
            "The count was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _counts(path: Path) -> tuple[int, int, int, str | None]:
    body = _object(path)
    geometry = body.get("geometry")
    if not isinstance(geometry, dict):
        return 0, 0, 0, _MISSING
    raw = geometry.get("coordinates")
    if not isinstance(raw, list):
        return 0, 0, 0, _MISSING
    rings = 0
    positions = 0
    skipped = 0
    for ring in raw:
        if not isinstance(ring, list):
            skipped += 1
            continue
        rings += 1
        for position in ring:
            if _is_position(position):
                positions += 1
            else:
                skipped += 1
    return rings, positions, skipped, None


def _is_position(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return all(not isinstance(item, bool) and isinstance(item, Decimal | int) for item in value)


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
