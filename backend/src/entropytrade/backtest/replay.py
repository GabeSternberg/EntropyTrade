"""Point-in-time replay. The strategy sees an as-of view, never the raw recording.

A fill is taken from the book at ``decision_time + latency``. If that book is
missing, there is no fill. If it is better than the book the strategy saw, the
prices are clamped back to that earlier touch, so the run cannot buy the
improvement.
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from entropytrade.domain.enums import MarketResult
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.observations import FeatureObservation, select_as_of
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import BacktestRun, SampleSplit, SplitWindow
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskRejectedError, seal

Strategy = Callable[["DecisionView", OrderBook], OrderIntent | None]


class ReplayError(ValueError):
    """The strategy or the recording broke a replay rule."""


class DecisionView:
    """Features whose ``available_at`` is at or before the decision."""

    def __init__(self, records: Sequence[FeatureObservation], decision_time: datetime) -> None:
        self.decision_time = ensure_utc(decision_time)
        self._visible = select_as_of(
            records,
            self.decision_time,
            key=lambda record: (record.feature_name, record.entity_id),
        )

    def feature(self, name: str, entity_id: str) -> FeatureObservation | None:
        return self._visible.get((name, entity_id))


class ReplayResult:
    """Fills produced inside one split, and the equity after them."""

    def __init__(self, *, fill_ids: tuple[str, ...], ending_equity: Decimal) -> None:
        self.fill_ids = fill_ids
        self.ending_equity = ending_equity

    def digest(self, run: BacktestRun) -> str:
        from entropytrade.domain.ids import content_hash

        return content_hash(
            {
                "config_hash": run.config_hash,
                "ending_equity": self.ending_equity,
                "fill_ids": self.fill_ids,
                "spec_hash": run.strategy_spec_hash,
                "strategy_id": run.strategy_id,
            }
        )


def run_replay(
    *,
    books: Sequence[OrderBook],
    records: Sequence[FeatureObservation],
    strategy: Strategy,
    ledger: Ledger,
    broker: PaperBroker,
    engine: RiskEngine,
    latency: timedelta,
    window: SplitWindow,
    settlements: Sequence[tuple[datetime, str, MarketResult]] = (),
) -> ReplayResult:
    """Walk books inside ``window``. Holdout is not a trading split."""
    if window.split is SampleSplit.HOLDOUT:
        raise ReplayError("holdout rows are not passed to the strategy")
    ordered = tuple(sorted(books, key=lambda book: (book.received_at, book.market_ticker)))
    known = {fill.fill_id for fill in ledger.fills()}
    for book in ordered:
        if book.received_at < window.start or book.received_at >= window.end:
            continue
        _settle_due(ledger, settlements, book.received_at, window)
        view = DecisionView(records, book.received_at)
        intent = strategy(view, book)
        if intent is None:
            continue
        if intent.decision_time > book.received_at:
            raise ReplayError("an intent cannot be decided after the book it saw")
        if intent.contract.market_ticker != book.market_ticker:
            raise ReplayError("intent market does not match the book")
        later = _book_at(ordered, book.market_ticker, book.received_at + latency)
        if later is None or later.is_crossed:
            continue
        fill_book = clamp_to_decision(book, later)
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
        try:
            approved = seal(intent, decision)
        except RiskRejectedError:
            continue
        broker.submit(approved, fill_book, now=later.received_at)
    _settle_due(ledger, settlements, window.end, window)
    fresh = tuple(fill.fill_id for fill in ledger.fills() if fill.fill_id not in known)
    return ReplayResult(fill_ids=fresh, ending_equity=ledger.equity())


def run_walk_forward(
    *,
    books: Sequence[OrderBook],
    records: Sequence[FeatureObservation],
    strategy: Strategy,
    ledger: Ledger,
    broker: PaperBroker,
    engine: RiskEngine,
    latency: timedelta,
    splits: Sequence[SplitWindow],
) -> dict[SampleSplit, ReplayResult]:
    """Train, then validation. The holdout split is skipped."""
    results: dict[SampleSplit, ReplayResult] = {}
    for window in splits:
        if window.split is SampleSplit.HOLDOUT:
            continue
        results[window.split] = run_replay(
            books=books,
            records=records,
            strategy=strategy,
            ledger=ledger,
            broker=broker,
            engine=engine,
            latency=latency,
            window=window,
        )
    return results


def _settle_due(
    ledger: Ledger,
    settlements: Sequence[tuple[datetime, str, MarketResult]],
    as_of: datetime,
    window: SplitWindow,
) -> None:
    for available_at, ticker, result in settlements:
        if available_at < window.start or available_at >= window.end or available_at > as_of:
            continue
        if ledger.position(ticker) is None:
            continue
        ledger.settle(ticker, result, at=available_at)


def clamp_to_decision(decision: OrderBook, later: OrderBook) -> OrderBook:
    """Drop any price improvement versus the book the strategy was shown."""
    ask_floor = decision.best_ask.price if decision.best_ask is not None else None
    bid_ceiling = decision.best_bid.price if decision.best_bid is not None else None
    asks: list[tuple[Decimal, Decimal]] = []
    for level in later.asks:
        price = level.price if ask_floor is None or level.price >= ask_floor else ask_floor
        asks.append((price, level.quantity))
    bids: list[tuple[Decimal, Decimal]] = []
    for level in later.bids:
        price = level.price if bid_ceiling is None or level.price <= bid_ceiling else bid_ceiling
        bids.append((price, level.quantity))
    return OrderBook(
        market_ticker=later.market_ticker,
        bids=_merge(bids, descending=True),
        asks=_merge(asks, descending=False),
        received_at=later.received_at,
        exchange_ts=later.exchange_ts,
        sequence=later.sequence,
    )


def _book_at(books: Sequence[OrderBook], ticker: str, when: datetime) -> OrderBook | None:
    for book in books:
        if book.market_ticker == ticker and book.received_at >= when:
            return book
    return None


def _merge(
    levels: list[tuple[Decimal, Decimal]],
    *,
    descending: bool,
) -> tuple[OrderBookLevel, ...]:
    totals: dict[Decimal, Decimal] = {}
    for price, quantity in levels:
        totals[price] = totals.get(price, ZERO) + quantity
    ordered = sorted(totals, reverse=descending)
    return tuple(OrderBookLevel(price=price, quantity=totals[price]) for price in ordered)
