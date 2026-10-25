"""Credential-free scheduled weather capture with bounded retries and disk budget."""

import asyncio
import json
from collections.abc import Callable
from typing import Literal

import httpx
from pydantic import Field

from entropytrade.collector.service import check_space
from entropytrade.data.schema import Location
from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import utc_now
from entropytrade.storage.forecast_archive import ForecastArchive


class WeatherConfig(DomainModel):
    locations: tuple[Location, ...] = Field(min_length=1)
    providers: tuple[Literal["open-meteo", "nws"], ...] = Field(
        default=("open-meteo", "nws"), min_length=1
    )
    interval_seconds: int = Field(default=900, ge=30)
    attempts: int = Field(default=3, ge=1, le=5)
    max_bytes: int = Field(default=5_000_000_000, ge=100_000)


async def poll_weather(
    *,
    config: WeatherConfig,
    archive: ForecastArchive,
    stop: asyncio.Event,
    once: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
    emit: Callable[[str], None],
) -> None:
    async with httpx.AsyncClient(
        transport=transport,
        timeout=30,
        headers={
            "User-Agent": "EntropyTrade private research (github.com/GabeSternberg/EntropyTrade)"
        },
    ) as client:
        while not stop.is_set():
            for location in config.locations:
                if location.latitude is None or location.longitude is None:
                    raise ValueError("weather capture requires configured coordinates")
                for provider in config.providers:
                    if stop.is_set():
                        break
                    url = (
                        "https://api.open-meteo.com/v1/forecast?latitude="
                        + location.latitude
                        + "&longitude="
                        + location.longitude
                        + "&hourly=temperature_2m"
                        "&temperature_unit=fahrenheit&timezone=UTC&forecast_days=7&models=gfs_seamless"
                    )
                    if provider == "nws":
                        url = f"https://api.weather.gov/points/{location.latitude},{location.longitude}"
                        point = await _get(client, url, config, archive)
                        if point is None:
                            continue
                        try:
                            payload = json.loads(point)
                            url = str(payload["properties"]["forecastHourly"])
                            if not url.startswith("https://api.weather.gov/gridpoints/"):
                                raise ValueError("NWS points left the approved provider host")
                        except (ValueError, KeyError, TypeError):
                            archive.save_health(json.dumps({"nws_points_invalid": True}), utc_now())
                            emit(json.dumps({"provider": provider, "captured": False}))
                            continue
                    elif provider != "open-meteo":
                        raise ValueError("unsupported weather provider")
                    response = await _get(
                        client, url, config, archive, provider=provider, location=location
                    )
                    emit(
                        json.dumps(
                            {
                                "provider": provider,
                                "location": location.station,
                                "captured": response is not None,
                            },
                            sort_keys=True,
                        )
                    )
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=config.interval_seconds)
            except TimeoutError:
                continue


async def _get(
    client: httpx.AsyncClient,
    url: str,
    config: WeatherConfig,
    archive: ForecastArchive,
    *,
    provider: str | None = None,
    location: Location | None = None,
) -> bytes | None:
    for attempt in range(config.attempts):
        check_space(archive.path, config.max_bytes)
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            archive.save_health(
                json.dumps({"weather_transport_error": True, "url": url}), utc_now()
            )
        else:
            received = utc_now()
            if provider is not None and location is not None:
                identity = archive.capture(
                    body=response.content,
                    url=url,
                    status=response.status_code,
                    received_at=received,
                    provider=provider,
                    location=location,
                )
                if identity is not None:
                    return response.content
            else:
                archive.record_http(
                    path=url,
                    status=response.status_code,
                    body=response.content,
                    received_at=received,
                )
                if response.status_code == 200:
                    return response.content
            if response.status_code not in {429, 500, 502, 503, 504}:
                return None
        if attempt + 1 < config.attempts:
            await asyncio.sleep(min(30, 2**attempt))
    return None
