"""Paper and shadow checks against recorded books. Never a live order.

``LIVE`` and ``DEMO`` are refused after ``resolve_trading_mode``, including
when the live flag is set. Only ``PAPER`` writes the ledger. ``SHADOW``
records the price it would have paid and does not.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.market_data import OrderBook, TradePrint
from entropytrade.domain.modes import TradingMode, resolve_trading_mode
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.orders import ApprovedOrderIntent, OrderIntent
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskRejectedError, seal

Strategy = Callable[[OrderBook], OrderIntent | None]


class ShadowError(ValueError):
    """The runner was asked to start in a mode that can submit."""


@dataclass(frozen=True)
class ShadowComparison:
    """A paper or shadow price against the next recorded print, if one exists."""

    filled: bool
    price: Decimal | None
    next_print: Decimal | None
    difference: Decimal | None

    @property
    def gap(self) -> bool:
        """True when we had a price and no later print to compare it with."""
        return self.price is not None and self.next_print is None


def run_shadow(
    *,
    requested: TradingMode,
    environment: KalshiEnvironment,
    process_env: Mapping[str, str],
    books: Sequence[OrderBook],
    prints: Sequence[TradePrint],
    strategy: Strategy,
    ledger: Ledger,
    broker: PaperBroker,
    engine: RiskEngine,
) -> tuple[ShadowComparison, ...]:
    """Walk recorded books. ``LIVE`` and ``DEMO`` raise before the strategy runs."""
    resolved = resolve_trading_mode(requested, environment, process_env)
    if resolved is TradingMode.LIVE or resolved.submits_orders_to_exchange:
        raise ShadowError("the shadow runner does not submit to an exchange")
    compares = resolved in (TradingMode.PAPER, TradingMode.SHADOW)
    rows: list[ShadowComparison] = []
    for book in sorted(books, key=lambda item: item.received_at):
        intent = strategy(book)
        if intent is None or not compares:
            continue
        approved = _approve(intent, book, ledger, engine)
        if approved is None:
            rows.append(
                ShadowComparison(filled=False, price=None, next_print=None, difference=None)
            )
            continue
        price = approved.intent.yes_price
        filled = False
        if resolved is TradingMode.PAPER:
            known = {fill.fill_id for fill in ledger.fills()}
            broker.submit(approved, book, now=book.received_at)
            fresh = [fill for fill in ledger.fills() if fill.fill_id not in known]
            if fresh:
                price = fresh[-1].yes_price
                filled = True
        nxt = _next_print(prints, book.received_at)
        difference = None if nxt is None else nxt - price
        rows.append(
            ShadowComparison(filled=filled, price=price, next_print=nxt, difference=difference)
        )
    return tuple(rows)


def _approve(
    intent: OrderIntent,
    book: OrderBook,
    ledger: Ledger,
    engine: RiskEngine,
) -> ApprovedOrderIntent | None:
    decision = engine.evaluate(
        intent,
        portfolio=ledger.snapshot(),
        book=book,
        now=book.received_at,
        event_deployed=ZERO,
        realized_pnl=ledger.realized_pnl,
        peak_equity=ledger.peak_equity,
        equity=ledger.equity(),
    )
    if not decision.approved or decision.approved_quantity != intent.quantity:
        return None
    try:
        return seal(intent, decision)
    except RiskRejectedError:
        return None


def _next_print(prints: Sequence[TradePrint], at: datetime) -> Decimal | None:
    cutoff = ensure_utc(at)
    later = [item for item in prints if ensure_utc(item.executed_at) >= cutoff]
    if not later:
        return None
    return min(later, key=lambda item: item.executed_at).yes_price
