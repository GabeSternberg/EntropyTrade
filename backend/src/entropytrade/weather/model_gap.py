"""ECMWF minus HRRR from two stored series. This module does not open a socket.

The difference is not aligned to the CLI decision clock. Grid points are
not snapped together. This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.ecmwf_ifs import load_ecmwf_ifs
from entropytrade.weather.ncep_hrrr import load_ncep_hrrr

_ECMWF = Path("open-meteo/ecmwf-ifs.json")
_HRRR = Path("open-meteo/ncep-hrrr-conus.json")
_FIELD = "temperature_2m"
_MISSING_ECMWF = "missing from the ECMWF series"
_MISSING_HRRR = "missing from the HRRR series"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    time: str
    ecmwf: Decimal
    hrrr: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """An hour that failed the written eligibility rule."""

    time: str
    reason: str


@dataclass(frozen=True)
class ModelGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    ecmwf_latitude: Decimal
    ecmwf_longitude: Decimal
    hrrr_latitude: Decimal
    hrrr_longitude: Decimal
    traded: bool
    promoted: bool


def load_model_gap(root: Path) -> ModelGap:
    """Apply the written rule to the two stored bodies."""
    ecmwf = load_ecmwf_ifs(root)
    hrrr = load_ncep_hrrr(root)
    if ecmwf.traded or ecmwf.promoted or hrrr.traded or hrrr.promoted:
        raise ValueError("a stored forecast was traded")
    ecmwf_hours = _series(root / _ECMWF)
    hrrr_hours = _series(root / _HRRR)
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for stamp in sorted(set(ecmwf_hours) | set(hrrr_hours)):
        if stamp not in ecmwf_hours:
            skipped.append(SkippedHour(stamp, _MISSING_ECMWF))
            continue
        if stamp not in hrrr_hours:
            skipped.append(SkippedHour(stamp, _MISSING_HRRR))
            continue
        ecmwf_value = ecmwf_hours[stamp]
        hrrr_value = hrrr_hours[stamp]
        if ecmwf_value is None or hrrr_value is None:
            skipped.append(SkippedHour(stamp, _NULL))
            continue
        gaps.append(
            HourGap(
                time=stamp,
                ecmwf=ecmwf_value,
                hrrr=hrrr_value,
                difference=ecmwf_value - hrrr_value,
            )
        )
    return ModelGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        ecmwf_latitude=ecmwf.response_latitude,
        ecmwf_longitude=ecmwf.response_longitude,
        hrrr_latitude=hrrr.response_latitude,
        hrrr_longitude=hrrr.response_longitude,
        traded=False,
        promoted=False,
    )


def model_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_model_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    same_grid = (
        found.ecmwf_latitude == found.hrrr_latitude
        and found.ecmwf_longitude == found.hrrr_longitude
    )
    if same_grid:
        raise ValueError("the grid points were snapped together")
    return " ".join(
        (
            "The Philadelphia ECMWF-minus-HRRR record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the ECMWF temperature minus the HRRR temperature.",
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
