"""Convert Kalshi SDK models into domain values. Nothing in this module is re-exported.

Floats never enter a domain field: SDK decimals are already ``Decimal``, and wire strings
are parsed by the domain types.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

from kalshi.models.events import Event as SdkEvent
from kalshi.models.historical import HistoricalCutoff as SdkCutoff
from kalshi.models.historical import Trade as SdkTrade
from kalshi.models.markets import Market as SdkMarket
from kalshi.models.markets import Orderbook as SdkOrderbook
from kalshi.models.series import Series as SdkSeries

from entropytrade.domain.enums import (
    FeeType,
    MarketResult,
    MarketStatus,
    MarketType,
    OutcomeSide,
    StrikeType,
)
from entropytrade.domain.historical import HistoricalCutoff
from entropytrade.domain.market import (
    Event,
    Market,
    MarketRules,
    PriceRange,
    Series,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.domain.market_data import OrderBook, OrderBookLevel, TradePrint
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.settlement import parse_settlement

_STATUS_FILTER: dict[MarketStatus, str] = {
    MarketStatus.INITIALIZED: "unopened",
    MarketStatus.ACTIVE: "open",
    MarketStatus.INACTIVE: "paused",
    MarketStatus.CLOSED: "closed",
    MarketStatus.FINALIZED: "settled",
    MarketStatus.DETERMINED: "settled",
    MarketStatus.DISPUTED: "settled",
    MarketStatus.AMENDED: "settled",
}


def status_query(status: MarketStatus | None) -> str | None:
    """Kalshi's list filter is coarser than the market's own status enum."""
    if status is None:
        return None
    return _STATUS_FILTER[status]


def series_from_sdk(series: SdkSeries) -> Series:
    fee_type = _fee_type(series.fee_type)
    return Series(
        ticker=series.ticker,
        title=series.title,
        frequency=series.frequency,
        category=series.category,
        settlement_sources=_named_sources(series.settlement_sources),
        fee_type=fee_type,
        fee_multiplier=Decimal(series.fee_multiplier),
        contract_url=series.contract_url or None,
        exchange_index=series.exchange_index,
    )


def event_from_sdk(event: SdkEvent) -> Event:
    return Event(
        event_ticker=event.event_ticker,
        series_ticker=event.series_ticker,
        title=event.title,
        sub_title=event.sub_title,
        category=event.category,
        mutually_exclusive=event.mutually_exclusive,
        settlement_sources=_named_sources(event.settlement_sources),
        exchange_index=event.exchange_index,
    )


def market_from_sdk(
    market: SdkMarket,
    *,
    captured_at: datetime,
    series_ticker: str | None,
) -> Market:
    status = _status(market.status)
    result = _result(market.result)
    rules_text = market.rules_primary.strip()
    if not rules_text:
        raise GatewayError(f"{market.ticker} has empty rules_primary")
    parsed = parse_settlement(rules_text, market.rules_secondary, market.ticker)
    rules = MarketRules(
        market_ticker=market.ticker,
        rules_primary=rules_text,
        rules_secondary=market.rules_secondary,
        early_close_condition=market.early_close_condition,
        settlement_sources=parsed.sources,
        settlement_basis=parsed.basis,
        settlement_target_date=parsed.target_date,
        captured_at=captured_at,
    )
    return Market(
        ticker=market.ticker,
        event_ticker=market.event_ticker,
        series_ticker=series_ticker,
        market_type=_market_type(market.market_type),
        title=market.title or market.ticker,
        yes_sub_title=market.yes_sub_title,
        no_sub_title=market.no_sub_title,
        status=status,
        open_time=market.open_time,
        close_time=market.close_time,
        expected_expiration_time=market.expected_expiration_time,
        latest_expiration_time=market.latest_expiration_time,
        settlement_timer_seconds=market.settlement_timer_seconds,
        can_close_early=market.can_close_early,
        strike=_strike(market),
        rules=rules,
        tick_schedule=_ticks(market),
        result=result,
        settlement_value=market.settlement_value,
        settlement_ts=market.settlement_ts,
        exchange_index=market.exchange_index,
    )


def order_book_from_sdk(
    book: SdkOrderbook,
    *,
    received_at: datetime,
) -> OrderBook:
    yes = tuple(
        OrderBookLevel(price=level.price, quantity=level.quantity)
        for level in book.yes
        if level.quantity > 0
    )
    no = tuple(
        OrderBookLevel(price=level.price, quantity=level.quantity)
        for level in book.no
        if level.quantity > 0
    )
    return OrderBook.from_yes_and_no_bids(book.ticker, yes, no, received_at=received_at)


def trade_from_sdk(trade: SdkTrade, *, received_at: datetime) -> TradePrint:
    if trade.yes_price is None or trade.count is None:
        raise GatewayError(f"trade {trade.trade_id} is missing price or count")
    return TradePrint(
        trade_id=trade.trade_id,
        market_ticker=trade.ticker,
        yes_price=trade.yes_price,
        quantity=trade.count,
        taker_side=_taker(trade.taker_outcome_side),
        executed_at=trade.created_time,
        received_at=received_at,
        is_block_trade=trade.is_block_trade,
    )


def cutoff_from_sdk(cutoff: SdkCutoff, *, observed_at: datetime) -> HistoricalCutoff:
    return HistoricalCutoff(
        market_settled_ts=cutoff.market_settled_ts,
        trades_created_ts=cutoff.trades_created_ts,
        orders_updated_ts=cutoff.orders_updated_ts,
        market_positions_last_updated_ts=cutoff.market_positions_last_updated_ts,
        observed_at=observed_at,
    )


def _fee_type(value: str) -> FeeType:
    try:
        return FeeType(value)
    except ValueError as exc:
        raise GatewayError(f"unknown fee_type {value!r}") from exc


def _status(value: str) -> MarketStatus:
    try:
        return MarketStatus(value)
    except ValueError as exc:
        raise GatewayError(f"unknown market status {value!r}") from exc


def _market_type(value: str) -> MarketType:
    try:
        return MarketType(value)
    except ValueError as exc:
        raise GatewayError(f"unknown market type {value!r}") from exc


def _result(value: str) -> MarketResult | None:
    if value == "":
        return None
    try:
        return MarketResult(value)
    except ValueError as exc:
        raise GatewayError(f"unknown market result {value!r}") from exc


def _taker(value: str) -> OutcomeSide:
    try:
        return OutcomeSide(value)
    except ValueError as exc:
        raise GatewayError(f"unknown taker side {value!r}") from exc


def _strike(market: SdkMarket) -> Strike | None:
    if market.strike_type is None:
        return None
    try:
        kind = StrikeType(market.strike_type)
    except ValueError as exc:
        raise GatewayError(
            f"{market.ticker} has unknown strike_type {market.strike_type!r}"
        ) from exc
    return Strike(strike_type=kind, floor=market.floor_strike, cap=market.cap_strike)


def _ticks(market: SdkMarket) -> TickSchedule:
    ranges: list[PriceRange] = []
    raw_ranges = cast("Sequence[object]", market.price_ranges or [])
    for raw in raw_ranges:
        if not isinstance(raw, dict):
            continue
        start = raw.get("start")
        end = raw.get("end")
        step = raw.get("step")
        if start is None or end is None or step is None:
            continue
        ranges.append(
            PriceRange(
                start=_range_number(start, market.ticker),
                end=_range_number(end, market.ticker),
                step=_range_number(step, market.ticker),
            )
        )
    if not ranges:
        raise GatewayError(f"{market.ticker} has no price_ranges")
    return TickSchedule(ranges=tuple(ranges))


def _range_number(value: object, ticker: str) -> Decimal:
    if isinstance(value, bool | float):
        raise GatewayError(f"{ticker} price_ranges contains a {type(value).__name__}")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise GatewayError(f"{ticker} price_ranges value has type {type(value).__name__}")


def _named_sources(sources: object) -> tuple[SettlementSource, ...]:
    named: list[SettlementSource] = []
    if not isinstance(sources, list):
        return ()
    for source in sources:
        name = getattr(source, "name", None)
        url = getattr(source, "url", None)
        if isinstance(source, dict):
            name = source.get("name")
            url = source.get("url")
        if isinstance(name, str) and name.strip():
            named.append(
                SettlementSource(name=name.strip(), url=url if isinstance(url, str) else None)
            )
    return tuple(named)
