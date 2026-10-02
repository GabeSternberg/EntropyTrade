"""Structural price checks. Executable asks only. No model and no exchange submit.

A crossed book is skipped. A violation is still reported when the risk gate
refuses the paper package, and in that case nothing is filled.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import pairwise

from entropytrade.domain.enums import LiquidityRole, OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ONE, ZERO
from entropytrade.domain.orders import ApprovedOrderIntent, OrderIntent
from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.frames import BookSnapshotFrame
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskRejectedError, seal

_QTY = Decimal("1.00")


@dataclass(frozen=True)
class Bracket:
    """One greater-than strike and the book to trade it."""

    floor: Decimal
    book: OrderBook


@dataclass(frozen=True)
class Violation:
    kind: str
    tickers: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ScanResult:
    violations: tuple[Violation, ...]
    fill_ids: tuple[str, ...]


def book_from_snapshot(frame: BookSnapshotFrame) -> OrderBook:
    """YES and NO bids on a snapshot become one YES-price book."""
    return OrderBook.from_yes_and_no_bids(
        frame.market_ticker,
        (OrderBookLevel(price=level.price, quantity=level.quantity) for level in frame.yes),
        (OrderBookLevel(price=level.price, quantity=level.quantity) for level in frame.no),
        received_at=frame.received_at,
        exchange_ts=frame.exchange_ts,
        sequence=frame.seq,
    )


def scan_ladder(brackets: Sequence[Bracket]) -> tuple[Violation, ...]:
    """Flag a higher strike whose YES ask is strictly above a lower strike's YES ask."""
    usable = [bracket for bracket in brackets if _ask(bracket.book) is not None]
    ordered = sorted(usable, key=lambda bracket: bracket.floor)
    found: list[Violation] = []
    for lower, higher in pairwise(ordered):
        lower_ask = _ask(lower.book)
        higher_ask = _ask(higher.book)
        if lower_ask is None or higher_ask is None:
            continue
        if higher_ask > lower_ask:
            found.append(
                Violation(
                    kind="monotonic",
                    tickers=(lower.book.market_ticker, higher.book.market_ticker),
                    detail=f"YES ask {higher_ask} on the higher strike exceeds {lower_ask}",
                )
            )
    return tuple(found)


def scan_exhaustive(books: Sequence[OrderBook]) -> tuple[Violation, ...]:
    """Flag mutually exclusive, exhaustive YES asks that sum to less than 1."""
    asks: list[Decimal] = []
    tickers: list[str] = []
    for book in books:
        ask = _ask(book)
        if ask is None:
            return ()
        asks.append(ask)
        tickers.append(book.market_ticker)
    total = sum(asks, start=ZERO)
    if total >= ONE:
        return ()
    return (
        Violation(
            kind="exclusive",
            tickers=tuple(tickers),
            detail=f"YES asks sum to {total}, under 1",
        ),
    )


def complement_gap(book: OrderBook) -> Violation | None:
    """YES ask plus the NO ask implied by the YES bid. Crossed books are skipped.

    On an uncrossed book the sum is at least 1, so this returns nothing.
    """
    if book.is_crossed or book.best_ask is None or book.best_bid is None:
        return None
    total = book.best_ask.price + (ONE - book.best_bid.price)
    if total >= ONE:
        return None
    return Violation(
        kind="complement",
        tickers=(book.market_ticker,),
        detail=f"YES ask plus NO ask is {total}",
    )


