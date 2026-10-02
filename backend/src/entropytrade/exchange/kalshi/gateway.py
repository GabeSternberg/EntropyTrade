"""Read-only Kalshi gateway. Order methods exist only to refuse.

The trading key is not accepted here. ``submit_order`` and ``cancel_order`` call
``require_order_submission`` and therefore raise while the mode is ``read_only``, which is
the only mode this class constructs. SDK exceptions are translated before they leave.
"""

from collections.abc import Awaitable, Callable, Coroutine, Mapping
from typing import TYPE_CHECKING, cast
from uuid import UUID

import httpx
from kalshi import AsyncKalshiClient
from kalshi.errors import KalshiError, KalshiRateLimitError
from pydantic import ValidationError

if TYPE_CHECKING:
    from kalshi.models.markets import MarketStatusLiteral

from entropytrade.domain.enums import KalshiEnvironment, MarketStatus, Venue
from entropytrade.domain.historical import ApiOrigin, HistoricalCutoff
from entropytrade.domain.limits import (
    ApiLimits,
    EndpointCost,
    EndpointCostSchedule,
    ExchangeStatus,
    TokenBucket,
)
from entropytrade.domain.market import Event, Market, Series
from entropytrade.domain.market_data import OrderBook, TradePrint
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.orders import Fill, Order, OrderRequest
from entropytrade.domain.portfolio import PortfolioSnapshot, Settlement
from entropytrade.domain.time import Clock, SystemClock, UtcDatetime
from entropytrade.exchange.budget import RateLimitExceededError, ReadBudget
from entropytrade.exchange.gateway import GatewayError, require_order_submission
from entropytrade.exchange.kalshi.config import kalshi_config_for, refuse_unknown_host_override
from entropytrade.exchange.kalshi.mapping import (
    cutoff_from_sdk,
    event_from_sdk,
    market_from_sdk,
    order_book_from_sdk,
    series_from_sdk,
    status_query,
    trade_from_sdk,
)
from entropytrade.exchange.kalshi.transport import ObservingTransport, RawCapture

_DEFAULT_READ_COST = 10


