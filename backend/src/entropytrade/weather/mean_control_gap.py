"""Ensemble mean minus ensemble control. This module does not open a socket.

The mean formula is the existing unrounded sum divided by 31. The difference
is not aligned to the CLI decision clock. The stored grid is not rewritten.
This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.forecast_mean import load_forecast_mean
from entropytrade.weather.gfs_ensemble import load_gfs_ensemble

_BODY = Path("open-meteo/gfs-ensemble.json")
_FIELD = "temperature_2m"
_MISSING_MEAN = "missing from the ensemble mean"
_MISSING_CONTROL = "missing from the ensemble control"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    time: str
    mean: Decimal
    control: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """An hour that failed the written eligibility rule."""

    time: str
    reason: str


@dataclass(frozen=True)
class MeanControlGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    latitude: Decimal
    longitude: Decimal
    traded: bool
    promoted: bool


def load_mean_control_gap(root: Path) -> MeanControlGap:
    """Apply the written rule to the stored mean and the stored control."""
    ensemble = load_gfs_ensemble(root)
    mean = load_forecast_mean(root)
    if ensemble.traded or ensemble.promoted or mean.traded or mean.promoted:
        raise ValueError("a stored forecast was traded")
    if len(mean.hours) != len(mean.means):
        raise ValueError("the ensemble mean dropped an hour")
    mean_hours = dict(zip(mean.hours, mean.means, strict=True))
    control_hours = _series(root / _BODY)
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for stamp in sorted(set(mean_hours) | set(control_hours)):
        if stamp not in mean_hours:
            skipped.append(SkippedHour(stamp, _MISSING_MEAN))
            continue
        if stamp not in control_hours:
            skipped.append(SkippedHour(stamp, _MISSING_CONTROL))
            continue
        mean_value = mean_hours[stamp]
        control = control_hours[stamp]
        if control is None:
            skipped.append(SkippedHour(stamp, _NULL))
            continue
        gaps.append(
            HourGap(
                time=stamp,
                mean=mean_value,
                control=control,
                difference=mean_value - control,
            )
        )
    return MeanControlGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        latitude=ensemble.response_latitude,
        longitude=ensemble.response_longitude,
        traded=False,
        promoted=False,
    )


def mean_control_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_mean_control_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    return " ".join(
        (
            "The Philadelphia ensemble-mean-minus-control record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the unrounded ensemble mean minus the control temperature.",
            "The mean still uses all 31 temperature series.",
            "The stored response grid was not rewritten.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _series(path: Path) -> dict[str, Decimal | None]:
    body = _object(path)
    hourly = _mapping(body.get("hourly"), "hourly")
    times = _times(hourly.get("time"))
    values = _values(hourly.get(_FIELD), len(times))
    return dict(zip(times, values, strict=True))


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("a forecast hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, _FIELD)
    if len(rows) != hours:
        raise ValueError("forecast hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, _FIELD))
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
