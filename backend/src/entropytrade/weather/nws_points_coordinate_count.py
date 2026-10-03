"""Count of stored NWS points coordinate numbers.

This module does not open a socket. The forecast body and the hourly body
are not used. The geometry type was already recorded as Point. A position
counts when coordinates is a non-empty list of JSON numbers. A boolean is
not a number. A longitude and a latitude are not recorded. The point is
not snapped to a model grid. The count is not compared to 0.40 or to 2°F.
Nothing is traded.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_POINTS = Path("nws/points-39.87--75.23.json")
_MANIFEST = Path("nws/forecast.manifest.json")
_MISSING = "missing coordinates"


@dataclass(frozen=True)
class NwsPointsCoordinateCount:
    """One position count. ``traded`` and ``promoted`` stay false."""

    positions: int
    numbers: int
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_points_coordinate_count(root: Path) -> NwsPointsCoordinateCount:
    """Count numbers. A coordinate number is not kept."""
    _require_untraded(root / _MANIFEST)
    positions, numbers, reason = _counts(root / _POINTS)
    return NwsPointsCoordinateCount(
        positions=positions,
        numbers=numbers,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_points_coordinate_count_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_points_coordinate_count(root)
    if found.traded or found.promoted:
        raise ValueError("the points coordinate-count note must not trade")
    if found.positions == 1:
        listed = f"{found.numbers} numbers were stored in one position."
    else:
        listed = "No position was stored."
    return " ".join(
        (
            "The stored Philadelphia NWS points coordinate numbers are counted.",
            listed,
            "The forecast body was not used.",
            "The hourly body was not used.",
            "A longitude was not recorded.",
            "A latitude was not recorded.",
            "The point was not snapped to the HRRR/ECMWF/ensemble grid.",
            "The count was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _require_untraded(path: Path) -> None:
    manifest = _object(path)
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the NWS points archive was traded or promoted")


def _counts(path: Path) -> tuple[int, int, str | None]:
    body = _object(path)
    geometry = body.get("geometry")
    if not isinstance(geometry, dict):
        return 0, 0, _MISSING
    raw = geometry.get("coordinates")
    if not isinstance(raw, list) or not raw:
        return 0, 0, _MISSING
    if not all(not isinstance(item, bool) and isinstance(item, Decimal | int) for item in raw):
        return 0, 0, _MISSING
    return 1, len(raw), None


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
