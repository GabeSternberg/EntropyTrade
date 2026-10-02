"""Structural scanner on executable asks. Paper fills stop when risk says no."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import FeeType
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.exchange.frames import BookLevel, BookSnapshotFrame
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.strategies.scanner import (
    Bracket,
    ThresholdMark,
    book_from_snapshot,
    complement_gap,
    paper_ladder,
    scan_exhaustive,
    scan_ladder,
    scan_thresholds,
)


def _book(ticker: str, bid: str, ask: str) -> OrderBook:
    return OrderBook(
        market_ticker=ticker,
        bids=(OrderBookLevel(price=Decimal(bid), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal(ask), quantity=Decimal("5")),),
        received_at=datetime(2026, 10, 2, 15, tzinfo=UTC),
    )


def _schedule(coefficient: str) -> FeeSchedule:
    return FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        quadratic_coefficient=Decimal(coefficient),
    )


def _engine(max_loss: str = "50") -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            bankroll=Decimal("100"),
            per_trade=Decimal("100"),
            per_event=Decimal("100"),
            total_deployed=Decimal("100"),
            max_loss=Decimal(max_loss),
            max_drawdown=Decimal("50"),
            max_book_age_seconds=3600,
            min_liquidity=Decimal("1.00"),
            max_spread=Decimal("0.2000"),
            config_version="v1",
        )
    )


def _ladder() -> tuple[Bracket, Bracket]:
    return (
        Bracket(floor=Decimal(89), book=_book("KXHIGHPHIL-26OCT02-T89", "0.2000", "0.3000")),
        Bracket(floor=Decimal(90), book=_book("KXHIGHPHIL-26OCT02-T90", "0.8000", "0.9000")),
    )


def test_a_rich_higher_strike_is_a_violation_and_a_flat_ladder_is_not() -> None:
    found = scan_ladder(_ladder())
    assert len(found) == 1
    assert found[0].kind == "monotonic"
    calm = (
        Bracket(floor=Decimal(89), book=_book("A", "0.4000", "0.5000")),
        Bracket(floor=Decimal(90), book=_book("B", "0.2000", "0.3000")),
    )
    assert scan_ladder(calm) == ()


def test_a_trade_or_candle_is_not_an_executable_ladder() -> None:
    inverted = (
        ThresholdMark(floor=Decimal(80), ticker="T80", non_executable=True),
        ThresholdMark(floor=Decimal(87), ticker="T87", non_executable=True),
    )
    found = scan_thresholds(inverted)
    assert [item.kind for item in found] == ["non_executable", "non_executable"]
    books = (
        ThresholdMark(floor=Decimal(80), ticker="T80", book=_book("T80", "0.2000", "0.3000")),
        ThresholdMark(floor=Decimal(87), ticker="T87", book=_book("T87", "0.8000", "0.9000")),
    )
    priced = scan_thresholds(books)
    assert [item.kind for item in priced] == ["monotonic"]


def test_a_crossed_book_is_not_a_quote() -> None:
    crossed = (
        Bracket(floor=Decimal(89), book=_book("A", "0.2000", "0.3000")),
        Bracket(floor=Decimal(90), book=_book("B", "0.5000", "0.5000")),
    )
    assert scan_ladder(crossed) == ()
    assert complement_gap(_book("A", "0.3000", "0.4000")) is None
    assert complement_gap(_book("A", "0.5000", "0.4000")) is None


def test_exhaustive_asks_under_a_dollar_are_flagged() -> None:
    cheap = (_book("YES-A", "0.1000", "0.4000"), _book("YES-B", "0.1000", "0.4000"))
    found = scan_exhaustive(cheap)
    assert len(found) == 1
    assert found[0].kind == "exclusive"
    full = (_book("YES-A", "0.2000", "0.6000"), _book("YES-B", "0.2000", "0.5000"))
    assert scan_exhaustive(full) == ()


def test_a_snapshot_frame_is_enough_to_scan() -> None:
    when = datetime(2026, 10, 2, 15, tzinfo=UTC)
    frame = BookSnapshotFrame(
        sid=1,
        seq=1,
        market_ticker="KXHIGHPHIL-26OCT02-T89",
        yes=(BookLevel(price=Decimal("0.2000"), quantity=Decimal("5")),),
        no=(BookLevel(price=Decimal("0.7000"), quantity=Decimal("5")),),
        received_at=when,
    )
    book = book_from_snapshot(frame)
    assert book.best_ask is not None
    assert book.best_ask.price == Decimal("0.3000")
    higher = Bracket(floor=Decimal(90), book=_book("KXHIGHPHIL-26OCT02-T90", "0.8000", "0.9000"))
    found = scan_ladder((Bracket(floor=Decimal(89), book=book), higher))
    assert found[0].tickers[0] == "KXHIGHPHIL-26OCT02-T89"


def test_paper_package_fills_only_when_risk_and_fees_allow() -> None:
    when = datetime(2026, 10, 2, 15, tzinfo=UTC)
    ledger = Ledger(Decimal("100"), as_of=when)
    result = paper_ladder(
        _ladder(),
        schedule=_schedule("0"),
        ledger=ledger,
        broker=PaperBroker(ledger, _schedule("0")),
        engine=_engine(),
        now=when,
    )
    assert result.violations
    assert len(result.fill_ids) == 2
    assert ledger.cash == Decimal("99.50")

    blocked = Ledger(Decimal("100"), as_of=when)
    refused = paper_ladder(
        _ladder(),
        schedule=_schedule("0"),
        ledger=blocked,
        broker=PaperBroker(blocked, _schedule("0")),
        engine=_engine("0"),
        now=when,
    )
    assert refused.violations
    assert refused.fill_ids == ()
    assert blocked.cash == Decimal("100")

    priced = Ledger(Decimal("100"), as_of=when)
    no_edge = paper_ladder(
        _ladder(),
        schedule=_schedule("2"),
        ledger=priced,
        broker=PaperBroker(priced, _schedule("2")),
        engine=_engine(),
        now=when,
    )
    assert no_edge.violations
    assert no_edge.fill_ids == ()
    assert priced.cash == Decimal("100")


def test_the_scanner_does_not_name_the_gateway() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/strategies/scanner.py")
        .read_text(encoding="utf-8")
    )
    assert "KalshiGateway" not in text
    assert "submit_order" not in text
