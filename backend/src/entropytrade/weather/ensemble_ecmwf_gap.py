"""Ensemble control minus ECMWF from two stored series. This module does not open a socket.

The difference is not aligned to the CLI decision clock. Grid points are
not snapped together. This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.ecmwf_ifs import load_ecmwf_ifs
from entropytrade.weather.gfs_ensemble import load_gfs_ensemble

_ENSEMBLE = Path("open-meteo/gfs-ensemble.json")
_ECMWF = Path("open-meteo/ecmwf-ifs.json")
_FIELD = "temperature_2m"
_MISSING_ENSEMBLE = "missing from the ensemble series"
_MISSING_ECMWF = "missing from the ECMWF series"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    time: str
    control: Decimal
    ecmwf: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """An hour that failed the written eligibility rule."""

    time: str
    reason: str


@dataclass(frozen=True)
class EnsembleEcmwfGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    ensemble_latitude: Decimal
    ensemble_longitude: Decimal
    ecmwf_latitude: Decimal
    ecmwf_longitude: Decimal
    traded: bool
    promoted: bool


def load_ensemble_ecmwf_gap(root: Path) -> EnsembleEcmwfGap:
    """Apply the written rule to the two stored bodies."""
    ensemble = load_gfs_ensemble(root)
    ecmwf = load_ecmwf_ifs(root)
    if ensemble.traded or ensemble.promoted or ecmwf.traded or ecmwf.promoted:
        raise ValueError("a stored forecast was traded")
    ensemble_hours = _series(root / _ENSEMBLE)
    ecmwf_hours = _series(root / _ECMWF)
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for stamp in sorted(set(ensemble_hours) | set(ecmwf_hours)):
        if stamp not in ensemble_hours:
            skipped.append(SkippedHour(stamp, _MISSING_ENSEMBLE))
            continue
        if stamp not in ecmwf_hours:
            skipped.append(SkippedHour(stamp, _MISSING_ECMWF))
            continue
        control = ensemble_hours[stamp]
        ecmwf_value = ecmwf_hours[stamp]
        if control is None or ecmwf_value is None:
            skipped.append(SkippedHour(stamp, _NULL))
            continue
        gaps.append(
            HourGap(
                time=stamp,
                control=control,
                ecmwf=ecmwf_value,
                difference=control - ecmwf_value,
            )
        )
    return EnsembleEcmwfGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        ensemble_latitude=ensemble.response_latitude,
        ensemble_longitude=ensemble.response_longitude,
        ecmwf_latitude=ecmwf.response_latitude,
        ecmwf_longitude=ecmwf.response_longitude,
        traded=False,
        promoted=False,
    )


def ensemble_ecmwf_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_ensemble_ecmwf_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    same_grid = (
        found.ensemble_latitude == found.ecmwf_latitude
        and found.ensemble_longitude == found.ecmwf_longitude
    )
    if same_grid:
        raise ValueError("the grid points were snapped together")
    return " ".join(
        (
            "The Philadelphia ensemble-control-minus-ECMWF record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the ensemble control temperature minus the ECMWF temperature.",
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
