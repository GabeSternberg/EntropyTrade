"""Shadow and paper mode against recorded prints. Live never starts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.domain.enums import FeeType, KalshiEnvironment, OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel, TradePrint
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.orders import OrderIntent
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.execution.shadow import (
    ShadowComparison,
    ShadowError,
    compare_shadow_and_paper,
    run_shadow,
)
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits

WHEN = datetime(2026, 10, 2, 15, tzinfo=UTC)
TICKER = "KXHIGHPHIL-26OCT02-T89"


def _book() -> OrderBook:
    return OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5")),),
        received_at=WHEN,
    )


def _print_at(price: str, when: datetime) -> TradePrint:
    return TradePrint(
        trade_id="t1",
        market_ticker=TICKER,
        yes_price=Decimal(price),
        quantity=Decimal("1.00"),
        taker_side=OutcomeSide.YES,
        executed_at=when,
        received_at=when,
    )


def _buy(book: OrderBook) -> OrderIntent | None:
    ask = book.best_ask
    if ask is None:
        return None
    return OrderIntent(
        strategy_id="shadow",
        strategy_version=1,
        contract=Contract(market_ticker=book.market_ticker, side=OutcomeSide.YES),
        yes_price=ask.price,
        quantity=Decimal("1.00"),
        time_in_force=TimeInForce.FILL_OR_KILL,
        decision_time=book.received_at,
    )


def _limits() -> RiskLimits:
    return RiskLimits(
        bankroll=Decimal("100"),
        per_trade=Decimal("100"),
        per_event=Decimal("100"),
        total_deployed=Decimal("100"),
        max_loss=Decimal("50"),
        max_drawdown=Decimal("50"),
        max_book_age_seconds=3600,
        min_liquidity=Decimal("1.00"),
        max_spread=Decimal("0.2000"),
        config_version="v1",
    )


def _schedule() -> FeeSchedule:
    return FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        quadratic_coefficient=Decimal(0),
    )


def _run(
    mode: TradingMode,
    prints: tuple[TradePrint, ...],
) -> tuple[Ledger, tuple[ShadowComparison, ...]]:
    ledger = Ledger(Decimal("100"), as_of=WHEN)
    rows = run_shadow(
        requested=mode,
        environment=KalshiEnvironment.PRODUCTION,
        process_env={},
        books=(_book(),),
        prints=prints,
        strategy=_buy,
        ledger=ledger,
        broker=PaperBroker(ledger, _schedule()),
        engine=RiskEngine(_limits()),
    )
    return ledger, rows


def test_live_does_not_start_even_when_the_flag_is_set() -> None:
    def boom(book: OrderBook) -> OrderIntent | None:
        raise AssertionError(book.market_ticker)

    ledger = Ledger(Decimal("100"), as_of=WHEN)
    with pytest.raises(ShadowError, match="submit"):
        run_shadow(
            requested=TradingMode.LIVE,
            environment=KalshiEnvironment.PRODUCTION,
            process_env={"ENTROPYTRADE_LIVE_TRADING_ENABLED": "true"},
            books=(_book(),),
            prints=(),
            strategy=boom,
            ledger=ledger,
            broker=PaperBroker(ledger, _schedule()),
            engine=RiskEngine(_limits()),
        )
    assert ledger.cash == Decimal("100")


def test_paper_fill_is_compared_with_the_next_print() -> None:
    later = _print_at("0.4500", WHEN + timedelta(minutes=1))
    ledger, rows = _run(TradingMode.PAPER, (later,))
    row = rows[0]
    assert ledger.cash == Decimal("99.60")
    assert row.filled is True
    assert row.price == Decimal("0.4000")
    assert row.next_print == Decimal("0.4500")
    assert row.difference == Decimal("0.0500")
    assert row.gap is False


def test_a_missing_print_is_a_gap_and_shadow_does_not_fill() -> None:
    ledger, rows = _run(TradingMode.SHADOW, ())
    row = rows[0]
    assert ledger.cash == Decimal("100")
    assert row.filled is False
    assert row.price == Decimal("0.4000")
    assert row.gap is True
    assert row.difference is None


def test_read_only_does_not_fill() -> None:
    ledger, rows = _run(TradingMode.READ_ONLY, (_print_at("0.4500", WHEN),))
    assert ledger.cash == Decimal("100")
    assert rows == ()


def test_shadow_and_paper_prices_are_recorded_apart() -> None:
    later = _book()
    later = OrderBook(
        market_ticker=TICKER,
        bids=later.bids,
        asks=later.asks,
        received_at=WHEN + timedelta(minutes=5),
    )

    def buy_wide(book: OrderBook) -> OrderIntent | None:
        if book.received_at != WHEN:
            return None
        return OrderIntent(
            strategy_id="shadow",
            strategy_version=1,
            contract=Contract(market_ticker=book.market_ticker, side=OutcomeSide.YES),
            yes_price=Decimal("0.5000"),
            quantity=Decimal("1.00"),
            time_in_force=TimeInForce.FILL_OR_KILL,
            decision_time=book.received_at,
        )

    rows = compare_shadow_and_paper(
        environment=KalshiEnvironment.PRODUCTION,
        process_env={},
        books=(_book(), later),
        prints=(),
        strategy=buy_wide,
        starting_cash=Decimal("100"),
        as_of=WHEN,
        schedule=_schedule(),
        engines=(RiskEngine(_limits()), RiskEngine(_limits())),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.market_ticker == TICKER
    assert row.paper_filled is True
    assert row.paper_price == Decimal("0.4000")
    assert row.shadow_price == Decimal("0.5000")
    assert row.difference == Decimal("-0.1000")


def test_the_runner_does_not_name_the_gateway() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/execution/shadow.py")
        .read_text(encoding="utf-8")
    )
    assert "KalshiGateway" not in text
    assert "submit_order" not in text
