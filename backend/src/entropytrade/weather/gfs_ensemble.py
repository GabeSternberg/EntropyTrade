"""Stored GFS ensemble. This module does not open a socket.

The body is one ensemble response for ``gfs_seamless``. It is not aligned
to the CLI decision clock. It is not a threshold and it is not a trade.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

_BODY = Path("open-meteo/gfs-ensemble.json")
_MANIFEST = Path("open-meteo/gfs-ensemble.manifest.json")
_HOST = "https://ensemble-api.open-meteo.com/"
_MEMBERS = tuple(f"temperature_2m_member{index:02d}" for index in range(1, 31))
_SERIES = ("temperature_2m", *_MEMBERS)
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class GfsEnsemble:
    """One stored ensemble. ``traded`` and ``promoted`` stay false."""

    http_status: int
    hours: int
    series: int
    nulls: int
    first_time: str
    last_time: str
    first_control: Decimal
    last_control: Decimal
    unit: str
    requested_latitude: str
    requested_longitude: str
    response_latitude: Decimal
    response_longitude: Decimal
    timezone: str
    traded: bool
    promoted: bool


def load_gfs_ensemble(root: Path) -> GfsEnsemble:
    """Read the stored body. A missing member is not invented."""
    manifest = _object(root / _MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith(_HOST):
        raise ValueError("the ensemble call is not the ensemble API")
    if "past_days=" in url or _query(url, "models") != "gfs_seamless":
        raise ValueError("the ensemble model was changed")
    if _query(url, "forecast_days") != "1" or _query(url, "hourly") != "temperature_2m":
        raise ValueError("the ensemble window was changed")
    if manifest.get("http_status") != 200:
        raise ValueError("the ensemble archive is not HTTP 200")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the ensemble archive was traded or promoted")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    units = _mapping(body.get("hourly_units"), "hourly_units")
    if tuple(key for key in hourly if key != "time") != _SERIES:
        raise ValueError("the ensemble series were changed")
    times = _times(hourly.get("time"))
    _hourly(times)
    nulls = 0
    control = _values(hourly.get("temperature_2m"), len(times), "temperature_2m")
    nulls += sum(1 for item in control if item is None)
    for name in _SERIES[1:]:
        values = _values(hourly.get(name), len(times), name)
        nulls += sum(1 for item in values if item is None)
    if control[0] is None or control[-1] is None:
        raise ValueError("the ensemble control has no endpoint value")
    return GfsEnsemble(
        http_status=200,
        hours=len(times),
        series=len(_SERIES),
        nulls=nulls,
        first_time=times[0],
        last_time=times[-1],
        first_control=control[0],
        last_control=control[-1],
        unit=_text(units.get("temperature_2m"), "unit"),
        requested_latitude=_query(url, "latitude"),
        requested_longitude=_query(url, "longitude"),
        response_latitude=_decimal(body.get("latitude"), "latitude"),
        response_longitude=_decimal(body.get("longitude"), "longitude"),
        timezone=_text(body.get("timezone"), "timezone"),
        traded=False,
        promoted=False,
    )


def gfs_ensemble_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_gfs_ensemble(root)
    if found.traded or found.promoted:
        raise ValueError("the ensemble note must not trade")
    return " ".join(
        (
            "The Philadelphia GFS ensemble archive stores",
            f"{found.hours} hours and {found.series} temperature series.",
            f"{found.nulls} values are null.",
            f"The first hour is {found.first_time}.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _hourly(times: tuple[str, ...]) -> None:
    stamps = [datetime.fromisoformat(item).replace(tzinfo=UTC) for item in times]
    if any(stamps[index + 1] - stamps[index] != _HOUR for index in range(len(stamps) - 1)):
        raise ValueError("the ensemble hours are not consecutive")


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    if not rows:
        raise ValueError("the ensemble series is empty")
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


def _query(url: str, key: str) -> str:
    if "?" not in url:
        raise ValueError("the ensemble url has no query")
    for part in url.split("?", 1)[1].split("&"):
        name, separator, value = part.partition("=")
        if separator != "=" or name == "" or value == "":
            raise ValueError("the ensemble query is incomplete")
        if name == key:
            return value
    raise ValueError(f"the ensemble url has no {key}")


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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value
