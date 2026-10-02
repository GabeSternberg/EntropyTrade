"""The gateway protocol refuses orders unless the mode may submit them."""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest

from entropytrade.domain.enums import KalshiEnvironment, MarketStatus, Venue
from entropytrade.domain.limits import ApiLimits, ExchangeStatus
from entropytrade.domain.market import Event, Market, Series
from entropytrade.domain.market_data import OrderBook, TradePrint
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.orders import Fill, Order, OrderRequest
from entropytrade.domain.portfolio import PortfolioSnapshot, Settlement
from entropytrade.exchange.gateway import (
    ExchangeGateway,
    OrderSubmissionForbiddenError,
    require_order_submission,
)
from tests.support import order_request


class FakeGateway:
    """In-memory stand-in used to prove the protocol is implementable without an SDK."""

    def __init__(self, mode: TradingMode) -> None:
        self._mode = mode

    @property
    def venue(self) -> Venue:
        return Venue.KALSHI

    @property
    def environment(self) -> KalshiEnvironment:
        return KalshiEnvironment.DEMO

    @property
    def mode(self) -> TradingMode:
        return self._mode

    async def get_exchange_status(self) -> ExchangeStatus:
        raise NotImplementedError

    async def get_api_limits(self) -> ApiLimits:
        raise NotImplementedError

    async def get_series(self, ticker: str) -> Series:
        raise NotImplementedError

    async def get_event(self, event_ticker: str) -> Event:
        raise NotImplementedError

    async def get_market(self, ticker: str) -> Market:
        raise NotImplementedError

    async def list_markets(
        self,
        *,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        status: MarketStatus | None = None,
    ) -> tuple[Market, ...]:
        raise NotImplementedError

    async def get_order_book(self, ticker: str) -> OrderBook:
        raise NotImplementedError

    async def list_trades(
        self,
        ticker: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[TradePrint, ...]:
        raise NotImplementedError

    async def get_portfolio(self) -> PortfolioSnapshot:
        raise NotImplementedError

    async def list_orders(self) -> tuple[Order, ...]:
        raise NotImplementedError

    async def list_fills(self, *, since: datetime | None = None) -> tuple[Fill, ...]:
        raise NotImplementedError

    async def list_settlements(self, *, since: datetime | None = None) -> tuple[Settlement, ...]:
        raise NotImplementedError

    async def submit_order(self, request: OrderRequest) -> Order:
        require_order_submission(self.mode)
        raise NotImplementedError(request.client_order_id)

    async def cancel_order(self, client_order_id: UUID) -> Order:
        require_order_submission(self.mode)
        raise NotImplementedError(client_order_id)


def test_fake_satisfies_the_protocol_and_read_only_cannot_submit() -> None:
    gateway: ExchangeGateway = FakeGateway(TradingMode.READ_ONLY)
    assert isinstance(gateway, ExchangeGateway)
    with pytest.raises(OrderSubmissionForbiddenError):
        asyncio.run(gateway.submit_order(order_request()))
    with pytest.raises(OrderSubmissionForbiddenError):
        asyncio.run(gateway.cancel_order(order_request().client_order_id))


@pytest.mark.parametrize("mode", [TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.SHADOW])
def test_non_submitting_modes_are_refused(mode: TradingMode) -> None:
    with pytest.raises(OrderSubmissionForbiddenError):
        require_order_submission(mode)


def test_demo_passes_the_guard_and_still_has_no_transport() -> None:
    gateway = FakeGateway(TradingMode.DEMO)
    with pytest.raises(NotImplementedError):
        asyncio.run(gateway.submit_order(order_request()))
