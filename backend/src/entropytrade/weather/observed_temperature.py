"""Stored Philadelphia observed temperature. This module does not open a socket.

The body is one archive-API response for ``temperature_2m``. It is not a
trade and it does not add a threshold. It does not assign the revision
clock. A day outside the requested window is left missing.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

FIELD = "temperature_2m"
_BODY = Path("open-meteo/observed-temperature.json")
_MANIFEST = Path("open-meteo/observed-temperature.manifest.json")
_ISSUE_KEYS = frozenset(
    {"issue_time", "available_at", "run_time", "initialization_time", "model_run"}
)
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class ObservedTemperatureArchive:
    """One stored series. ``traded`` and ``promoted`` stay false."""

    http_status: int
    field: str
    hours: int
    nulls: int
    times: tuple[str, ...]
    values: tuple[Decimal | None, ...]
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
    has_issue_time: bool
    traded: bool
    promoted: bool


def load_observed_temperature(root: Path) -> ObservedTemperatureArchive:
    """Read the stored body. Coordinates and the field name are not rewritten."""
    manifest = _object(root / _MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith("https://archive-api.open-meteo.com/"):
        raise ValueError("the observed-temperature call is not the archive API")
    if "run=" in url:
        raise ValueError("the observed-temperature call used a rejected parameter")
    status = manifest.get("http_status")
    if status != 200:
        raise ValueError("the observed-temperature archive is not HTTP 200")
    field = _text(manifest.get("field"), "field")
    if field != FIELD or _query(url, "hourly") != FIELD:
        raise ValueError("the observed-temperature field was changed")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the observed-temperature archive was traded or promoted")
    if _query(url, "temperature_unit") != "fahrenheit":
        raise ValueError("the observed-temperature unit was changed")
    if _query(url, "timezone") != "UTC":
        raise ValueError("the observed-temperature timezone was changed")
    if _query(url, "start_date") != "2026-08-24" or _query(url, "end_date") != "2026-10-02":
        raise ValueError("the observed-temperature window was changed")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    units = _mapping(body.get("hourly_units"), "hourly_units")
    unit = _text(units.get(FIELD), "unit")
    times = _times(hourly.get("time"))
    values = _values(hourly.get(FIELD), len(times))
    if _issue_time(body):
        raise ValueError("the observed-temperature body has an issue time")
    _hourly(times)
    nulls = sum(1 for item in values if item is None)
    first = values[0]
    last = values[-1]
    if first is None or last is None:
        raise ValueError("the observed-temperature series has no endpoint value")
    return ObservedTemperatureArchive(
        http_status=200,
        field=field,
        hours=len(times),
        nulls=nulls,
        times=times,
        values=values,
        first_time=times[0],
        last_time=times[-1],
        first_value=first,
        last_value=last,
        unit=unit,
        requested_latitude=_query(url, "latitude"),
        requested_longitude=_query(url, "longitude"),
        response_latitude=_decimal(body.get("latitude"), "latitude"),
        response_longitude=_decimal(body.get("longitude"), "longitude"),
        timezone=_text(body.get("timezone"), "timezone"),
        has_issue_time=False,
        traded=False,
        promoted=False,
    )


def observed_temperature_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    archive = load_observed_temperature(root)
    if archive.traded or archive.promoted or archive.has_issue_time:
        raise ValueError("the observed-temperature note must not trade")
    return " ".join(
        (
            f"The Philadelphia observed-temperature archive stores {archive.hours} hours",
            f"of {archive.field}.",
            f"{archive.nulls} of those hours are null.",
            f"The first hour is {archive.first_time}.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _hourly(times: tuple[str, ...]) -> None:
    stamps = [datetime.fromisoformat(item).replace(tzinfo=UTC) for item in times]
    if any(stamps[index + 1] - stamps[index] != _HOUR for index in range(len(stamps) - 1)):
        raise ValueError("the observed-temperature hours are not consecutive")


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    if not rows:
        raise ValueError("the observed-temperature series is empty")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("an observed-temperature hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, FIELD)
    if len(rows) != hours:
        raise ValueError("observed-temperature hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, FIELD))
    return tuple(found)


def _issue_time(body: dict[str, object]) -> bool:
    keys = set(body)
    hourly = body.get("hourly")
    if isinstance(hourly, dict):
        keys.update(str(key) for key in hourly)
    return bool(keys & _ISSUE_KEYS)


def _query(url: str, key: str) -> str:
    if "?" not in url:
        raise ValueError("the observed-temperature url has no query")
    for part in url.split("?", 1)[1].split("&"):
        name, separator, value = part.partition("=")
        if separator != "=" or name == "" or value == "":
            raise ValueError("the observed-temperature query is incomplete")
        if name == key:
            return value
    raise ValueError(f"the observed-temperature url has no {key}")


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
