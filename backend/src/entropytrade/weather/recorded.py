"""Parse recorded weather bodies. These functions never open a socket.

A CLI daily high is the settlement-style label: the MAXIMUM line, not the
highest hourly temperature in the same text. ``available_at`` is an argument.
The product text does not say when we could have known it.
"""

import json
import re
from datetime import date, datetime

from entropytrade.domain.base import DomainModel
from entropytrade.domain.numeric import ExactDecimal, parse_exact_decimal
from entropytrade.domain.observations import Forecast
from entropytrade.domain.time import UtcDatetime, ensure_utc

_MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}
_FOR_DATE = re.compile(
    r"\bFOR\s+(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\s+(\d{4})\b",
    re.IGNORECASE,
)
_MAXIMUM = re.compile(r"(?m)^[ \t]*MAXIMUM\b[^\d\n-]*(-?\d+)")


class RecordedBodyError(ValueError):
    """The recorded text or JSON is not a daily high or a forecast vintage."""


class DailyHigh(DomainModel):
    """One station's daily high, available only after the observation day."""

    station: str
    valid_on: date
    high_f: ExactDecimal
    source_id: str
    available_at: UtcDatetime
    ingested_at: UtcDatetime


def parse_cli_daily_high(
    body: str,
    *,
    station: str,
    available_at: datetime,
    ingested_at: datetime | None = None,
) -> DailyHigh:
    """Read the first MAXIMUM line. Hourly temperatures in the same body are ignored."""
    if re.search(rf"\b{re.escape(station)}\b", body) is None:
        raise RecordedBodyError(f"CLI body does not name station {station}")
    found = _FOR_DATE.search(body)
    if found is None:
        raise RecordedBodyError("CLI body has no FOR <MONTH> <DAY> <YEAR> date")
    month = _MONTHS[found.group(1).upper()]
    valid_on = date(int(found.group(3)), month, int(found.group(2)))
    maximum = _MAXIMUM.search(body)
    if maximum is None:
        raise RecordedBodyError("CLI body has no MAXIMUM line; hourly temperatures are not a label")
    known = ensure_utc(available_at)
    if known.date() <= valid_on:
        raise RecordedBodyError("a CLI daily high is not available on the observation day")
    stored = known if ingested_at is None else ensure_utc(ingested_at)
    return DailyHigh(
        station=station,
        valid_on=valid_on,
        high_f=parse_exact_decimal(maximum.group(1)),
        source_id="nws-cli",
        available_at=known,
        ingested_at=stored,
    )


def parse_weather_company_high(
    body: str,
    *,
    available_at: datetime,
    ingested_at: datetime | None = None,
) -> DailyHigh:
    """Read a recorded Weather Company daily high. ``high_f`` must be a string, not a float."""
    payload = _object(
        body,
        required=("source", "station", "valid_on", "high_f"),
    )
    if payload["source"] != "weather_company":
        raise RecordedBodyError("source must be weather_company")
    valid_on = date.fromisoformat(_text(payload, "valid_on"))
    known = ensure_utc(available_at)
    if known.date() <= valid_on:
        raise RecordedBodyError("a daily high is not available on the observation day")
    stored = known if ingested_at is None else ensure_utc(ingested_at)
    return DailyHigh(
        station=_text(payload, "station"),
        valid_on=valid_on,
        high_f=parse_exact_decimal(_text(payload, "high_f")),
        source_id="weather-company",
        available_at=known,
        ingested_at=stored,
    )


def parse_recorded_forecast(body: str) -> Forecast:
    """Read one forecast vintage from a recorded JSON object. No network call."""
    payload = _object(
        body,
        required=(
            "provider",
            "model",
            "location_id",
            "variable",
            "run_time",
            "available_at",
            "valid_on",
            "value",
            "unit",
        ),
        optional=("ingested_at",),
    )
    run_time = ensure_utc(datetime.fromisoformat(_text(payload, "run_time")))
    available = ensure_utc(datetime.fromisoformat(_text(payload, "available_at")))
    ingested_text = payload.get("ingested_at")
    ingested = (
        available if ingested_text is None else ensure_utc(datetime.fromisoformat(ingested_text))
    )
    valid_on = date.fromisoformat(_text(payload, "valid_on"))
    start = datetime(valid_on.year, valid_on.month, valid_on.day, tzinfo=run_time.tzinfo)
    provider = _text(payload, "provider")
    return Forecast(
        source_id=provider,
        event_time=run_time,
        available_at=available,
        ingested_at=ingested,
        provider=provider,
        model=_text(payload, "model"),
        run_time=run_time,
        location_id=_text(payload, "location_id"),
        variable=_text(payload, "variable"),
        valid_from=start,
        valid_to=start.replace(hour=23, minute=59),
        value=parse_exact_decimal(_text(payload, "value")),
        unit=_text(payload, "unit"),
    )


def _object(
    body: str,
    *,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> dict[str, str]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RecordedBodyError("recorded body is not JSON") from exc
    if not isinstance(parsed, dict):
        raise RecordedBodyError("recorded body must be a JSON object")
    allowed = set(required) | set(optional)
    unexpected = set(parsed) - allowed
    if unexpected:
        raise RecordedBodyError(f"unexpected fields: {sorted(unexpected)}")
    missing = [key for key in required if key not in parsed]
    if missing:
        raise RecordedBodyError(f"missing fields: {missing}")
    return {key: _json_string(parsed[key], key) for key in parsed}


def _json_string(value: object, key: str) -> str:
    if isinstance(value, bool | float) or not isinstance(value, str) or not value.strip():
        raise RecordedBodyError(f"{key} must be a non-empty string")
    return value


def _text(payload: dict[str, str], key: str) -> str:
    return payload[key]
