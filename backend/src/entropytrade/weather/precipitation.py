"""Stored Philadelphia precipitation. This module does not open a socket.

The body is one previous-runs response for ``precipitation_previous_day1``.
It is not a trade and it does not add a threshold. It does not assign the
revision clock. A missing earlier day is left missing.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

FIELD = "precipitation_previous_day1"
_BODY = Path("open-meteo/precipitation-previous-day1.json")
_MANIFEST = Path("open-meteo/precipitation-previous-day1.manifest.json")
_ISSUE_KEYS = frozenset(
    {"issue_time", "available_at", "run_time", "initialization_time", "model_run"}
)
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class PrecipitationArchive:
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


def load_precipitation(root: Path) -> PrecipitationArchive:
    """Read the stored body. Coordinates and the field name are not rewritten."""
    manifest = _object(root / _MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith("https://previous-runs-api.open-meteo.com/"):
        raise ValueError("the precipitation call is not previous-runs")
    if "run=" in url or "start_date=" in url:
        raise ValueError("the precipitation call used a rejected parameter")
    status = manifest.get("http_status")
    if status != 200:
        raise ValueError("the precipitation archive is not HTTP 200")
    field = _text(manifest.get("field"), "field")
    if field != FIELD or _query(url, "hourly") != FIELD:
        raise ValueError("the precipitation field was changed")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the precipitation archive was traded or promoted")
    if _query(url, "temperature_unit") != "fahrenheit":
        raise ValueError("the precipitation unit was changed")
    if _query(url, "timezone") != "UTC":
        raise ValueError("the precipitation timezone was changed")
    if _query(url, "precipitation_unit") != "inch":
        raise ValueError("the precipitation unit was changed")
    if _query(url, "past_days") != "40" or _query(url, "forecast_days") != "0":
        raise ValueError("the precipitation window was changed")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    units = _mapping(body.get("hourly_units"), "hourly_units")
    unit = _text(units.get(FIELD), "unit")
    times = _times(hourly.get("time"))
    values = _values(hourly.get(FIELD), len(times))
    if _issue_time(body):
        raise ValueError("the precipitation body has an issue time")
    _hourly(times)
    nulls = sum(1 for item in values if item is None)
    first = values[0]
    last = values[-1]
    if first is None or last is None:
        raise ValueError("the precipitation series has no endpoint value")
    return PrecipitationArchive(
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


def precipitation_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    archive = load_precipitation(root)
    if archive.traded or archive.promoted or archive.has_issue_time:
        raise ValueError("the precipitation note must not trade")
    return " ".join(
        (
            f"The Philadelphia precipitation archive stores {archive.hours} hours",
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
        raise ValueError("the precipitation hours are not consecutive")


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    if not rows:
        raise ValueError("the precipitation series is empty")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("a precipitation hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, FIELD)
    if len(rows) != hours:
        raise ValueError("precipitation hours and values differ")
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
        raise ValueError("the precipitation url has no query")
    for part in url.split("?", 1)[1].split("&"):
        name, separator, value = part.partition("=")
        if separator != "=" or name == "" or value == "":
            raise ValueError("the precipitation query is incomplete")
        if name == key:
            return value
    raise ValueError(f"the precipitation url has no {key}")


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
