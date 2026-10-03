"""NWS hourly minus HRRR at equal UTC instants. This module does not open a socket.

An NWS period start is read with its offset and converted to UTC. The
difference is not aligned to the CLI decision clock. The NWS polygon is
not snapped to the HRRR grid. This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.ncep_hrrr import load_ncep_hrrr
from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_HRRR = Path("open-meteo/ncep-hrrr-conus.json")
_FIELD = "temperature_2m"
_OFF_HOUR = "does not land on a stored HRRR hour"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourGap:
    """One eligible hour. The difference is not a trading threshold."""

    start: str
    time: str
    nws: Decimal
    hrrr: Decimal
    difference: Decimal


@dataclass(frozen=True)
class SkippedHour:
    """A named NWS period that failed the written eligibility rule."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsHrrrGap:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourGap, ...]
    skipped: tuple[SkippedHour, ...]
    hrrr_latitude: Decimal
    hrrr_longitude: Decimal
    traded: bool
    promoted: bool


def load_nws_hrrr_gap(root: Path) -> NwsHrrrGap:
    """Apply the written rule to the two stored bodies."""
    hourly = load_nws_hourly(root)
    hrrr = load_ncep_hrrr(root)
    if hourly.traded or hourly.promoted or hrrr.traded or hrrr.promoted:
        raise ValueError("a stored forecast was traded")
    if hourly.temperature_unit != "F":
        raise ValueError("the NWS temperature unit was changed")
    periods = _periods(root / _HOURLY)
    hrrr_hours = _series(root / _HRRR)
    gaps: list[HourGap] = []
    skipped: list[SkippedHour] = []
    for start, nws_value in periods:
        stamp = _utc_hour(start)
        if stamp is None or stamp not in hrrr_hours:
            skipped.append(SkippedHour(start, _OFF_HOUR))
            continue
        hrrr_value = hrrr_hours[stamp]
        if nws_value is None or hrrr_value is None:
            skipped.append(SkippedHour(start, _NULL))
            continue
        gaps.append(
            HourGap(
                start=start,
                time=stamp,
                nws=nws_value,
                hrrr=hrrr_value,
                difference=nws_value - hrrr_value,
            )
        )
    return NwsHrrrGap(
        hours=tuple(gaps),
        skipped=tuple(skipped),
        hrrr_latitude=hrrr.response_latitude,
        hrrr_longitude=hrrr.response_longitude,
        traded=False,
        promoted=False,
    )


def nws_hrrr_gap_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hrrr_gap(root)
    if found.traded or found.promoted:
        raise ValueError("the model-gap note must not trade")
    return " ".join(
        (
            "The Philadelphia NWS-minus-HRRR record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The difference is the NWS temperature minus the HRRR temperature.",
            "An NWS period start is read with its offset and converted to UTC.",
            "The NWS polygon was not snapped to the HRRR grid.",
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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
