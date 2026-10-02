"""Point-in-time replay: leakage, latency, and a stable artifact hash."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from entropytrade.backtest.replay import DecisionView, ReplayError, run_replay, run_walk_forward
from entropytrade.domain.enums import (
    ExecutionFidelity,
    FeeType,
    FillScenario,
    MarketResult,
    OutcomeSide,
    TimeInForce,
)
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import BacktestRun, SampleSplit, SplitWindow
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from tests.support import utc

TICKER = "KXHIGHPHIL-26OCT02-T89"
HASH = "sha256:" + "ab" * 32
TRAIN_START = utc(2026, 10, 2, 10)
TRAIN_END = utc(2026, 10, 2, 12)
VALID_END = utc(2026, 10, 2, 14)
HOLD_END = utc(2026, 10, 2, 16)


def _level(price: str, quantity: str = "5.00") -> OrderBookLevel:
    return OrderBookLevel(price=Decimal(price), quantity=Decimal(quantity))


def _book(hour: int, *, ask: str, bid: str = "0.4000") -> OrderBook:
    return OrderBook(
        market_ticker=TICKER,
        bids=(_level(bid),),
        asks=(_level(ask),),
        received_at=utc(2026, 10, 2, hour),
    )


def _feature(hour: int, value: str) -> FeatureObservation:
    stamp = utc(2026, 10, 2, hour)
    return FeatureObservation(
        source_id="station",
        event_time=stamp,
        available_at=stamp,
        ingested_at=stamp,
        feature_name="settled_value",
        feature_version="1",
        entity_id=TICKER,
        value=Decimal(value),
    )


def _intent(when: object) -> OrderIntent:
    return OrderIntent(
        intent_id=UUID(int=1),
        strategy_id="baseline",
        strategy_version=1,
        contract=Contract(market_ticker=TICKER, side=OutcomeSide.YES),
        yes_price=Decimal("0.5000"),
        quantity=Decimal("1.00"),
        time_in_force=TimeInForce.GOOD_TILL_CANCELED,
        decision_time=when,  # type: ignore[arg-type]
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


def _window(split: SampleSplit, start: object, end: object) -> SplitWindow:
    return SplitWindow(split=split, start=start, end=end)  # type: ignore[arg-type]


def _run_pair(
    strategy: object,
    books: tuple[OrderBook, ...],
    records: tuple[FeatureObservation, ...],
) -> object:
    ledger = Ledger(Decimal("100"), as_of=TRAIN_START)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=ZERO,
        ),
    )
    window = _window(SampleSplit.TRAIN, TRAIN_START, TRAIN_END)
    return run_replay(
        books=books,
        records=records,
        strategy=strategy,  # type: ignore[arg-type]
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(_limits()),
        latency=timedelta(0),
        window=window,
    )


def test_a_future_settlement_is_invisible_and_does_not_trade() -> None:
    records = (_feature(9, "0"), _feature(15, "1"))
    seen: list[Decimal | None] = []

    def leaky(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        row = view.feature("settled_value", TICKER)
        seen.append(None if row is None or row.value is None else row.value)
        if row is not None and row.value == Decimal(1):
            return _intent(book.received_at)
        return None

    result = _run_pair(leaky, (_book(10, ask="0.4400"),), records)
    assert seen == [Decimal(0)]
    assert result.fill_ids == ()  # type: ignore[attr-defined]


def test_latency_does_not_fill_at_a_better_price_than_the_decision_book() -> None:
    def buy_once(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        del view
        if book.received_at != TRAIN_START:
            return None
        return _intent(book.received_at)

    ledger = Ledger(Decimal("100"), as_of=TRAIN_START)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=ZERO,
        ),
    )
    result = run_replay(
        books=(_book(10, ask="0.5000"), _book(11, ask="0.4000", bid="0.3000")),
        records=(),
        strategy=buy_once,
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(_limits()),
        latency=timedelta(hours=1),
        window=_window(SampleSplit.TRAIN, TRAIN_START, TRAIN_END),
    )
    position = ledger.position(TICKER)
    assert position is not None
    assert position.total_cost == Decimal("0.50")
    assert result.fill_ids != ()


def test_the_same_recording_hashes_to_the_same_artifact() -> None:
    def buy_once(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        del view
        if book.received_at != TRAIN_START:
            return None
        return _intent(book.received_at)

    books = (_book(10, ask="0.4400"),)
    first = _run_pair(buy_once, books, ())
    second = _run_pair(buy_once, books, ())
    run = _provenance()
    assert first.digest(run) == second.digest(run)  # type: ignore[attr-defined]


def test_walk_forward_does_not_call_the_strategy_on_the_holdout() -> None:
    seen: list[object] = []

    def watch(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        del view
        seen.append(book.received_at)
        return None

    ledger = Ledger(Decimal("100"), as_of=TRAIN_START)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=ZERO,
        ),
    )
    splits = (
        _window(SampleSplit.TRAIN, TRAIN_START, TRAIN_END),
        _window(SampleSplit.VALIDATION, TRAIN_END, VALID_END),
        _window(SampleSplit.HOLDOUT, VALID_END, HOLD_END),
    )
    run_walk_forward(
        books=(_book(10, ask="0.4400"), _book(12, ask="0.4400"), _book(14, ask="0.4400")),
        records=(_feature(15, "1"),),
        strategy=watch,
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(_limits()),
        latency=timedelta(0),
        splits=splits,
    )
    assert utc(2026, 10, 2, 14) not in seen
    assert TRAIN_START in seen
    with pytest.raises(ReplayError, match="holdout"):
        run_replay(
            books=(),
            records=(),
            strategy=watch,
            ledger=ledger,
            broker=broker,
            engine=RiskEngine(_limits()),
            latency=timedelta(0),
            window=splits[2],
        )


def test_settlement_inside_the_window_flattens_the_position() -> None:
    def buy_once(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        del view
        if book.received_at != TRAIN_START:
            return None
        return _intent(book.received_at)

    ledger = Ledger(Decimal("100"), as_of=TRAIN_START)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=ZERO,
        ),
    )
    run_replay(
        books=(_book(10, ask="0.4400"),),
        records=(),
        strategy=buy_once,
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(_limits()),
        latency=timedelta(0),
        window=_window(SampleSplit.TRAIN, TRAIN_START, TRAIN_END),
        settlements=((utc(2026, 10, 2, 11), TICKER, MarketResult.YES),),
    )
    assert ledger.position(TICKER) is None
    assert ledger.cash == Decimal("100.56")


def _provenance() -> BacktestRun:
    return BacktestRun(
        strategy_id="baseline",
        strategy_version=1,
        strategy_spec_hash=HASH,
        config_hash=HASH,
        dataset_manifest_hash=HASH,
        feature_version="1",
        fee_model=FeeModelRef(
            version="kxhigh",
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            effective_from=TRAIN_START,
        ),
        execution_model_version="paper-1",
        fill_scenario=FillScenario.BASE,
        execution_fidelity=ExecutionFidelity.ORDER_BOOK,
        random_seed=1,
        start=TRAIN_START,
        end=HOLD_END,
        splits=(
            _window(SampleSplit.TRAIN, TRAIN_START, TRAIN_END),
            _window(SampleSplit.VALIDATION, TRAIN_END, VALID_END),
            _window(SampleSplit.HOLDOUT, VALID_END, HOLD_END),
        ),
        created_at=TRAIN_START,
    )
