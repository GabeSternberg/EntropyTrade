"""Point-in-time replay. The strategy sees an as-of view, never the raw recording.

A fill is taken from the book at ``decision_time + latency``. If that book is
missing, there is no fill. If it is better than the book the strategy saw, the
prices are clamped back to that earlier touch, so the run cannot buy the
improvement.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from heapq import heappop, heappush
from itertools import count
from typing import TYPE_CHECKING, cast

from entropytrade.domain.enums import (
    ExecutionFidelity,
    FillScenario,
    LiquidityRole,
    MarketResult,
    OutcomeSide,
)
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.observations import FeatureObservation, select_as_of
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import BacktestRun, SampleSplit, SplitWindow
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.execution.paper import PaperBroker
from entropytrade.execution.series_fees import SeriesFeeTable
from entropytrade.portfolio.ledger import Ledger, LedgerError
from entropytrade.risk.engine import RiskEngine, RiskRejectedError, seal

if TYPE_CHECKING:
    from uuid import UUID


Strategy = Callable[["DecisionView", OrderBook], OrderIntent | None]


class ReplayError(ValueError):
    """The strategy or the recording broke a replay rule."""


class DecisionView:
    """Features whose ``available_at`` is at or before the decision."""

    def __init__(
        self,
        records: Sequence[FeatureObservation],
        decision_time: datetime,
        *,
        ledger: Ledger | None = None,
        schedule: FeeSchedule | None = None,
        pending: Mapping[tuple[str, OutcomeSide], Decimal] | None = None,
        target_date: date | None = None,
    ) -> None:
        self.ledger = ledger
        self.schedule = schedule
        self.pending = pending or {}
        self.target_date = target_date
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

    def __init__(
        self,
        *,
        fill_ids: tuple[str, ...],
        ending_equity: Decimal,
        fee_model_version: str | None = None,
        fee_models: tuple[FeeModelRef, ...] = (),
    ) -> None:
        self.audit: list[dict[str, object]] = []
        self.equity_curve: list[tuple[datetime, Decimal]] = []
        self.event_pnl: dict[str, Decimal] = {}
        self.fill_ids = fill_ids
        self.ending_equity = ending_equity
        self.fee_model_version = fee_model_version
        self.fee_models = fee_models

    def digest(self, run: BacktestRun) -> str:
        from entropytrade.domain.ids import content_hash

        return content_hash(
            {
                "config_hash": run.config_hash,
                "ending_equity": self.ending_equity,
                "fee_model_version": self.fee_model_version,
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
    series_fees: SeriesFeeTable | None = None,
    fee_schedule_at: Callable[[str, datetime], FeeSchedule] | None = None,
    max_book_age: timedelta = timedelta(hours=1),
    event_ids: Mapping[str, str] | None = None,
    close_times: Mapping[str, datetime] | None = None,
    target_dates: Mapping[str, date] | None = None,
    scenario: FillScenario = FillScenario.BASE,
    fidelity: ExecutionFidelity = ExecutionFidelity.ORDER_BOOK,
) -> ReplayResult:
    """Chronological snapshot-taker simulation. No future books or cross-split fills.

    Unknown queues are not modeled. Identical book payloads do not replenish consumed
    capacity unless a non-null exchange sequence advances. Resting remainders cancel.
    """
    if window.split is SampleSplit.HOLDOUT:
        raise ReplayError("holdout rows are not passed to the strategy")
    if latency < timedelta(0) or max_book_age < timedelta(0):
        raise ReplayError("latency and maximum book age must be nonnegative")
    if fidelity is not ExecutionFidelity.ORDER_BOOK:
        raise ReplayError("execution P&L requires sized order-book evidence")
    events: list[tuple[datetime, int, int, str, object]] = []
    serial = count()
    ordered = sorted(books, key=lambda b: (b.received_at, b.market_ticker))
    seen_books: dict[tuple[str, datetime], OrderBook] = {}
    for book in ordered:
        key = book.market_ticker, book.received_at
        if key in seen_books:
            if seen_books[key] != book:
                raise ReplayError("conflicting books at one receipt time")
            continue
        seen_books[key] = book
        if window.start <= book.received_at < window.end:
            heappush(events, (book.received_at, 0, next(serial), "book", book))
            heappush(events, (book.received_at, 3, next(serial), "decision", book))
    for stamp, ticker, outcome in settlements:
        if window.start <= stamp < window.end:
            heappush(events, (stamp, 1, next(serial), "settle", (ticker, outcome)))
    known = {fill.fill_id for fill in ledger.fills()}
    applied: dict[str, FeeModelRef] = {}
    current: dict[str, OrderBook] = {}
    remaining: dict[str, OrderBook] = {}
    pending: dict[UUID, tuple[OrderIntent, OrderBook]] = {}
    resolved: set[str] = set()
    audit: list[dict[str, object]] = []
    curve: list[tuple[datetime, Decimal]] = [(window.start, ledger.equity())]
    event_pnl: dict[str, Decimal] = {}

    def event(ticker: str) -> str:
        return (event_ids or {}).get(ticker, ticker.rsplit("-", 1)[0])

    def exposure(ticker: str) -> Decimal:
        return sum(
            (
                p.total_cost
                for p in ledger.positions
                if event(p.contract.market_ticker) == event(ticker)
            ),
            ZERO,
        ) + sum(
            (
                o.max_cost
                for o, _ in pending.values()
                if event(o.contract.market_ticker) == event(ticker)
            ),
            ZERO,
        )

    while events:
        stamp, _, _, kind, payload = heappop(events)
        if stamp >= window.end:
            continue
        if kind == "book":
            book = cast("OrderBook", payload)
            previous = current.get(book.market_ticker)
            if (
                previous is None
                or previous.bids != book.bids
                or previous.asks != book.asks
                or (
                    book.sequence is not None
                    and previous.sequence is not None
                    and book.sequence > previous.sequence
                )
            ):
                remaining[book.market_ticker] = book
            else:
                remaining[book.market_ticker] = remaining[book.market_ticker].revalidated(
                    received_at=stamp, exchange_ts=book.exchange_ts, sequence=book.sequence
                )
            current[book.market_ticker] = book
            continue
        if kind == "settle":
            ticker, outcome = cast("tuple[str, MarketResult]", payload)
            resolved.add(ticker)
            if ledger.position(ticker) is not None:
                before = ledger.realized_pnl
                ledger.settle(ticker, outcome, at=stamp)
                event_pnl[event(ticker)] = (
                    event_pnl.get(event(ticker), ZERO) + ledger.realized_pnl - before
                )
                curve.append((stamp, ledger.equity()))
            continue
        if kind == "decision":
            book = cast("OrderBook", payload)
            ticker = book.market_ticker
            if ticker in resolved or stamp >= (close_times or {}).get(ticker, window.end):
                continue
            if fee_schedule_at is not None:
                broker.use_schedule(fee_schedule_at(ticker, stamp))
            elif series_fees is not None:
                _apply_series_fee(broker, series_fees, ticker, applied)
            quantities: dict[tuple[str, OutcomeSide], Decimal] = {}
            for order, _ in pending.values():
                pending_key = order.contract.market_ticker, order.contract.side
                quantities[pending_key] = quantities.get(pending_key, ZERO) + order.quantity
            view = DecisionView(
                records,
                stamp,
                ledger=ledger,
                schedule=broker.schedule,
                pending=quantities,
                target_date=(target_dates or {}).get(ticker),
            )
            intent = strategy(view, book)
            if intent is None:
                continue
            if intent.decision_time != stamp or intent.contract.market_ticker != ticker:
                raise ReplayError("intent must identify its exact decision time and book market")
            if intent.intent_id in pending or ledger.order(intent.intent_id) is not None:
                audit.append(
                    {"time": stamp.isoformat(), "status": "duplicate_intent", "ticker": ticker}
                )
                continue
            decision = engine.evaluate(
                intent,
                portfolio=ledger.snapshot(),
                book=book,
                now=stamp,
                event_deployed=exposure(ticker),
                realized_pnl=ledger.realized_pnl,
                peak_equity=ledger.peak_equity,
                equity=ledger.equity(),
            )
            try:
                approved = seal(intent, decision)
            except RiskRejectedError:
                audit.append(
                    {"time": stamp.isoformat(), "status": "risk_rejected", "ticker": ticker}
                )
                continue
            eligible = stamp + latency
            if eligible >= window.end or eligible >= (close_times or {}).get(ticker, window.end):
                audit.append(
                    {
                        "time": stamp.isoformat(),
                        "status": "outside_execution_window",
                        "ticker": ticker,
                    }
                )
                continue
            intent = intent.revalidated(quantity=approved.quantity)
            reserve = intent.max_cost + trade_fee(
                broker.schedule,
                yes_price=intent.yes_price,
                quantity=intent.quantity,
                role=LiquidityRole.TAKER,
            )
            try:
                ledger.reserve(intent.intent_id, reserve)
            except LedgerError:
                audit.append(
                    {"time": stamp.isoformat(), "status": "insufficient_cash", "ticker": ticker}
                )
                continue
            pending[intent.intent_id] = intent, book
            heappush(events, (eligible, 2, next(serial), "execute", intent.intent_id))
            continue
        identifier = cast("UUID", payload)
        intent, decision_book = pending.pop(identifier)
        ledger.release(identifier)
        ticker = intent.contract.market_ticker
        execution_book = remaining.get(ticker)
        if (
            execution_book is None
            or execution_book.received_at > stamp
            or stamp - execution_book.received_at > max_book_age
            or ticker in resolved
            or execution_book.is_crossed
            or (intent.expires_at is not None and stamp >= intent.expires_at)
        ):
            audit.append(
                {"time": stamp.isoformat(), "status": "unfilled_stale_or_closed", "ticker": ticker}
            )
            continue
        if fee_schedule_at is not None:
            broker.use_schedule(fee_schedule_at(ticker, stamp))
        elif series_fees is not None:
            _apply_series_fee(broker, series_fees, ticker, applied)
        fill_book = (
            execution_book
            if scenario is FillScenario.OPTIMISTIC
            else clamp_to_decision(decision_book, execution_book)
        )
        if scenario is FillScenario.CONSERVATIVE:
            fill_book = _conservative(fill_book)
        if intent.edge is not None:
            level_count = len(
                fill_book.asks if intent.contract.side is OutcomeSide.YES else fill_book.bids
            )
            estimate = trade_fee(
                broker.schedule,
                yes_price=Decimal("0.5"),
                quantity=intent.quantity,
                role=LiquidityRole.TAKER,
            ) + max(0, level_count - 1) * Decimal("0.01")
            intent = intent.revalidated(
                edge=intent.edge.revalidated(
                    fee_per_contract=(estimate / intent.quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_CEILING
                    )
                )
            )
        decision = engine.evaluate(
            intent,
            portfolio=ledger.snapshot(),
            book=fill_book,
            now=stamp,
            event_deployed=exposure(ticker),
            realized_pnl=ledger.realized_pnl,
            peak_equity=ledger.peak_equity,
            equity=ledger.equity(),
        )
        try:
            approved = seal(intent, decision)
        except RiskRejectedError:
            audit.append(
                {"time": stamp.isoformat(), "status": "execution_risk_rejected", "ticker": ticker}
            )
            continue
        before = ledger.realized_pnl
        before_ids = {f.fill_id for f in ledger.fills()}
        completed_order = broker.submit(approved, fill_book, now=stamp)
        if not completed_order.state.is_terminal:
            completed_order = broker.cancel(completed_order.client_order_id, now=stamp)
        fresh = [f for f in ledger.fills() if f.fill_id not in before_ids]
        consumed = sum((f.quantity for f in fresh), ZERO)
        remaining[ticker] = _consume(
            execution_book, intent.contract.side, intent.yes_price, consumed
        )
        event_pnl[event(ticker)] = event_pnl.get(event(ticker), ZERO) + ledger.realized_pnl - before
        audit.append(
            {
                "time": stamp.isoformat(),
                "decision_time": intent.decision_time.isoformat(),
                "status": completed_order.state.value,
                "ticker": ticker,
                "requested": str(intent.quantity),
                "filled": str(completed_order.filled_quantity),
            }
        )
        curve.append((stamp, ledger.equity()))
    result = ReplayResult(
        fill_ids=tuple(f.fill_id for f in ledger.fills() if f.fill_id not in known),
        ending_equity=ledger.equity(),
        fee_model_version=None if series_fees is None else series_fees.version,
        fee_models=tuple(applied.values()),
    )
    result.audit = audit
    result.equity_curve = curve
    result.event_pnl = event_pnl
    return result


def _consume(book: OrderBook, side: OutcomeSide, limit: Decimal, quantity: Decimal) -> OrderBook:
    levels = book.asks if side is OutcomeSide.YES else book.bids
    updated = []
    for level in levels:
        available = level.quantity
        if level.price <= limit if side is OutcomeSide.YES else level.price >= limit:
            taken = min(quantity, available)
            quantity -= taken
            available -= taken
        if available > ZERO:
            updated.append(level.revalidated(quantity=available))
    return book.revalidated(**{"asks" if side is OutcomeSide.YES else "bids": tuple(updated)})


def _conservative(book: OrderBook) -> OrderBook:
    def levels(items: tuple[OrderBookLevel, ...], side: OutcomeSide) -> tuple[OrderBookLevel, ...]:
        changed = []
        for level in items:
            quantity = (level.quantity / 2).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            price = level.price + (Decimal("0.01") if side is OutcomeSide.YES else Decimal("-0.01"))
            if quantity > ZERO and ZERO < price < 1:
                changed.append(level.revalidated(price=price, quantity=quantity))
        return tuple(changed)

    return book.revalidated(
        asks=levels(book.asks, OutcomeSide.YES), bids=levels(book.bids, OutcomeSide.NO)
    )


def _apply_series_fee(
    broker: PaperBroker,
    series_fees: SeriesFeeTable,
    market_ticker: str,
    applied: dict[str, FeeModelRef],
) -> None:
    try:
        series = series_fees.match(market_ticker)
    except KeyError as exc:
        raise ReplayError(f"no stored series fee for {market_ticker}") from exc
    broker.use_schedule(
        series_fees.schedule(series, coefficient=broker.schedule.quadratic_coefficient)
    )
    applied[series.ticker] = series_fees.fee_model(series)


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
    eligible = [b for b in books if b.market_ticker == ticker and b.received_at <= when]
    return max(eligible, key=lambda b: b.received_at) if eligible else None


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
