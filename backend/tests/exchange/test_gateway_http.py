"""KalshiGateway against a fake HTTP transport. No credentials and no socket."""

import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from entropytrade.domain.enums import FeeType, KalshiEnvironment, MarketStatus
from entropytrade.domain.historical import ApiOrigin
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.gateway import (
    ExchangeGateway,
    GatewayError,
    OrderSubmissionForbiddenError,
)
from entropytrade.exchange.kalshi.gateway import KalshiGateway, RateLimitedError
from tests.support import order_request, utc

TICKER = "KXHIGHPHIL-26OCT02-T89"


def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _market_body() -> dict[str, object]:
    stamp = "2026-10-02T12:00:00Z"
    return {
        "ticker": TICKER,
        "event_ticker": "KXHIGHPHIL-26OCT02",
        "market_type": "binary",
        "title": "Highest temperature in Philadelphia",
        "yes_sub_title": "90° or above",
        "no_sub_title": "89° or below",
        "status": "active",
        "yes_bid_dollars": "0.4200",
        "yes_ask_dollars": "0.4400",
        "no_bid_dollars": "0.5600",
        "no_ask_dollars": "0.5800",
        "last_price_dollars": "0.4300",
        "previous_yes_bid_dollars": "0.4100",
        "previous_yes_ask_dollars": "0.4300",
        "previous_price_dollars": "0.4200",
        "notional_value_dollars": "1.0000",
        "liquidity_dollars": "10.0000",
        "yes_bid_size_fp": "10.00",
        "yes_ask_size_fp": "8.00",
        "volume_fp": "100.00",
        "volume_24h_fp": "20.00",
        "open_interest_fp": "50.00",
        "created_time": stamp,
        "updated_time": stamp,
        "open_time": "2026-10-02T08:00:00Z",
        "close_time": "2026-10-03T04:00:00Z",
        "latest_expiration_time": "2026-10-03T05:00:00Z",
        "settlement_bounds_type": "default",
        "settlement_timer_seconds": 3600,
        "result": "",
        "can_close_early": False,
        "expiration_value": "",
        "rules_primary": (
            "If the highest temperature in Philadelphia is greater than 89°, "
            "according to The Weather Company at weather.com/kalshi, the market resolves to Yes."
        ),
        "rules_secondary": "",
        "strike_type": "greater",
        "floor_strike": "89",
        "price_level_structure": "linear_cent",
        "price_ranges": [{"start": "0.0000", "end": "1.0000", "step": "0.0100"}],
        "exchange_index": 0,
    }


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/exchange/status"):
        return httpx.Response(200, json={"exchange_active": True, "trading_active": False})
    if path.endswith("/account/endpoint_costs"):
        return httpx.Response(
            200,
            json={
                "default_cost": 10,
                "endpoint_costs": [{"method": "GET", "path": "/exchange/status", "cost": 15}],
            },
        )
    if path.endswith("/account/limits"):
        return httpx.Response(
            200,
            json={
                "usage_tier": "basic",
                "read": {"bucket_capacity": 20, "refill_rate": 10},
                "write": {"bucket_capacity": 10, "refill_rate": 5},
                "grants": [],
            },
        )
    if path.endswith("/historical/cutoff"):
        return httpx.Response(
            200,
            json={
                "market_settled_ts": "2026-08-02T00:00:00Z",
                "trades_created_ts": "2026-08-02T00:00:00Z",
                "orders_updated_ts": "2026-08-02T00:00:00Z",
            },
        )
    if path.endswith(f"/markets/{TICKER}/orderbook"):
        return httpx.Response(
            200,
            json={
                "orderbook_fp": {
                    "yes_dollars": [["0.4200", "10.00"]],
                    "no_dollars": [["0.5600", "4.00"]],
                }
            },
        )
    if path.endswith(f"/markets/{TICKER}"):
        return httpx.Response(200, json={"market": _market_body()})
    if path.endswith("/historical/markets"):
        body = _market_body()
        body["status"] = "finalized"
        body["result"] = "yes"
        body["settlement_value_dollars"] = "1.0000"
        body["settlement_ts"] = "2026-07-31T23:00:00Z"
        return httpx.Response(200, json={"markets": [body], "cursor": ""})
    if path.endswith("/markets"):
        return httpx.Response(200, json={"markets": [_market_body()], "cursor": ""})
    if path.endswith("/series/KXHIGHPHIL"):
        return httpx.Response(
            200,
            json={
                "series": {
                    "ticker": "KXHIGHPHIL",
                    "frequency": "daily",
                    "title": "Highest temperature in Philadelphia",
                    "category": "Climate and Weather",
                    "categories": ["Climate and Weather"],
                    "tags": [],
                    "settlement_sources": [
                        {"name": "The Weather Company", "url": "https://weather.com/kalshi"}
                    ],
                    "contract_url": "https://kalshi.com/contract",
                    "contract_terms_url": "https://kalshi.com/contract",
                    "fee_type": "quadratic",
                    "fee_multiplier": "1",
                    "additional_prohibitions": [],
                    "exchange_index": 0,
                }
            },
        )
    if path.endswith("/events/KXHIGHPHIL-26OCT02"):
        return httpx.Response(
            200,
            json={
                "event": {
                    "event_ticker": "KXHIGHPHIL-26OCT02",
                    "series_ticker": "KXHIGHPHIL",
                    "title": "Philadelphia high on Oct 2",
                    "sub_title": "",
                    "collateral_return_type": "none",
                    "mutually_exclusive": True,
                    "settlement_sources": [
                        {"name": "The Weather Company", "url": "https://weather.com/kalshi"}
                    ],
                    "exchange_index": 0,
                }
            },
        )
    if path.endswith("/markets/trades"):
        return httpx.Response(
            200,
            json={
                "trades": [
                    {
                        "trade_id": "trade-1",
                        "ticker": TICKER,
                        "count_fp": "2.00",
                        "yes_price_dollars": "0.4300",
                        "no_price_dollars": "0.5700",
                        "taker_side": "yes",
                        "created_time": "2026-10-02T15:00:00Z",
                        "taker_outcome_side": "yes",
                        "taker_book_side": "bid",
                        "is_block_trade": False,
                    }
                ],
                "cursor": "",
            },
        )
    if path.endswith("/limited"):
        return httpx.Response(429, json={"error": "too many requests"})
    return httpx.Response(404, json={"message": path})


