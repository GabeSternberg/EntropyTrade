"""Coherent forward adapters. Initialization, product update and receipt are distinct clocks."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from entropytrade.data.schema import Location
from entropytrade.domain.base import DomainModel
from entropytrade.domain.ids import canonical_json, content_hash
from entropytrade.domain.time import UtcDatetime, ensure_utc


class ForecastPoint(DomainModel):
    valid_at: UtcDatetime
    value: Decimal
    unit: str = "degF"


class ForecastVintage(DomainModel):
    provider: str
    model: str
    location_id: str
    grid: str
    points: tuple[ForecastPoint, ...]
    issued_at: UtcDatetime | None = None
    published_at: UtcDatetime | None = None
    product_generated_at: UtcDatetime | None = None
    upstream_revision: str | None = None

    def identity(self) -> str:
        # Provider runtime/generation metadata is not a new forecast initialization.
        return content_hash(self.model_dump(exclude={"product_generated_at"}))


def _time(value: object) -> datetime | None:
    return ensure_utc(datetime.fromisoformat(value)) if isinstance(value, str) and value else None


def fahrenheit(value: object, unit: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("temperature must be a real measurement")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("temperature must be finite")
    if unit in {"F", "°F", "degF"}:
        return number
    if unit in {"C", "°C", "degC"}:
        return number * Decimal(9) / Decimal(5) + Decimal(32)
    raise ValueError("unsupported temperature unit")


def parse_forecast(body: bytes, *, provider: str, location: Location) -> ForecastVintage:
    payload: dict[str, Any] = json.loads(body, parse_float=Decimal)
    points: list[ForecastPoint] = []
    if provider == "open-meteo":
        if payload.get("utc_offset_seconds") != 0:
            raise ValueError("Open-Meteo adapter requires explicit UTC response")
        hourly = payload["hourly"]
        field = "temperature_2m"
        unit = payload["hourly_units"][field]
        for valid, value in zip(hourly["time"], hourly[field], strict=True):
            if value is not None:
                # The requested timezone is UTC; this is valid time, never issuance.
                at = datetime.fromisoformat(valid)
                if at.tzinfo is not None and at.utcoffset() != UTC.utcoffset(at):
                    raise ValueError("Open-Meteo valid times must use the requested UTC")
                at = at.replace(tzinfo=UTC)
                points.append(ForecastPoint(valid_at=at, value=fahrenheit(value, unit)))
        if len({p.valid_at for p in points}) != len(points):
            raise ValueError("duplicate forecast valid times")
        return ForecastVintage(
            provider=provider,
            model="gfs_seamless",
            location_id=location.station,
            grid=f"{payload['latitude']},{payload['longitude']}",
            points=tuple(points),
        )
    if provider == "nws":
        properties = payload["properties"]
        for period in properties["periods"]:
            if period.get("temperature") is not None:
                valid_time = _time(period["startTime"])
                if valid_time is None:
                    raise ValueError("NWS period lacks valid time")
                points.append(
                    ForecastPoint(
                        valid_at=valid_time,
                        value=fahrenheit(period["temperature"], period["temperatureUnit"]),
                    )
                )
        if len({p.valid_at for p in points}) != len(points):
            raise ValueError("duplicate forecast valid times")
        return ForecastVintage(
            provider=provider,
            model="nws-hourly",
            location_id=location.station,
            grid=canonical_json(payload.get("geometry", {})),
            points=tuple(points),
            published_at=_time(properties.get("updateTime")),
            product_generated_at=_time(properties.get("generatedAt")),
            upstream_revision=properties.get("updateTime"),
        )
    raise ValueError("unsupported forecast provider")
