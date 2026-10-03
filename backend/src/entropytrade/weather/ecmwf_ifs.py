"""Stored ECMWF forecast for ``ecmwf_ifs``. This module does not open a socket.

The body is one forecast-API response. It is not aligned to the CLI decision
clock. It is not a threshold and it is not a trade. A second model is not read here.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

FIELD = "temperature_2m"
MODEL = "ecmwf_ifs"
_BODY = Path("open-meteo/ecmwf-ifs.json")
_MANIFEST = Path("open-meteo/ecmwf-ifs.manifest.json")
_HOST = "https://api.open-meteo.com/"
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class EcmwfIfsArchive:
    """One stored series. ``traded`` and ``promoted`` stay false."""

    http_status: int
    model: str
    hours: int
    nulls: int
    first_time: str
    last_time: str
    first_value: Decimal
    last_value: Decimal
    unit: str
    requested_latitude: str
    requested_longitude: str
    response_latitude: Decimal
    response_longitude: Decimal
    timezone: str
    traded: bool
    promoted: bool


def load_ecmwf_ifs(root: Path) -> EcmwfIfsArchive:
    """Read the stored body. A missing hour is not invented."""
    manifest = _object(root / _MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith(_HOST) or _query(url, "models") != MODEL:
        raise ValueError("the ECMWF model was changed")
    if _query(url, "forecast_days") != "1" or _query(url, "hourly") != FIELD:
        raise ValueError("the ECMWF window was changed")
    if _query(url, "temperature_unit") != "fahrenheit" or _query(url, "timezone") != "UTC":
        raise ValueError("the ECMWF unit was changed")
    if manifest.get("http_status") != 200 or manifest.get("model") != MODEL:
        raise ValueError("the ECMWF archive is not the stored call")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the ECMWF archive was traded or promoted")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    units = _mapping(body.get("hourly_units"), "hourly_units")
    if tuple(key for key in hourly if key != "time") != (FIELD,):
        raise ValueError("the ECMWF series were changed")
    times = _times(hourly.get("time"))
    values = _values(hourly.get(FIELD), len(times))
    _hourly(times)
    nulls = sum(1 for item in values if item is None)
    first = values[0]
    last = values[-1]
    if first is None or last is None:
        raise ValueError("the ECMWF series has no endpoint value")
    return EcmwfIfsArchive(
        http_status=200,
        model=MODEL,
        hours=len(times),
        nulls=nulls,
        first_time=times[0],
        last_time=times[-1],
        first_value=first,
        last_value=last,
        unit=_text(units.get(FIELD), "unit"),
        requested_latitude=_query(url, "latitude"),
        requested_longitude=_query(url, "longitude"),
        response_latitude=_decimal(body.get("latitude"), "latitude"),
        response_longitude=_decimal(body.get("longitude"), "longitude"),
        timezone=_text(body.get("timezone"), "timezone"),
        traded=False,
        promoted=False,
    )


def ecmwf_ifs_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_ecmwf_ifs(root)
    if found.traded or found.promoted or found.model != MODEL:
        raise ValueError("the ECMWF note must not trade")
    return " ".join(
        (
            "The Philadelphia ECMWF archive stores",
            f"{found.hours} hours of {FIELD} from {found.model}.",
            f"{found.nulls} of those hours are null.",
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
        raise ValueError("the ECMWF hours are not consecutive")


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    if not rows:
        raise ValueError("the ECMWF series is empty")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("an ECMWF hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, FIELD)
    if len(rows) != hours:
        raise ValueError("ECMWF hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, FIELD))
    return tuple(found)


def _query(url: str, key: str) -> str:
    if "?" not in url:
        raise ValueError("the ECMWF url has no query")
    for part in url.split("?", 1)[1].split("&"):
        name, separator, value = part.partition("=")
        if separator == "=" and name == key and value != "":
            return value
    raise ValueError(f"the ECMWF url has no {key}")


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
