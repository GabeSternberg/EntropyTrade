"""One-shot public Philadelphia evidence, kept outside historical experiment coverage."""

import asyncio
import hashlib
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from entropytrade.data.schema import Location
from entropytrade.domain.time import utc_now
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.families.public import BoundedTransport
from entropytrade.weather.forecast import parse_forecast

PHILADELPHIA = Location(
    name="Philadelphia",
    series="KXHIGHPHIL",
    station="CLIPHL",
    timezone="America/New_York",
    latitude="39.87",
    longitude="-75.23",
)
MARKETS_URL = (
    "https://api.elections.kalshi.com/trade-api/v2/markets"
    "?series_ticker=KXHIGHPHIL&status=open&limit=24"
)
POINTS_URL = f"https://api.weather.gov/points/{PHILADELPHIA.latitude},{PHILADELPHIA.longitude}"
_NWS_GRID = re.compile(r"https://api\.weather\.gov/gridpoints/[A-Z]{3}/\d+,\d+/forecast/hourly")
_LOCAL = ZoneInfo(PHILADELPHIA.timezone)


async def fetch_course_sources(
    *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    """Fetch at most three anonymous GETs through the existing allowlisted transport."""
    async with httpx.AsyncClient(
        transport=BoundedTransport(transport),
        follow_redirects=False,
        headers={"User-Agent": "EntropyTrade research (github.com/GabeSternberg/EntropyTrade)"},
    ) as client:
        markets, weather = await asyncio.gather(_markets(client), _weather(client))
    market_dates = {m["target_date"] for m in markets["items"]}
    weather["market_dates_with_forecast"] = sorted(
        market_dates & {f["target_date"] for f in weather["items"] if f["hours_returned"] > 0}
    )
    weather["market_dates_with_full_forecast"] = sorted(
        market_dates
        & {f["target_date"] for f in weather["items"] if f["projected_hourly_max_f"] is not None}
    )
    return {"current_markets": markets, "weather": weather}


async def _read[T](
    client: httpx.AsyncClient,
    url: str,
    requests: list[dict[str, Any]],
    parse: Callable[[httpx.Response, datetime], T],
) -> T | None:
    started = time.monotonic()
    entry: dict[str, Any] = {"url": url, "method": "GET", "started_at": utc_now().isoformat()}
    requests.append(entry)
    try:
        async with asyncio.timeout(10):
            response = await client.get(url)
        received = utc_now()
        entry.update(
            http_status=response.status_code,
            received_at=received.isoformat(),
            response_sha256=hashlib.sha256(response.content).hexdigest(),
        )
        response.raise_for_status()
        result = parse(response, received)
    except (
        httpx.HTTPError,
        TimeoutError,
        KeyError,
        ValueError,
        TypeError,
        InvalidOperation,
    ) as exc:
        entry.update(status="failed", error=type(exc).__name__)
        return None
    else:
        entry["status"] = "returned"
        return result
    finally:
        entry.update(
            finished_at=utc_now().isoformat(), latency_ms=(time.monotonic() - started) * 1000
        )


def _project_markets(response: httpx.Response, received: datetime) -> dict[str, Any]:
    payload = response.json()
    rows = payload["markets"]
    if not isinstance(rows, list) or len(rows) > 24:
        raise ValueError("invalid bounded markets page")
    items = []
    skipped = 0
    for row in rows:
        try:
            market = market_from_body(row, captured_at=received, series=PHILADELPHIA.series)
        except (GatewayError, ValueError, TypeError):
            skipped += 1
            continue
        rules = market.rules
        day = rules.settlement_target_date
        if (
            not market.event_ticker.startswith(f"{PHILADELPHIA.series}-")
            or not market.ticker.startswith(f"{market.event_ticker}-")
            or not market.status.is_tradable
            or not market.open_time <= received < market.close_time
            or day is None
            or day < received.astimezone(_LOCAL).date()
            or rules.settlement_basis != "contract_text"
            or len(rules.rules_primary) + len(rules.rules_secondary) > 3000
        ):
            skipped += 1
            continue
        items.append(
            {
                "ticker": market.ticker,
                "event_ticker": market.event_ticker,
                "target_date": day.isoformat(),
                "close_time": market.close_time.isoformat(),
                "strike": market.strike.model_dump(mode="json") if market.strike else None,
                "rules": rules.model_dump(
                    mode="json",
                    exclude={"market_ticker"},
                ),
            }
        )
    # Limit the supplied text by prioritizing newer target dates in the returned page.
    items.sort(key=lambda row: (row["target_date"], row["ticker"]), reverse=True)
    return {
        "items": items[:4],
        "skipped_rows": skipped,
        "sampled_page_rows": len(rows),
        "truncated": bool(payload.get("cursor") or len(items) > 4),
    }


async def _markets(client: httpx.AsyncClient) -> dict[str, Any]:
    requests: list[dict[str, Any]] = []
    result = await _read(client, MARKETS_URL, requests, _project_markets)
    return {
        "source": "Kalshi public market listings and contract rules",
        "status": "available" if result and result["items"] else "unavailable",
        "requests": requests,
        **(result or {"items": []}),
    }


def _forecast_url(response: httpx.Response, _received: datetime) -> str:
    url = response.json()["properties"]["forecastHourly"]
    if not isinstance(url, str) or _NWS_GRID.fullmatch(url) is None:
        raise ValueError("NWS hourly URL outside allowlist")
    return url


def _project_weather(response: httpx.Response, received: datetime) -> dict[str, Any]:
    vintage = parse_forecast(response.content, provider="nws", location=PHILADELPHIA)
    clocks = (vintage.published_at, vintage.product_generated_at)
    if any(clock is not None and clock > received for clock in clocks):
        raise ValueError("NWS forecast carries a future publication or generation clock")
    today = received.astimezone(_LOCAL).date()
    items = []
    for offset in range(4):
        day = today + timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time(), _LOCAL).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), _LOCAL).astimezone(UTC)
        hours = (end - start) // timedelta(hours=1)
        expected = {start + timedelta(hours=h) for h in range(hours)}
        points = {p.valid_at: p.value for p in vintage.points if p.valid_at in expected}
        maximum = str(max(points.values())) if points else None
        items.append(
            {
                "target_date": day.isoformat(),
                "hours_returned": len(points),
                "hours_expected": len(expected),
                "first_valid_at": min(points).isoformat() if points else None,
                "last_valid_at": max(points).isoformat() if points else None,
                "max_in_returned_hours_f": maximum,
                "projected_hourly_max_f": maximum if points.keys() == expected else None,
            }
        )
    return {
        "items": items,
        "published_at": vintage.published_at.isoformat() if vintage.published_at else None,
        "product_generated_at": (
            vintage.product_generated_at.isoformat() if vintage.product_generated_at else None
        ),
    }


async def _weather(client: httpx.AsyncClient) -> dict[str, Any]:
    requests: list[dict[str, Any]] = []
    url = await _read(client, POINTS_URL, requests, _forecast_url)
    result = await _read(client, url, requests, _project_weather) if url else None
    return {
        "source": "NWS hourly forecast",
        "status": (
            "available"
            if result and any(f["hours_returned"] > 0 for f in result["items"])
            else "unavailable"
        ),
        "scope": "Philadelphia local-calendar-day hourly maxima are forecast proxies",
        "requests": requests,
        **(result or {"items": []}),
    }
