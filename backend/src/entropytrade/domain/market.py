"""Series, events, markets, contracts and their rules (spec sections 4 and 6).

A Kalshi *market* is one binary contract pair (YES/NO). :class:`Contract` names one tradable
outcome of a market. Rules are first-class data: :class:`MarketRules` carries the full rule text
and settlement sources, and its ``rules_hash`` changes whenever any of them change, which is how
rule revisions are detected and versioned.
"""

from decimal import Decimal
from itertools import pairwise
from typing import Self

from pydantic import Field, computed_field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import (
    FeeType,
    MarketResult,
    MarketStatus,
    MarketType,
    OutcomeSide,
    StrikeType,
    Venue,
)
from entropytrade.domain.ids import ContentHash, content_hash
from entropytrade.domain.numeric import ZERO, ExactDecimal, Price
from entropytrade.domain.time import UtcDatetime


class Contract(DomainModel):
    """One tradable outcome: (venue, market ticker, side)."""

    venue: Venue = Venue.KALSHI
    market_ticker: str = Field(min_length=1)
    side: OutcomeSide

    def opposite(self) -> "Contract":
        return Contract(venue=self.venue, market_ticker=self.market_ticker, side=self.side.opposite)


class SettlementSource(DomainModel):
    name: str = Field(min_length=1)
    url: str | None = None


class PriceRange(DomainModel):
    """A band of valid order prices with a fixed tick (Kalshi ``price_ranges``)."""

    start: Price
    end: Price
    step: Price

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.step <= ZERO:
            raise ValueError("tick step must be positive")
        if self.start > self.end:
            raise ValueError("price range start must not exceed end")
        return self

    def contains(self, price: Decimal) -> bool:
        return self.start <= price <= self.end and (price - self.start) % self.step == ZERO


class TickSchedule(DomainModel):
    ranges: tuple[PriceRange, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        ordered = sorted(self.ranges, key=lambda r: r.start)
        if list(self.ranges) != ordered:
            raise ValueError("price ranges must be sorted by start")
        for left, right in pairwise(ordered):
            if right.start < left.end:
                raise ValueError("price ranges must not overlap")
        return self

    def is_valid_order_price(self, price: Decimal) -> bool:
        """True if ``price`` is strictly inside (0, 1) and on the tick grid of some range."""
        if not ZERO < price < Decimal(1):
            return False
        return any(r.contains(price) for r in self.ranges)


class Strike(DomainModel):
    """How a numeric outcome maps to YES.

    Kalshi semantics (verified against live rule text, 2026-10-02):
    ``greater`` with floor 89 is "above 89" (90+ for integer readings); ``less`` with cap 82 is
    "below 82" (81 or lower); ``between`` floor 88 / cap 89 is inclusive on both ends.
    Functional, custom and structured strikes cannot be evaluated from floor/cap alone.
    """

    strike_type: StrikeType
    floor: ExactDecimal | None = None
    cap: ExactDecimal | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        needs_floor = self.strike_type in (StrikeType.GREATER, StrikeType.GREATER_OR_EQUAL)
        needs_cap = self.strike_type in (StrikeType.LESS, StrikeType.LESS_OR_EQUAL)
        if needs_floor and (self.floor is None or self.cap is not None):
            raise ValueError(f"{self.strike_type} strikes need a floor and no cap")
        if needs_cap and (self.cap is None or self.floor is not None):
            raise ValueError(f"{self.strike_type} strikes need a cap and no floor")
        if self.strike_type is StrikeType.BETWEEN:
            if self.floor is None or self.cap is None:
                raise ValueError("between strikes need both floor and cap")
            if self.floor > self.cap:
                raise ValueError("between strike floor must not exceed cap")
        return self

    @property
    def is_evaluable(self) -> bool:
        return self.strike_type not in (
            StrikeType.FUNCTIONAL,
            StrikeType.CUSTOM,
            StrikeType.STRUCTURED,
        )

    def resolves_yes(self, value: Decimal) -> bool:
        floor, cap = self.floor, self.cap
        match self.strike_type:
            case StrikeType.GREATER if floor is not None:
                return value > floor
            case StrikeType.GREATER_OR_EQUAL if floor is not None:
                return value >= floor
            case StrikeType.LESS if cap is not None:
                return value < cap
            case StrikeType.LESS_OR_EQUAL if cap is not None:
                return value <= cap
            case StrikeType.BETWEEN if floor is not None and cap is not None:
                return floor <= value <= cap
            case _:
                raise ValueError(f"{self.strike_type} strikes cannot be evaluated from a value")


class MarketRules(DomainModel):
    """A snapshot of a market's resolution terms. Any change produces a new ``rules_hash``."""

    market_ticker: str = Field(min_length=1)
    rules_primary: str = Field(min_length=1)
    rules_secondary: str = ""
    early_close_condition: str | None = None
    settlement_sources: tuple[SettlementSource, ...] = ()
    captured_at: UtcDatetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rules_hash(self) -> ContentHash:
        return content_hash(
            {
                "market_ticker": self.market_ticker,
                "rules_primary": self.rules_primary,
                "rules_secondary": self.rules_secondary,
                "early_close_condition": self.early_close_condition,
                "settlement_sources": [s.model_dump() for s in self.settlement_sources],
            }
        )


class Series(DomainModel):
    venue: Venue = Venue.KALSHI
    ticker: str = Field(min_length=1)
    title: str
    frequency: str | None = None
    category: str | None = None
    settlement_sources: tuple[SettlementSource, ...] = ()
    fee_type: FeeType
    fee_multiplier: ExactDecimal
    contract_url: str | None = None


class Event(DomainModel):
    venue: Venue = Venue.KALSHI
    event_ticker: str = Field(min_length=1)
    series_ticker: str = Field(min_length=1)
    title: str
    sub_title: str = ""
    category: str | None = None
    mutually_exclusive: bool
    settlement_sources: tuple[SettlementSource, ...] = ()
    exchange_index: int | None = Field(default=None, ge=0)


class Market(DomainModel):
    venue: Venue = Venue.KALSHI
    ticker: str = Field(min_length=1)
    event_ticker: str = Field(min_length=1)
    series_ticker: str | None = None
    market_type: MarketType
    title: str
    yes_sub_title: str = ""
    no_sub_title: str = ""
    status: MarketStatus
    open_time: UtcDatetime
    close_time: UtcDatetime
    expected_expiration_time: UtcDatetime | None = None
    latest_expiration_time: UtcDatetime | None = None
    settlement_timer_seconds: int | None = Field(default=None, ge=0)
    can_close_early: bool = False
    strike: Strike | None = None
    rules: MarketRules
    tick_schedule: TickSchedule
    result: MarketResult | None = None
    settlement_value: Price | None = None
    settlement_ts: UtcDatetime | None = None
    exchange_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.close_time < self.open_time:
            raise ValueError("close_time must not precede open_time")
        if (
            self.latest_expiration_time is not None
            and self.latest_expiration_time < self.close_time
        ):
            raise ValueError("latest_expiration_time must not precede close_time")
        if self.rules.market_ticker != self.ticker:
            raise ValueError("rules belong to a different market")
        if self.result is not None and not self.status.has_result:
            raise ValueError(f"a {self.status} market cannot have a result")
        if self.status is MarketStatus.FINALIZED and self.result is None:
            raise ValueError("a finalized market must have a result")
        return self

    def contract(self, side: OutcomeSide) -> Contract:
        return Contract(venue=self.venue, market_ticker=self.ticker, side=side)
