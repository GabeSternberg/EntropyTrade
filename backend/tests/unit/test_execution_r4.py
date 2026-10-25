"""Chronology, capacity, exposure and faithful YES/NO strategy semantics."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from entropytrade.agents.fixture import demo_specs
from entropytrade.backtest.replay import (
    DecisionView,
    ReplayError,
    ReplayResult,
    Strategy,
    run_replay,
)
from entropytrade.domain.enums import FeeType, MarketResult, OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.domain.strategy import (
    ComparisonOp,
    EntryWindow,
    Predicate,
    RuleSet,
    SizingMethod,
    StrategySpec,
)
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.strategies.interpret import UnsupportedSpecError, compile_strategy

AT = datetime(2025, 1, 1, 12, tzinfo=UTC)
TICKER = "FAMILY-EVENT-T1"


def book(
    second: int = 0, *, ticker: str = TICKER, bid: str = ".3", ask: str = ".4", size: str = "10"
) -> OrderBook:
    return OrderBook(
        market_ticker=ticker,
        received_at=AT + timedelta(seconds=second),
        bids=(OrderBookLevel(price=Decimal(bid), quantity=Decimal(size)),),
        asks=(OrderBookLevel(price=Decimal(ask), quantity=Decimal(size)),),
    )


def schedule(coefficient: str = "0") -> FeeSchedule:
    return FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        quadratic_coefficient=Decimal(coefficient),
    )


def limits(*, event: str = "100", edge: Decimal | None = None) -> RiskLimits:
    return RiskLimits(
        bankroll=Decimal(100),
        per_trade=Decimal(100),
        per_event=Decimal(event),
        total_deployed=Decimal(100),
        max_loss=Decimal(100),
        max_drawdown=Decimal(100),
        max_book_age_seconds=3600,
        min_liquidity=Decimal(".01"),
        max_spread=Decimal(".99"),
        min_net_edge=edge,
        config_version="test",
    )


def feature(value: str = ".8", *, when: datetime = AT) -> FeatureObservation:
    return FeatureObservation(
        source_id="fixture",
        event_time=when,
        available_at=when,
        ingested_at=when,
        feature_name="model_yes_probability",
        feature_version="1",
        entity_id=TICKER,
        value=Decimal(value),
    )


def spec() -> StrategySpec:
    baseline = demo_specs()[0]
    return baseline.revalidated(
        market_universe=baseline.market_universe.revalidated(
            market_tickers=(TICKER,), series_tickers=(), event_tickers=()
        ),
        features=(),
        entry_rules=RuleSet(
            description="probability input",
            all_of=(
                Predicate(
                    feature="model_yes_probability", op=ComparisonOp.GE, threshold=Decimal(".1")
                ),
            ),
        ),
        exit_rules=RuleSet(
            description="hold to settlement",
            all_of=(Predicate(feature="settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),),
        ),
    )


def intent(when: datetime, ticker: str = TICKER) -> OrderIntent:
    return OrderIntent(
        intent_id=UUID(int=1 + int((when - AT).total_seconds()) + (100 if ticker != TICKER else 0)),
        strategy_id="test",
        strategy_version=1,
        contract=Contract(market_ticker=ticker, side=OutcomeSide.YES),
        yes_price=Decimal(".5"),
        quantity=Decimal(1),
        time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
        decision_time=when,
    )


def replay(
    books: tuple[OrderBook, ...],
    strategy: Strategy,
    *,
    latency: int = 0,
    age: int = 60,
    end: int = 100,
    event_cap: str = "100",
    records: tuple[FeatureObservation, ...] = (),
) -> tuple[Ledger, ReplayResult]:
    ledger = Ledger(Decimal(100), as_of=AT)
    result = run_replay(
        books=books,
        records=records,
        strategy=strategy,
        ledger=ledger,
        broker=PaperBroker(ledger, schedule()),
        engine=RiskEngine(limits(event=event_cap)),
        latency=timedelta(seconds=latency),
        max_book_age=timedelta(seconds=age),
        window=SplitWindow(split=SampleSplit.VALIDATION, start=AT, end=AT + timedelta(seconds=end)),
    )
    return ledger, result


def test_later_book_is_not_selected_for_an_earlier_execution() -> None:
    ledger, result = replay(
        (book(), book(10, ask=".35")),
        lambda v, b: intent(b.received_at) if b.received_at == AT else None,
        latency=5,
        age=0,
    )
    assert not ledger.fills()
    assert any(a["status"] == "unfilled_stale_or_closed" for a in result.audit)


def test_future_fills_do_not_change_an_intermediate_decision() -> None:
    observed: list[tuple[datetime, int, Decimal]] = []

    def strategy(view: DecisionView, snapshot: OrderBook) -> OrderIntent | None:
        assert view.ledger is not None
        observed.append(
            (view.decision_time, len(view.ledger.positions), view.ledger.resting_collateral)
        )
        return intent(snapshot.received_at) if snapshot.received_at == AT else None

    ledger, _ = replay((book(), book(1)), strategy, latency=10)
    assert observed[1][1] == 0
    assert observed[1][2] > 0
    assert ledger.fills()[0].executed_at == AT + timedelta(seconds=10)


def test_execution_never_crosses_split_end() -> None:
    ledger, result = replay(
        (book(), book(10)), lambda v, b: intent(b.received_at), latency=5, end=5
    )
    assert ledger.fills() == ()
    assert result.audit[0]["status"] == "outside_execution_window"


@given(st.integers(2, 12))
def test_repeated_identical_books_cannot_reuse_consumed_depth(count: int) -> None:
    ledger, _ = replay(
        tuple(book(i, size="1") for i in range(count)), lambda v, b: intent(b.received_at)
    )
    assert sum((f.quantity for f in ledger.fills()), Decimal(0)) == 1


def test_pending_and_filled_event_exposure_is_not_zero() -> None:
    ledger, _ = replay(
        (book(ticker=TICKER), book(ticker="FAMILY-EVENT-T2")),
        lambda v, b: intent(b.received_at, b.market_ticker),
        latency=5,
        event_cap=".5",
    )
    assert sum((p.total_cost for p in ledger.positions), Decimal(0)) <= Decimal(".5")
    assert len(ledger.fills()) == 1


def test_crossed_and_conflicting_books_cannot_fill() -> None:
    ledger, _ = replay((book(bid=".5", ask=".4"),), lambda v, b: intent(b.received_at))
    assert not ledger.fills()
    with pytest.raises(ReplayError, match="conflicting"):
        replay((book(), book(ask=".5")), lambda v, b: None)


def test_no_side_probability_cost_and_fees_use_complements() -> None:
    selected = spec().revalidated(side=OutcomeSide.NO, minimum_edge=Decimal(".05"))
    view = DecisionView((feature(".2"),), AT, schedule=schedule(".07"))
    trade = compile_strategy(selected)(view, book(bid=".35", ask=".4"))
    assert trade is not None
    assert trade.edge is not None
    assert trade.contract.side is OutcomeSide.NO
    assert trade.yes_price == Decimal(".35")
    assert trade.price_per_contract == Decimal(".65")
    assert trade.edge.outcome_probability == Decimal(".8")
    assert trade.edge.net_edge < Decimal(".15")


def test_positive_gross_edge_cannot_ignore_fees() -> None:
    selected = spec().revalidated(minimum_edge=Decimal(".005"))
    assert (
        compile_strategy(selected)(
            DecisionView((feature(".41"),), AT, schedule=schedule(".07")), book()
        )
        is None
    )


def test_fixed_dollar_budget_includes_fees_and_max_position() -> None:
    selected = spec().revalidated(
        position_sizing=spec().position_sizing.revalidated(
            method=SizingMethod.FIXED_DOLLARS,
            contracts=None,
            dollars=Decimal(".50"),
            max_contracts=Decimal(5),
        )
    )
    trade = compile_strategy(selected)(
        DecisionView((feature(".9"),), AT, schedule=schedule(".07")), book()
    )
    assert trade is not None
    from entropytrade.domain.enums import LiquidityRole

    assert trade.max_cost + trade_fee(
        schedule(".07"),
        yes_price=trade.yes_price,
        quantity=trade.quantity,
        role=LiquidityRole.TAKER,
    ) <= Decimal(".5")
    capped = compile_strategy(spec())(
        DecisionView(
            (feature(),), AT, schedule=schedule(), pending={(TICKER, OutcomeSide.YES): Decimal(1)}
        ),
        book(),
    )
    assert capped is None


def test_entry_windows_prices_spread_and_feature_versions_are_enforced() -> None:
    view = DecisionView((feature(),), AT, schedule=schedule())
    assert (
        compile_strategy(spec().revalidated(max_entry_price=Decimal(".39")))(view, book()) is None
    )
    assert (
        compile_strategy(
            spec().revalidated(entry_window=EntryWindow(start=AT + timedelta(seconds=1)))
        )(view, book())
        is None
    )
    assert (
        compile_strategy(
            spec().revalidated(execution=spec().execution.revalidated(max_spread=Decimal(".05")))
        )(view, book())
        is None
    )
    assert (
        compile_strategy(spec().revalidated(min_displayed_quantity=Decimal(11)))(view, book())
        is None
    )
    assert (
        compile_strategy(spec())(
            DecisionView((feature(when=AT + timedelta(seconds=1)),), AT, schedule=schedule()),
            book(),
        )
        is None
    )


def test_simple_exit_reduces_instead_of_flipping_and_settlement_is_chronological() -> None:
    selected = spec().revalidated(
        exit_mode="predicate",
        exit_rules=RuleSet(
            description="exit at bid",
            all_of=(Predicate(feature="yes_bid", op=ComparisonOp.GE, threshold=Decimal(".7")),),
        ),
    )
    ledger = Ledger(Decimal(100), as_of=AT)
    result = run_replay(
        books=(book(), book(1, bid=".8", ask=".9")),
        records=(feature(),),
        strategy=compile_strategy(selected),
        ledger=ledger,
        broker=PaperBroker(ledger, schedule()),
        engine=RiskEngine(limits(edge=selected.minimum_edge)),
        latency=timedelta(0),
        window=SplitWindow(split=SampleSplit.VALIDATION, start=AT, end=AT + timedelta(seconds=10)),
        settlements=((AT + timedelta(seconds=2), TICKER, MarketResult.YES),),
    )
    assert len(ledger.fills()) == 2
    assert not ledger.positions
    assert ledger.cash == Decimal("100.4")
    assert sum(result.event_pnl.values()) == ledger.realized_pnl


def test_unsupported_fields_are_not_silently_accepted() -> None:
    with pytest.raises(UnsupportedSpecError, match="hedging"):
        compile_strategy(spec().revalidated(hedging_rules="dynamic hedge"))
    with pytest.raises(UnsupportedSpecError, match="immediate"):
        compile_strategy(
            spec().revalidated(
                execution=spec().execution.revalidated(time_in_force=TimeInForce.GOOD_TILL_CANCELED)
            )
        )
    with pytest.raises(UnsupportedSpecError, match="fee schedule"):
        compile_strategy(spec())(DecisionView((feature(),), AT), book())
    with pytest.raises(UnsupportedSpecError, match="lot-level clocks"):
        compile_strategy(spec().revalidated(maximum_holding_period_seconds=60))


def test_entry_window_prevents_an_order_filling_after_its_deadline() -> None:
    selected = spec().revalidated(entry_window=EntryWindow(end=AT + timedelta(seconds=1)))
    ledger, result = replay((book(),), compile_strategy(selected), latency=2, records=(feature(),))
    assert not ledger.fills()
    assert result.audit[-1]["status"] == "unfilled_stale_or_closed"
