"""One YES-price order book shared by the live feed and by replay.

Kalshi publishes YES bids and NO bids. A NO bid at ``q`` is a YES ask at ``1 - q``. Deltas
are signed fixed-point counts; a level at or below zero is removed. The book is stale after
a gap or a disconnect until a snapshot replaces it.
"""

from decimal import Decimal

from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import QUANTITY_QUANTUM, ZERO, to_decimal
from entropytrade.domain.time import UtcDatetime


class BookError(ValueError):
    """A delta arrived for a book that has no snapshot, or a quantity is off the grid."""


def signed_quantity(value: object) -> Decimal:
    """A contract-count delta on the 2 dp grid. Negative removes size."""
    number = to_decimal(value)
    quantized = number.quantize(QUANTITY_QUANTUM)
    if quantized != number:
        raise BookError(f"quantity delta {number} is finer than {QUANTITY_QUANTUM}")
    return quantized


class LocalBook:
    """Price-indexed YES and NO bids for a single ticker."""

    def __init__(self, market_ticker: str) -> None:
        self.market_ticker = market_ticker
        self.yes: dict[Decimal, Decimal] = {}
        self.no: dict[Decimal, Decimal] = {}
        self.sequence: int | None = None
        self.ready = False

    def wipe(self) -> None:
        self.yes.clear()
        self.no.clear()
        self.sequence = None
        self.ready = False

    def apply_snapshot(
        self,
        yes: tuple[tuple[Decimal, Decimal], ...],
        no: tuple[tuple[Decimal, Decimal], ...],
        *,
        sequence: int,
        received_at: UtcDatetime,
        exchange_ts: UtcDatetime | None = None,
    ) -> OrderBook:
        self.yes = _merge(yes)
        self.no = _merge(no)
        self.sequence = sequence
        self.ready = True
        return self.view(received_at=received_at, exchange_ts=exchange_ts)

    def apply_delta(
        self,
        side: str,
        price: Decimal,
        delta: Decimal,
        *,
        sequence: int,
        received_at: UtcDatetime,
        exchange_ts: UtcDatetime | None = None,
    ) -> OrderBook:
        if not self.ready:
            raise BookError(f"{self.market_ticker} has no snapshot; refusing the delta")
        levels = self.yes if side == "yes" else self.no
        if side not in ("yes", "no"):
            raise BookError(f"unknown book side {side!r}")
        updated = levels.get(price, ZERO) + delta
        if updated < ZERO:
            raise BookError("delta would make displayed quantity negative")
        if updated == ZERO:
            levels.pop(price, None)
        else:
            levels[price] = updated
        self.sequence = sequence
        return self.view(received_at=received_at, exchange_ts=exchange_ts)

    def view(
        self,
        *,
        received_at: UtcDatetime,
        exchange_ts: UtcDatetime | None = None,
    ) -> OrderBook:
        return OrderBook.from_yes_and_no_bids(
            self.market_ticker,
            _levels(self.yes),
            _levels(self.no),
            received_at=received_at,
            exchange_ts=exchange_ts,
            sequence=self.sequence,
        )


def _merge(levels: tuple[tuple[Decimal, Decimal], ...]) -> dict[Decimal, Decimal]:
    merged: dict[Decimal, Decimal] = {}
    for price, quantity in levels:
        if quantity <= ZERO:
            continue
        merged[price] = merged.get(price, ZERO) + quantity
    return merged


def _levels(levels: dict[Decimal, Decimal]) -> tuple[OrderBookLevel, ...]:
    return tuple(
        OrderBookLevel(price=price, quantity=quantity)
        for price, quantity in levels.items()
        if quantity > ZERO
    )
