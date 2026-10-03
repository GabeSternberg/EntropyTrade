"""Range of the stored GFS ensemble. No socket.

The range is not a threshold and it is not aligned to the CLI decision clock.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.gfs_ensemble import load_gfs_ensemble

_BODY = Path("open-meteo/gfs-ensemble.json")
_MEMBERS = tuple(f"temperature_2m_member{index:02d}" for index in range(1, 31))
_SERIES = ("temperature_2m", *_MEMBERS)


@dataclass(frozen=True)
class ForecastDispersion:
    """One range per stored hour. ``traded`` and ``promoted`` stay false."""

    hours: tuple[str, ...]
    ranges: tuple[Decimal, ...]
    traded: bool
    promoted: bool


def load_forecast_dispersion(root: Path) -> ForecastDispersion:
    """Subtract the minimum from the maximum at each hour. None are dropped."""
    archive = load_gfs_ensemble(root)
    if archive.traded or archive.promoted:
        raise ValueError("the ensemble was traded")
    if archive.series != len(_SERIES) or archive.nulls != 0:
        raise ValueError("the ensemble series count changed")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    times = _times(hourly.get("time"))
    if times[0] != archive.first_time or times[-1] != archive.last_time:
        raise ValueError("the ensemble hours changed")
    if len(times) != archive.hours:
        raise ValueError("the ensemble hours changed")
    columns = tuple(_values(hourly.get(name), len(times), name) for name in _SERIES)
    ranges: list[Decimal] = []
    for index in range(len(times)):
        sample = tuple(column[index] for column in columns)
        if any(item is None for item in sample):
            raise ValueError("an ensemble hour is null")
        present = tuple(item for item in sample if item is not None)
        if len(present) != len(_SERIES):
            raise ValueError("an ensemble hour dropped a series")
        ranges.append(max(present) - min(present))
    return ForecastDispersion(
        hours=times,
        ranges=tuple(ranges),
        traded=False,
        promoted=False,
    )


def forecast_dispersion_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_forecast_dispersion(root)
    if found.traded or found.promoted:
        raise ValueError("the forecast-dispersion note must not trade")
    return " ".join(
        (
            "The Philadelphia forecast-dispersion record has",
            f"{len(found.ranges)} hourly ranges.",
            "Each range is the maximum minus the minimum of all 31 series.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("an ensemble hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int, label: str) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, label)
    if len(rows) != hours:
        raise ValueError("ensemble hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, label))
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


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