def _gateway() -> KalshiGateway:
    clock = SimulatedClock(datetime(2026, 10, 2, 16, tzinfo=UTC))
    return KalshiGateway(
        environment=KalshiEnvironment.DEMO,
        key_id="read-scoped-test",
        private_key_pem=_pem(),
        clock=clock,
        transport=httpx.MockTransport(_handler),
        environ={},
    )


def test_read_only_market_book_and_cutoff_use_decimals() -> None:
    gateway = _gateway()

    async def run() -> None:
        assert isinstance(gateway, ExchangeGateway)
        assert gateway.mode is TradingMode.READ_ONLY
        assert gateway.max_retries == 0
        market = await gateway.get_market(TICKER)
        assert market.exchange_index == 0
        assert market.strike is not None
        assert market.strike.resolves_yes(Decimal(90))
        assert not market.strike.resolves_yes(Decimal(89))
        assert market.rules.settlement_sources[0].name == "The Weather Company"
        assert market.rules.settlement_basis == "contract_text"
        assert market.rules.settlement_target_date == date(2026, 10, 2)
        assert isinstance(market.rules.rules_hash, str)
        book = await gateway.get_order_book(TICKER)
        assert book.best_bid is not None
        assert book.best_bid.price == Decimal("0.4200")
        assert book.best_ask is not None
        assert book.best_ask.price == Decimal("0.4400")
        assert isinstance(book.best_bid.quantity, Decimal)
        series = await gateway.get_series("KXHIGHPHIL")
        assert series.fee_type is FeeType.QUADRATIC
        assert series.fee_multiplier == Decimal(1)
        assert series.exchange_index == 0
        event = await gateway.get_event("KXHIGHPHIL-26OCT02")
        assert event.mutually_exclusive
        assert event.exchange_index == 0
        listed = await gateway.list_markets(status=MarketStatus.ACTIVE, series_ticker="KXHIGHPHIL")
        assert listed[0].ticker == TICKER
        historical = await gateway.list_markets(
            origin=ApiOrigin.HISTORICAL,
            series_ticker="KXHIGHPHIL",
        )
        assert historical[0].status is MarketStatus.FINALIZED
        assert gateway.origin_of_last_call() is ApiOrigin.HISTORICAL
        cutoff = await gateway.get_historical_cutoff()
        assert cutoff.market_settled_ts == utc(2026, 8, 2)
        trades = await gateway.list_trades(TICKER)
        assert trades[0].quantity == Decimal("2.00")
        assert trades[0].yes_price == Decimal("0.4300")
        status = await gateway.get_exchange_status()
        assert status.trading_active is False
        limits = await gateway.get_api_limits()
        assert limits.usage_tier == "basic"
        assert limits.read.refill_per_second == 10
        with pytest.raises(OrderSubmissionForbiddenError):
            await gateway.submit_order(order_request())
        with pytest.raises(OrderSubmissionForbiddenError):
            await gateway.cancel_order(order_request().intent_id)
        with pytest.raises(GatewayError, match="Phase 2"):
            await gateway.get_portfolio()
        await gateway.aclose()

    asyncio.run(run())


