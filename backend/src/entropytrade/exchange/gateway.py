"""Venue-neutral exchange gateway (spec sections 2A and 18).

Strategies, risk, backtests and research depend on this protocol, never on a venue SDK.
``KalshiGateway`` (Phase 1) is the first implementation and is the only place the Kalshi SDK
may be imported. SDK exceptions are translated into :class:`GatewayError` before they leave
the adapter.

Order submission is part of the protocol so later phases have one seam, but
:func:`require_order_submission` refuses it unless the mode is ``DEMO`` or ``LIVE``.
Phase 0 ships no implementation that can reach an exchange.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from entropytrade.domain.enums import KalshiEnvironment, MarketStatus, Venue
from entropytrade.domain.limits import ApiLimits, ExchangeStatus
from entropytrade.domain.market import Event, Market, Series
from entropytrade.domain.market_data import OrderBook, TradePrint
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.orders import Fill, Order, OrderRequest
from entropytrade.domain.portfolio import PortfolioSnapshot, Settlement


class GatewayError(Exception):
    """Failure of a gateway call. Adapters must not leak SDK exception types."""


class OrderSubmissionForbiddenError(GatewayError):
    """The trading mode does not permit sending orders."""

    def __init__(self, mode: TradingMode) -> None:
        super().__init__(f"trading mode {mode.value} cannot submit or cancel orders")
        self.mode = mode


def require_order_submission(mode: TradingMode) -> None:
    """Call at the start of every mutating gateway method."""
    if not mode.submits_orders_to_exchange:
        raise OrderSubmissionForbiddenError(mode)


@runtime_checkable
class ExchangeGateway(Protocol):
    """Read and, where the mode allows, trade one venue.

    Streaming (WebSocket) subscriptions are added in Phase 1 on this same protocol.
    Implementations must call :func:`require_order_submission` before ``submit_order`` and
    ``cancel_order``, and must reconcile after any submit whose outcome is uncertain.
    """

    @property
    def venue(self) -> Venue: ...

    @property
    def environment(self) -> KalshiEnvironment: ...

    @property
    def mode(self) -> TradingMode: ...

    async def get_exchange_status(self) -> ExchangeStatus: ...

    async def get_api_limits(self) -> ApiLimits: ...

    async def get_series(self, ticker: str) -> Series: ...

    async def get_event(self, event_ticker: str) -> Event: ...

    async def get_market(self, ticker: str) -> Market: ...

    async def list_markets(
        self,
        *,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        status: MarketStatus | None = None,
    ) -> tuple[Market, ...]: ...

    async def get_order_book(self, ticker: str) -> OrderBook: ...

    async def list_trades(
        self,
        ticker: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[TradePrint, ...]: ...

    async def get_portfolio(self) -> PortfolioSnapshot: ...

    async def list_orders(self) -> tuple[Order, ...]: ...

    async def list_fills(self, *, since: datetime | None = None) -> tuple[Fill, ...]: ...

    async def list_settlements(
        self, *, since: datetime | None = None
    ) -> tuple[Settlement, ...]: ...

    async def submit_order(self, request: OrderRequest) -> Order: ...

    async def cancel_order(self, client_order_id: UUID) -> Order: ...
