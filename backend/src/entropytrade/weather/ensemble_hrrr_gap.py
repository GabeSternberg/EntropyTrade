"""Ensemble control minus HRRR from two stored series. This module does not open a socket.

The difference is not aligned to the CLI decision clock. Grid points are
not snapped together. This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.gfs_ensemble import load_gfs_ensemble
from entropytrade.weather.ncep_hrrr import load_ncep_hrrr

_ENSEMBLE = Path("open-meteo/gfs-ensemble.json")
_HRRR = Path("open-meteo/ncep-hrrr-conus.json")
_FIELD = "temperature_2m"
_MISSING_ENSEMBLE = "missing from the ensemble series"
_MISSING_HRRR = "missing from the HRRR series"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    time: str
    control: Decimal
    hrrr: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """An hour that failed the written eligibility rule."""

    time: str
    reason: str


@dataclass(frozen=True)
class EnsembleHrrrGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    ensemble_latitude: Decimal
    ensemble_longitude: Decimal
    hrrr_latitude: Decimal
    hrrr_longitude: Decimal
    traded: bool
    promoted: bool


def load_ensemble_hrrr_gap(root: Path) -> EnsembleHrrrGap:
    """Apply the written rule to the two stored bodies."""
    ensemble = load_gfs_ensemble(root)
    hrrr = load_ncep_hrrr(root)
    if ensemble.traded or ensemble.promoted or hrrr.traded or hrrr.promoted:
        raise ValueError("a stored forecast was traded")
    ensemble_hours = _series(root / _ENSEMBLE)
    hrrr_hours = _series(root / _HRRR)
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for stamp in sorted(set(ensemble_hours) | set(hrrr_hours)):
        if stamp not in ensemble_hours:
            skipped.append(SkippedHour(stamp, _MISSING_ENSEMBLE))
            continue
        if stamp not in hrrr_hours:
            skipped.append(SkippedHour(stamp, _MISSING_HRRR))
            continue
        control = ensemble_hours[stamp]
        hrrr_value = hrrr_hours[stamp]
        if control is None or hrrr_value is None:
            skipped.append(SkippedHour(stamp, _NULL))
            continue
        gaps.append(
            HourGap(
                time=stamp,
                control=control,
                hrrr=hrrr_value,
                difference=control - hrrr_value,
            )
        )
    return EnsembleHrrrGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        ensemble_latitude=ensemble.response_latitude,
        ensemble_longitude=ensemble.response_longitude,
        hrrr_latitude=hrrr.response_latitude,
        hrrr_longitude=hrrr.response_longitude,
        traded=False,
        promoted=False,
    )


def ensemble_hrrr_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_ensemble_hrrr_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    same_grid = (
        found.ensemble_latitude == found.hrrr_latitude
        and found.ensemble_longitude == found.hrrr_longitude
    )
    if same_grid:
        raise ValueError("the grid points were snapped together")
    return " ".join(
        (
            "The Philadelphia ensemble-control-minus-HRRR record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the ensemble control temperature minus the HRRR temperature.",
            "The grid points were not snapped together.",
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