class RateLimitedError(GatewayError):
    """A read was refused. ``retry_after`` is unset when Kalshi omits the header."""

    def __init__(self, message: str, *, retry_after: str | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class KalshiGateway:
    """``ExchangeGateway`` for one Kalshi environment, reads only."""

    def __init__(
        self,
        *,
        environment: KalshiEnvironment,
        key_id: str,
        private_key_pem: str,
        clock: Clock | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        refuse_unknown_host_override(environ)
        self._environment = environment
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._config = kalshi_config_for(environment)
        inner = transport if transport is not None else httpx.AsyncHTTPTransport()
        self._observing = ObservingTransport(inner)
        self._client = AsyncKalshiClient(
            key_id=key_id,
            private_key=private_key_pem,
            config=self._config,
            transport=self._observing,
        )
        self._budget: ReadBudget | None = None
        self._default_cost = _DEFAULT_READ_COST

    @property
    def venue(self) -> Venue:
        return Venue.KALSHI

    @property
    def environment(self) -> KalshiEnvironment:
        return self._environment

    @property
    def mode(self) -> TradingMode:
        return TradingMode.READ_ONLY

    @property
    def max_retries(self) -> int:
        return self._config.max_retries

    @property
    def last_capture(self) -> RawCapture | None:
        return self._observing.last

    @property
    def http_calls(self) -> int:
        return self._observing.calls

    async def aclose(self) -> None:
        await self._client.close()

    async def get_exchange_status(self) -> ExchangeStatus:
        raw = await self._guard(self._client.exchange.status(), path="/exchange/status")
        return ExchangeStatus(trading_active=raw.trading_active, observed_at=self._now())

    async def get_api_limits(self) -> ApiLimits:
        raw = await self._guard(self._client.account.limits())
        limits = ApiLimits(
            usage_tier=raw.usage_tier,
            read=TokenBucket(
                refill_per_second=raw.read.refill_rate,
                capacity=raw.read.bucket_capacity,
            ),
            write=TokenBucket(
                refill_per_second=raw.write.refill_rate,
                capacity=raw.write.bucket_capacity,
            ),
            observed_at=self._now(),
        )
        self._budget = ReadBudget(limits.read, now=self._now())
        return limits

    async def get_endpoint_costs(self) -> EndpointCostSchedule:
        raw = await self._guard(
            self._client.account.endpoint_costs(),
            path="/account/endpoint_costs",
        )
        schedule = EndpointCostSchedule(
            default_cost=raw.default_cost,
            endpoints=tuple(
                EndpointCost(method=item.method, path=item.path, cost=item.cost)
                for item in raw.endpoint_costs
            ),
            observed_at=self._now(),
        )
        self._default_cost = schedule.default_cost
        if self._budget is not None:
            self._budget.use_schedule(schedule)
        return schedule

    async def get_historical_cutoff(self) -> HistoricalCutoff:
        raw = await self._guard(self._client.historical.cutoff())
        return cutoff_from_sdk(raw, observed_at=self._now())

    async def get_series(self, ticker: str) -> Series:
        raw = await self._guard(self._client.series.get(ticker))
        return self._domain(series_from_sdk, raw)

    async def get_event(self, event_ticker: str) -> Event:
        raw = await self._guard(self._client.events.get(event_ticker))
        return self._domain(event_from_sdk, raw)

    async def get_market(self, ticker: str) -> Market:
        raw = await self._guard(self._client.markets.get(ticker))
        return self._domain(
            lambda item: market_from_sdk(item, captured_at=self._now(), series_ticker=None),
            raw,
        )

    async def list_markets(
        self,
        *,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        status: MarketStatus | None = None,
        origin: ApiOrigin = ApiOrigin.LIVE,
    ) -> tuple[Market, ...]:
        query = status_query(status)
        if origin is ApiOrigin.HISTORICAL:
            page = await self._guard(
                self._client.historical.markets(
                    series_ticker=series_ticker,
                    event_ticker=event_ticker,
                    limit=200,
                )
            )
        else:
            page = await self._guard(
                self._client.markets.list(
                    status=cast("MarketStatusLiteral", query) if query is not None else None,
                    series_ticker=series_ticker,
                    event_ticker=event_ticker,
                    limit=200,
                )
            )
        captured_at = self._now()
        markets = tuple(
            self._domain(
                lambda item: market_from_sdk(
                    item,
                    captured_at=captured_at,
                    series_ticker=series_ticker,
                ),
                item,
            )
            for item in page.items
        )
        if status is None:
            return markets
        return tuple(market for market in markets if market.status is status)

    async def get_order_book(self, ticker: str) -> OrderBook:
        raw = await self._guard(self._client.markets.orderbook(ticker))
        return self._domain(lambda book: order_book_from_sdk(book, received_at=self._now()), raw)

    async def list_trades(
        self,
        ticker: str,
        *,
        start: UtcDatetime | None = None,
        end: UtcDatetime | None = None,
    ) -> tuple[TradePrint, ...]:
        page = await self._guard(
            self._client.markets.list_trades(
                ticker=ticker,
                min_ts=int(start.timestamp()) if start is not None else None,
                max_ts=int(end.timestamp()) if end is not None else None,
                limit=200,
            )
        )
        return tuple(
            self._domain(lambda item: trade_from_sdk(item, received_at=self._now()), item)
            for item in page.items
        )

    async def get_portfolio(self) -> PortfolioSnapshot:
        raise GatewayError("portfolio reads belong to Phase 2; this gateway does not load them")

    async def list_orders(self) -> tuple[Order, ...]:
        raise GatewayError("order reads belong to a later phase; this gateway does not load them")

    async def list_fills(self, *, since: UtcDatetime | None = None) -> tuple[Fill, ...]:
        del since
        raise GatewayError("fill reads belong to a later phase; this gateway does not load them")

    async def list_settlements(self, *, since: UtcDatetime | None = None) -> tuple[Settlement, ...]:
        del since
        raise GatewayError("settlement reads belong to a later phase")

    async def submit_order(self, request: OrderRequest) -> Order:
        del request
        require_order_submission(self.mode)
        raise GatewayError("read-only gateway cannot submit orders")

    async def cancel_order(self, client_order_id: UUID) -> Order:
        del client_order_id
        require_order_submission(self.mode)
        raise GatewayError("read-only gateway cannot cancel orders")

    def origin_of_last_call(self) -> ApiOrigin:
        capture = self._observing.last
        if capture is not None and "/historical/" in capture.path:
            return ApiOrigin.HISTORICAL
        return ApiOrigin.LIVE

    async def _guard[T](self, awaitable: Awaitable[T], *, method: str = "GET", path: str = "") -> T:
        try:
            self._spend(self._cost_for(method, path))
        except RateLimitedError:
            # The SDK call is already a coroutine. Closing it avoids an un-awaited warning
            # when the local budget refuses the read before any HTTP is sent.
            if isinstance(awaitable, Coroutine):
                awaitable.close()
            raise
        try:
            return await awaitable
        except KalshiRateLimitError as exc:
            retry_after = None
            if self._observing.last is not None:
                retry_after = self._observing.last.headers.get("retry-after")
            raise RateLimitedError(str(exc), retry_after=retry_after) from exc
        except KalshiError as exc:
            raise GatewayError(str(exc)) from exc

    def _cost_for(self, method: str, path: str) -> int:
        if self._budget is not None:
            return self._budget.cost_for(method, path)
        return self._default_cost

    def _spend(self, cost: int) -> None:
        if self._budget is None:
            return
        try:
            self._budget.take(cost, self._now())
        except RateLimitExceededError as exc:
            raise RateLimitedError(str(exc), retry_after=None) from exc

    def _now(self) -> UtcDatetime:
        return self._clock.now()

    def _domain[T, U](self, convert: Callable[[T], U], value: T) -> U:
        try:
            return convert(value)
        except ValidationError as exc:
            raise GatewayError(str(exc)) from exc
        except GatewayError:
            raise
