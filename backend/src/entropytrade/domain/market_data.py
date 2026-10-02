"""Order books, quotes and trade prints.

Books are stored in a single YES-price scale: ``bids`` are YES bids, ``asks`` are YES asks.
Kalshi publishes YES bids and NO bids; a NO bid at ``q`` is a YES ask at ``1 - q``
(:meth:`OrderBook.from_yes_and_no_bids`). Every timestamp distinguishes the exchange's time from
the time we received the data so latency and point-in-time availability are explicit.
"""

from collections.abc import Iterable
from decimal import Decimal
from itertools import pairwise
from typing import Self

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import MarketStatus, OutcomeSide
from entropytrade.domain.numeric import (
    ONE,
    PositiveQuantity,
    Price,
    Quantity,
    complement,
)
from entropytrade.domain.time import UtcDatetime


class OrderBookLevel(DomainModel):
    price: Price
    quantity: PositiveQuantity


class OrderBook(DomainModel):
    market_ticker: str = Field(min_length=1)
    bids: tuple[OrderBookLevel, ...] = ()
    asks: tuple[OrderBookLevel, ...] = ()
    exchange_ts: UtcDatetime | None = None
    received_at: UtcDatetime
    sequence: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> Self:
        bid_prices = [level.price for level in self.bids]
        ask_prices = [level.price for level in self.asks]
        if any(a <= b for a, b in pairwise(bid_prices)):
            raise ValueError("bids must be strictly descending by price")
        if any(a >= b for a, b in pairwise(ask_prices)):
            raise ValueError("asks must be strictly ascending by price")
        return self

    @classmethod
    def from_yes_and_no_bids(
        cls,
        market_ticker: str,
        yes_bids: Iterable[OrderBookLevel],
        no_bids: Iterable[OrderBookLevel],
        *,
        received_at: UtcDatetime,
        exchange_ts: UtcDatetime | None = None,
        sequence: int | None = None,
    ) -> "OrderBook":
        """Build from Kalshi's native representation (both sides as bids in their own leg)."""
        bids = sorted(yes_bids, key=lambda lvl: lvl.price, reverse=True)
        asks = sorted(
            (OrderBookLevel(price=complement(lvl.price), quantity=lvl.quantity) for lvl in no_bids),
            key=lambda lvl: lvl.price,
        )
        return cls(
            market_ticker=market_ticker,
            bids=tuple(bids),
            asks=tuple(asks),
            received_at=received_at,
            exchange_ts=exchange_ts,
            sequence=sequence,
        )

    def no_bids(self) -> tuple[OrderBookLevel, ...]:
        """The NO-leg view of the ask side, highest NO bid first."""
        return tuple(
            OrderBookLevel(price=complement(lvl.price), quantity=lvl.quantity) for lvl in self.asks
        )

    @property
    def best_bid(self) -> OrderBookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> OrderBookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return ask.price - bid.price

    @property
    def midpoint(self) -> Decimal | None:
        """Displayed midpoint. Never an executable price; use bids/asks for that."""
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return (bid.price + ask.price) / 2

    @property
    def is_crossed(self) -> bool:
        """A crossed or locked book indicates corrupted state; strategies must not consume it."""
        spread = self.spread
        return spread is not None and spread <= 0

    def best_price_to_buy(self, side: OutcomeSide) -> Decimal | None:
        """Cheapest available price per contract to go long ``side`` (taker), in that leg."""
        if side is OutcomeSide.YES:
            return self.best_ask.price if self.best_ask else None
        return ONE - self.best_bid.price if self.best_bid else None


class MarketSnapshot(DomainModel):
    """Top-of-book and summary statistics for a market at one moment."""

    market_ticker: str = Field(min_length=1)
    status: MarketStatus
    yes_bid: Price | None = None
    yes_bid_size: Quantity | None = None
    yes_ask: Price | None = None
    yes_ask_size: Quantity | None = None
    last_price: Price | None = None
    volume: Quantity | None = None
    open_interest: Quantity | None = None
    exchange_ts: UtcDatetime | None = None
    received_at: UtcDatetime

    @property
    def implied_probability(self) -> Decimal | None:
        """Displayed mid as a rough market-implied probability (not executable)."""
        if self.yes_bid is None or self.yes_ask is None:
            return None
        return (self.yes_bid + self.yes_ask) / 2


class TradePrint(DomainModel):
    """A public trade. ``yes_price`` is the YES-leg price regardless of taker side."""

    trade_id: str = Field(min_length=1)
    market_ticker: str = Field(min_length=1)
    yes_price: Price
    quantity: PositiveQuantity
    taker_side: OutcomeSide
    executed_at: UtcDatetime
    received_at: UtcDatetime
    is_block_trade: bool = False
