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
from entropytrade.execution.fees import FeeSchedule
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
    market_ticker: str = ""

    @property
    def gap(self) -> bool:
        """True when we had a price and no later print to compare it with."""
        return self.price is not None and self.next_print is None


@dataclass(frozen=True)
class ShadowPaperRecord:
    """Paper fill price minus the shadow price on the same decision."""

    market_ticker: str
    paper_filled: bool
    paper_price: Decimal | None
    shadow_price: Decimal | None
    difference: Decimal | None


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
                ShadowComparison(
                    filled=False,
                    price=None,
                    next_print=None,
                    difference=None,
                    market_ticker=book.market_ticker,
                )
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
            ShadowComparison(
                filled=filled,
                price=price,
                next_print=nxt,
                difference=difference,
                market_ticker=book.market_ticker,
            )
        )
    return tuple(rows)


def compare_shadow_and_paper(
    *,
    environment: KalshiEnvironment,
    process_env: Mapping[str, str],
    books: Sequence[OrderBook],
    prints: Sequence[TradePrint],
    strategy: Strategy,
    starting_cash: Decimal,
    as_of: datetime,
    schedule: FeeSchedule,
    engines: tuple[RiskEngine, RiskEngine],
) -> tuple[ShadowPaperRecord, ...]:
    """Run paper and shadow on separate ledgers and record the price gap.

    ``difference`` is the paper price minus the shadow price. It is set only
    when both sides named a price. Neither mode submits to an exchange.
    """
    paper_ledger = Ledger(starting_cash, as_of=as_of)
    shadow_ledger = Ledger(starting_cash, as_of=as_of)
    paper_rows = run_shadow(
        requested=TradingMode.PAPER,
        environment=environment,
        process_env=process_env,
        books=books,
        prints=prints,
        strategy=strategy,
        ledger=paper_ledger,
        broker=PaperBroker(paper_ledger, schedule),
        engine=engines[0],
    )
    shadow_rows = run_shadow(
        requested=TradingMode.SHADOW,
        environment=environment,
        process_env=process_env,
        books=books,
        prints=prints,
        strategy=strategy,
        ledger=shadow_ledger,
        broker=PaperBroker(shadow_ledger, schedule),
        engine=engines[1],
    )
    if len(paper_rows) != len(shadow_rows):
        raise ShadowError("paper and shadow did not see the same decisions")
    records: list[ShadowPaperRecord] = []
    for paper, shadow in zip(paper_rows, shadow_rows, strict=True):
        difference = None
        if paper.price is not None and shadow.price is not None:
            difference = paper.price - shadow.price
        ticker = paper.market_ticker or shadow.market_ticker
        records.append(
            ShadowPaperRecord(
                market_ticker=ticker,
                paper_filled=paper.filled,
                paper_price=paper.price,
                shadow_price=shadow.price,
                difference=difference,
            )
        )
    return tuple(records)


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
