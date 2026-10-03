"""NWS hourly minus the unrounded ensemble mean. This module does not open a socket.

An NWS period start is read with its offset and converted to UTC. The mean
is the existing unrounded sum of all 31 series divided by 31. This module
does not replace that formula. The difference is not aligned to the CLI
decision clock. The NWS polygon is not snapped to the ensemble grid. This
module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.forecast_mean import load_forecast_mean
from entropytrade.weather.gfs_ensemble import load_gfs_ensemble
from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_OFF_HOUR = "does not land on a stored mean hour"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    start: str
    time: str
    nws: Decimal
    mean: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """A named NWS period that failed the written eligibility rule."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsMeanGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    latitude: Decimal
    longitude: Decimal
    traded: bool
    promoted: bool


def load_nws_mean_gap(root: Path) -> NwsMeanGap:
    """Apply the written rule to the stored NWS periods and the stored mean."""
    hourly = load_nws_hourly(root)
    ensemble = load_gfs_ensemble(root)
    mean = load_forecast_mean(root)
    if hourly.traded or hourly.promoted or ensemble.traded or ensemble.promoted:
        raise ValueError("a stored forecast was traded")
    if mean.traded or mean.promoted:
        raise ValueError("a stored forecast was traded")
    if hourly.temperature_unit != "F":
        raise ValueError("the NWS temperature unit was changed")
    if len(mean.hours) != len(mean.means):
        raise ValueError("the ensemble mean dropped an hour")
    periods = _periods(root / _HOURLY)
    mean_hours = dict(zip(mean.hours, mean.means, strict=True))
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for start, nws_value in periods:
        stamp = _utc_hour(start)
        if stamp is None or stamp not in mean_hours:
            skipped.append(SkippedHour(start, _OFF_HOUR))
            continue
        mean_value = mean_hours[stamp]
        if nws_value is None:
            skipped.append(SkippedHour(start, _NULL))
            continue
        gaps.append(
            HourGap(
                start=start,
                time=stamp,
                nws=nws_value,
                mean=mean_value,
                difference=nws_value - mean_value,
            )
        )
    return NwsMeanGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        latitude=ensemble.response_latitude,
        longitude=ensemble.response_longitude,
        traded=False,
        promoted=False,
    )


def nws_mean_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_mean_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    return " ".join(
        (
            "The Philadelphia NWS-minus-mean record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the NWS temperature minus the unrounded ensemble mean.",
            "The mean still uses all 31 temperature series.",
            "An NWS period start is read with its offset and converted to UTC.",
            "The NWS polygon was not snapped to the ensemble grid.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _utc_hour(start: str) -> str | None:
    stamp = datetime.fromisoformat(start)
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")


def _periods(path: Path) -> tuple[tuple[str, Decimal | None], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, Decimal | None]] = []
    for item in periods:
        period = _mapping(item, "period")
        start = _text(period.get("startTime"), "startTime")
        if _text(period.get("temperatureUnit"), "temperatureUnit") != "F":
            raise ValueError("the NWS temperature unit was changed")
        raw = period.get("temperature")
        if raw is None:
            found.append((start, None))
            continue
        found.append((start, _decimal(raw, "temperature")))
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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