def test_unknown_host_override_refuses_to_start() -> None:
    with pytest.raises(GatewayError, match="KALSHI_ALLOW_UNKNOWN_HOST"):
        KalshiGateway(
            environment=KalshiEnvironment.PRODUCTION,
            key_id="read-scoped-test",
            private_key_pem=_pem(),
            transport=httpx.MockTransport(_handler),
            environ={"KALSHI_ALLOW_UNKNOWN_HOST": "1"},
        )


def test_local_budget_blocks_once_the_bucket_is_empty() -> None:
    gateway = _gateway()

    async def run() -> None:
        await gateway.get_api_limits()
        await gateway.get_exchange_status()
        await gateway.get_exchange_status()
        with pytest.raises(RateLimitedError, match="budget"):
            await gateway.get_exchange_status()
        await gateway.aclose()

    asyncio.run(run())


def test_endpoint_cost_replaces_the_flat_read_price() -> None:
    gateway = _gateway()

    async def run() -> None:
        await gateway.get_api_limits()
        schedule = await gateway.get_endpoint_costs()
        assert schedule.default_cost == 10
        assert schedule.endpoints[0].cost == 15
        with pytest.raises(RateLimitedError, match="budget"):
            await gateway.get_exchange_status()
        await gateway.aclose()

    asyncio.run(run())


def test_http_429_is_one_attempt_and_keeps_the_body() -> None:
    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "too many requests"})

    gateway = KalshiGateway(
        environment=KalshiEnvironment.DEMO,
        key_id="read-scoped-test",
        private_key_pem=_pem(),
        clock=SimulatedClock(datetime(2026, 10, 2, tzinfo=UTC)),
        transport=httpx.MockTransport(limited),
        environ={},
    )

    async def run() -> None:
        with pytest.raises(RateLimitedError) as caught:
            await gateway.get_exchange_status()
        assert caught.value.retry_after is None
        assert gateway.http_calls == 1
        assert gateway.last_capture is not None
        assert json.loads(gateway.last_capture.body) == {"error": "too many requests"}
        await gateway.aclose()

    asyncio.run(run())
