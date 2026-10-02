"""Positions, portfolio snapshots and settlements.

Kalshi nets positions per market: holding YES and buying NO reduces the YES position. A
:class:`Position` is therefore one (market, side, quantity) with ``quantity >= 0``; flat is
``quantity == 0``. Settlement pays ``value`` per YES contract and ``1 - value`` per NO contract
(``value`` is 1 for a YES result and 0 for NO), so payouts are bounded by ``[0, quantity]``.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import MarketResult, OutcomeSide
from entropytrade.domain.market import Contract
from entropytrade.domain.numeric import (
    ONE,
    ZERO,
    Money,
    NonNegativeMoney,
    Price,
    Quantity,
    complement,
    notional,
)
from entropytrade.domain.time import UtcDatetime


class Position(DomainModel):
    contract: Contract
    quantity: Quantity
    total_cost: NonNegativeMoney
    realized_pnl: Money = Decimal(0)
    fees_paid: NonNegativeMoney = Decimal(0)
    as_of: UtcDatetime

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.quantity == ZERO and self.total_cost != ZERO:
            raise ValueError("a flat position cannot carry open cost")
        if self.total_cost > notional(ONE, self.quantity):
            raise ValueError("cost basis cannot exceed $1 per contract")
        return self

    @property
    def is_flat(self) -> bool:
        return self.quantity == ZERO

    @property
    def max_payout(self) -> Decimal:
        return notional(ONE, self.quantity)

    @property
    def max_loss(self) -> Decimal:
        """Worst-case loss of the open position, excluding fees already paid."""
        return self.total_cost


def settlement_value_for(result: MarketResult, scalar_value: Decimal | None = None) -> Decimal:
    """Dollars paid per YES contract for a determined result."""
    if result is MarketResult.YES:
        return ONE
    if result is MarketResult.NO:
        return ZERO
    if scalar_value is None:
        raise ValueError("a scalar result needs a settlement value")
    return scalar_value


def settlement_payout(side: OutcomeSide, quantity: Decimal, yes_value: Decimal) -> Decimal:
    """Cash received at settlement for ``quantity`` contracts of ``side``."""
    per_contract = yes_value if side is OutcomeSide.YES else complement(yes_value)
    return notional(per_contract, quantity)


class Settlement(DomainModel):
    market_ticker: str = Field(min_length=1)
    result: MarketResult
    yes_value: Price
    yes_quantity: Quantity = Decimal(0)
    no_quantity: Quantity = Decimal(0)
    revenue: NonNegativeMoney
    fees: NonNegativeMoney = Decimal(0)
    settled_at: UtcDatetime

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.result is MarketResult.YES and self.yes_value != ONE:
            raise ValueError("a YES result pays $1 per YES contract")
        if self.result is MarketResult.NO and self.yes_value != ZERO:
            raise ValueError("a NO result pays $0 per YES contract")
        expected = settlement_payout(
            OutcomeSide.YES, self.yes_quantity, self.yes_value
        ) + settlement_payout(OutcomeSide.NO, self.no_quantity, self.yes_value)
        if self.revenue != expected:
            raise ValueError(f"revenue {self.revenue} does not match payout {expected}")
        return self


class SnapshotSource(StrEnum):
    EXCHANGE = "exchange"
    LOCAL = "local"
    PAPER = "paper"


class PortfolioSnapshot(DomainModel):
    as_of: UtcDatetime
    source: SnapshotSource
    cash_balance: Money
    resting_order_collateral: NonNegativeMoney = Decimal(0)
    positions: tuple[Position, ...] = ()

    @model_validator(mode="after")
    def _check(self) -> Self:
        tickers = [p.contract.market_ticker for p in self.positions if not p.is_flat]
        if len(tickers) != len(set(tickers)):
            raise ValueError("positions are netted per market; found duplicates")
        return self

    @property
    def open_positions(self) -> tuple[Position, ...]:
        return tuple(p for p in self.positions if not p.is_flat)

    @property
    def capital_at_risk(self) -> Decimal:
        """Open cost basis plus collateral locked by resting orders."""
        return sum((p.max_loss for p in self.open_positions), ZERO) + self.resting_order_collateral