def paper_ladder(
    brackets: Sequence[Bracket],
    *,
    schedule: FeeSchedule,
    ledger: Ledger,
    broker: PaperBroker,
    engine: RiskEngine,
    now: datetime,
) -> ScanResult:
    """Report ladder violations and paper the locked package when it costs under 1."""
    violations = scan_ladder(brackets)
    if not violations:
        return ScanResult(violations=(), fill_ids=())
    ordered = sorted(
        (bracket for bracket in brackets if _ask(bracket.book) is not None),
        key=lambda bracket: bracket.floor,
    )
    fill_ids: list[str] = []
    for lower, higher in pairwise(ordered):
        if _ask(higher.book) is None or _ask(lower.book) is None:
            continue
        higher_ask = _ask(higher.book)
        lower_ask = _ask(lower.book)
        if higher_ask is None or lower_ask is None or higher_ask <= lower_ask:
            continue
        package = _locked_intents(lower, higher, now=ensure_utc(now))
        if package is None or not _edge_covers_fees(lower, higher, schedule):
            continue
        fill_ids.extend(
            _submit_package(
                package,
                {lower.book.market_ticker: lower.book, higher.book.market_ticker: higher.book},
                ledger=ledger,
                broker=broker,
                engine=engine,
                now=ensure_utc(now),
            )
        )
    return ScanResult(violations=violations, fill_ids=tuple(fill_ids))


def _ask(book: OrderBook) -> Decimal | None:
    if book.is_crossed or book.best_ask is None:
        return None
    return book.best_ask.price


def _edge_covers_fees(lower: Bracket, higher: Bracket, schedule: FeeSchedule) -> bool:
    lower_ask = _ask(lower.book)
    higher_bid = None if higher.book.best_bid is None else higher.book.best_bid.price
    if lower_ask is None or higher_bid is None or higher.book.is_crossed:
        return False
    no_cost = ONE - higher_bid
    yes_fee = trade_fee(schedule, yes_price=lower_ask, quantity=_QTY, role=LiquidityRole.TAKER)
    no_fee = trade_fee(schedule, yes_price=higher_bid, quantity=_QTY, role=LiquidityRole.TAKER)
    return lower_ask + no_cost + yes_fee + no_fee < ONE


def _locked_intents(
    lower: Bracket,
    higher: Bracket,
    *,
    now: datetime,
) -> tuple[OrderIntent, OrderIntent] | None:
    lower_ask = _ask(lower.book)
    if lower_ask is None or higher.book.best_bid is None:
        return None
    bought_yes = OrderIntent(
        strategy_id="scanner",
        strategy_version=1,
        contract=Contract(market_ticker=lower.book.market_ticker, side=OutcomeSide.YES),
        yes_price=lower_ask,
        quantity=_QTY,
        time_in_force=TimeInForce.FILL_OR_KILL,
        decision_time=now,
        rationale="Buy the cheaper lower strike against a rich higher strike.",
    )
    bought_no = OrderIntent(
        strategy_id="scanner",
        strategy_version=1,
        contract=Contract(market_ticker=higher.book.market_ticker, side=OutcomeSide.NO),
        yes_price=higher.book.best_bid.price,
        quantity=_QTY,
        time_in_force=TimeInForce.FILL_OR_KILL,
        decision_time=now,
        rationale="Buy NO on the expensive higher strike.",
    )
    return bought_yes, bought_no


def _submit_package(
    intents: tuple[OrderIntent, OrderIntent],
    books: dict[str, OrderBook],
    *,
    ledger: Ledger,
    broker: PaperBroker,
    engine: RiskEngine,
    now: datetime,
) -> tuple[str, ...]:
    approved: list[ApprovedOrderIntent] = []
    for intent in intents:
        book = books[intent.contract.market_ticker]
        decision = engine.evaluate(
            intent,
            portfolio=ledger.snapshot(),
            book=book,
            now=now,
            event_deployed=ZERO,
            realized_pnl=ledger.realized_pnl,
            peak_equity=ledger.peak_equity,
            equity=ledger.equity(),
        )
        if decision.approved_quantity != intent.quantity:
            return ()
        try:
            approved.append(seal(intent, decision))
        except RiskRejectedError:
            return ()
    known = {fill.fill_id for fill in ledger.fills()}
    for approved_intent in approved:
        book = books[approved_intent.intent.contract.market_ticker]
        broker.submit(approved_intent, book, now=now)
    return tuple(fill.fill_id for fill in ledger.fills() if fill.fill_id not in known)
