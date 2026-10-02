"""Paper fills, the risk gate, and restart-safe accounting."""

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from entropytrade.domain.enums import (
    FeeType,
    LiquidityRole,
    MarketResult,
    OutcomeSide,
    TimeInForce,
)
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.orders import ApprovedOrderIntent, Order, OrderIntent, OrderState
from entropytrade.domain.portfolio import PortfolioSnapshot, SnapshotSource
from entropytrade.domain.risk import RiskCheckResult, RiskDecision
from entropytrade.domain.signals import EdgeEstimate
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.execution.paper import PaperBroker, PaperBrokerError
from entropytrade.execution.reconcile import ReconcileMismatchError, adopt_order, compare_snapshots
from entropytrade.portfolio.ledger import Ledger
from entropytrade.portfolio.store import LedgerStore
from entropytrade.risk.engine import (
    RiskEngine,
    RiskLimits,
    RiskRejectedError,
    halt_sentinel,
    seal,
)
from tests.support import utc

TICKER = "KXHIGHPHIL-26OCT02-T89"
NOW = utc(2026, 10, 2, 15)
WHEN = utc(2026, 10, 2, 15)


def _book(*, ask: str = "0.4400", ask_qty: str = "3.00", bid: str = "0.4000") -> OrderBook:
    return OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal(bid), quantity=Decimal("10.00")),),
        asks=(
            OrderBookLevel(price=Decimal(ask), quantity=Decimal(ask_qty)),
            OrderBookLevel(price=Decimal("0.5000"), quantity=Decimal("10.00")),
        ),
        received_at=WHEN,
    )


def _schedule(*, maker_pays: bool = False, coefficient: str = "0") -> FeeSchedule:
    return FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=maker_pays,
        quadratic_coefficient=Decimal(coefficient),
    )


def _intent(
    *,
    side: OutcomeSide = OutcomeSide.YES,
    price: str = "0.4500",
    quantity: str = "5.00",
    time_in_force: TimeInForce = TimeInForce.GOOD_TILL_CANCELED,
    post_only: bool = False,
    reduce_only: bool = False,
    edge: EdgeEstimate | None = None,
) -> OrderIntent:
    return OrderIntent(
        strategy_id="baseline",
        strategy_version=1,
        contract=Contract(market_ticker=TICKER, side=side),
        yes_price=Decimal(price),
        quantity=Decimal(quantity),
        time_in_force=time_in_force,
        post_only=post_only,
        reduce_only=reduce_only,
        decision_time=NOW,
        edge=edge,
    )


def _approve(intent: OrderIntent, quantity: str | None = None) -> ApprovedOrderIntent:
    approved = intent.quantity if quantity is None else Decimal(quantity)
    decision = RiskDecision(
        intent_id=intent.intent_id,
        approved=True,
        approved_quantity=approved,
        checks=(RiskCheckResult(check_name="test", passed=True),),
        risk_config_version="test",
        decided_at=NOW,
    )
    return ApprovedOrderIntent(intent=intent, decision=decision)


def _limits() -> RiskLimits:
    return RiskLimits(
        bankroll=Decimal("100"),
        per_trade=Decimal("100"),
        per_event=Decimal("100"),
        total_deployed=Decimal("100"),
        max_loss=Decimal("50"),
        max_drawdown=Decimal("50"),
        max_book_age_seconds=60,
        min_liquidity=Decimal("1.00"),
        max_spread=Decimal("0.2000"),
        config_version="v1",
    )


def test_equity_is_starting_cash_plus_realized_pnl_after_a_round_trip() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    broker = PaperBroker(ledger, _schedule())
    bought = broker.submit(_approve(_intent(quantity="2.00", price="0.4400")), _book(), now=NOW)
    assert bought.state is OrderState.FILLED
    assert ledger.position(TICKER) is not None
    closed = broker.submit(
        _approve(_intent(side=OutcomeSide.NO, price="0.4000", quantity="2.00")),
        _book(),
        now=NOW,
    )
    assert closed.state is OrderState.FILLED
    assert ledger.position(TICKER) is None
    assert ledger.equity() == ledger.starting_cash + ledger.realized_pnl
    assert ledger.equity() < Decimal("100")


def test_settlement_pays_yes_holders_and_flattens_the_position() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    PaperBroker(ledger, _schedule()).submit(
        _approve(_intent(quantity="2.00", price="0.4400")),
        _book(),
        now=NOW,
    )
    settlement = ledger.settle(TICKER, MarketResult.YES, at=NOW)
    assert settlement.revenue == Decimal("2")
    assert ledger.position(TICKER) is None
    assert ledger.cash == Decimal("101.12")
    assert ledger.equity() == ledger.starting_cash + ledger.realized_pnl


def test_the_same_fill_does_not_apply_twice_after_restart(tmp_path: Path) -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    broker = PaperBroker(ledger, _schedule())
    broker.submit(_approve(_intent(quantity="1.00", price="0.4400")), _book(), now=NOW)
    cash = ledger.cash
    store = LedgerStore(tmp_path / "ledger.sqlite")
    store.save(ledger)
    store.close()
    reopened = LedgerStore(tmp_path / "ledger.sqlite")
    loaded = reopened.load()
    assert loaded is not None
    fill = loaded.fills()[0]
    assert loaded.apply_fill(fill) is False
    assert loaded.cash == cash
    assert loaded.equity() == loaded.starting_cash + loaded.realized_pnl
    reopened.close()


def test_taker_walks_the_book_and_rests_the_remainder() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    order = PaperBroker(ledger, _schedule()).submit(_approve(_intent()), _book(), now=NOW)
    assert order.state is OrderState.PARTIALLY_FILLED
    assert order.filled_quantity == Decimal("3.00")
    position = ledger.position(TICKER)
    assert position is not None
    assert position.quantity == Decimal("3.00")
    assert ledger.resting_collateral == Decimal("0.900000")


def test_fill_or_kill_cancels_when_the_book_is_short() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    intent = _intent(time_in_force=TimeInForce.FILL_OR_KILL)
    order = PaperBroker(ledger, _schedule()).submit(_approve(intent), _book(), now=NOW)
    assert order.state is OrderState.CANCELLED
    assert ledger.position(TICKER) is None
    assert ledger.cash == Decimal("100")


def test_post_only_rests_behind_the_ask_and_rejects_a_cross() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    broker = PaperBroker(ledger, _schedule())
    resting = broker.submit(
        _approve(_intent(price="0.4000", post_only=True, quantity="1.00")),
        _book(),
        now=NOW,
    )
    assert resting.state is OrderState.RESTING
    assert ledger.position(TICKER) is None
    crossed = broker.submit(
        _approve(_intent(price="0.4400", post_only=True, quantity="1.00")),
        _book(),
        now=NOW,
    )
    assert crossed.state is OrderState.REJECTED


def test_reduce_only_cannot_open_and_can_close() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    broker = PaperBroker(ledger, _schedule())
    broker.submit(_approve(_intent(quantity="2.00", price="0.4400")), _book(), now=NOW)
    rejected = broker.submit(
        _approve(_intent(quantity="1.00", price="0.4000", reduce_only=True)),
        _book(),
        now=NOW,
    )
    assert rejected.state is OrderState.REJECTED
    closed = broker.submit(
        _approve(
            _intent(
                side=OutcomeSide.NO,
                price="0.4000",
                quantity="5.00",
                reduce_only=True,
                time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL,
            )
        ),
        _book(),
        now=NOW,
    )
    assert closed.filled_quantity == Decimal("2.00")
    assert closed.state is OrderState.CANCELLED
    assert ledger.position(TICKER) is None


def test_kxhigh_style_maker_fee_is_zero_and_the_coefficient_is_an_input() -> None:
    schedule = _schedule(coefficient="0.02")
    assert (
        trade_fee(
            schedule,
            yes_price=Decimal("0.5000"),
            quantity=Decimal("10.00"),
            role=LiquidityRole.MAKER,
        )
        == ZERO
    )
    taker = trade_fee(
        schedule,
        yes_price=Decimal("0.5000"),
        quantity=Decimal("10.00"),
        role=LiquidityRole.TAKER,
    )
    other_side = trade_fee(
        schedule,
        yes_price=Decimal("0.5000"),
        quantity=Decimal("10.00"),
        role=LiquidityRole.TAKER,
    )
    assert taker == other_side
    assert taker == Decimal("0.050000")


def test_raw_intent_cannot_reach_the_broker() -> None:
    broker = PaperBroker(Ledger(Decimal("100"), as_of=NOW), _schedule())
    submit = cast("Callable[..., Order]", broker.submit)
    with pytest.raises(PaperBrokerError, match="approved"):
        submit(_intent(), _book(), now=NOW)


def test_a_rejected_decision_cannot_be_sealed() -> None:
    intent = _intent(quantity="1.00", price="0.4500")
    engine = RiskEngine(_limits())
    engine.kill()
    decision = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )
    assert not decision.approved
    assert "kill_switch" in {check.check_name for check in decision.failed_checks}
    with pytest.raises(RiskRejectedError):
        seal(intent, decision)


def test_risk_clips_to_the_per_trade_cap_and_blocks_a_wide_spread() -> None:
    intent = _intent(quantity="10.00", price="0.4500")
    limits = _limits().revalidated(per_trade=Decimal("1"))
    engine = RiskEngine(limits)
    decision = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(ask_qty="10.00"),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )
    assert decision.approved
    assert decision.approved_quantity < intent.quantity
    sealed = seal(intent, decision)
    wide = _book()
    wide = OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.1000"), quantity=Decimal("10.00")),),
        asks=(OrderBookLevel(price=Decimal("0.5000"), quantity=Decimal("10.00")),),
        received_at=WHEN,
    )
    blocked = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=wide,
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )
    assert not blocked.approved
    assert any(check.check_name == "max_spread" and not check.passed for check in blocked.checks)
    assert sealed.quantity == decision.approved_quantity


def test_stale_book_and_drawdown_reject() -> None:
    intent = _intent(quantity="1.00", price="0.4500")
    engine = RiskEngine(_limits())
    stale = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=utc(2026, 10, 2, 16),
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )
    assert any(check.check_name == "stale_book" and not check.passed for check in stale.checks)
    drawn = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=Decimal("-60"),
        peak_equity=Decimal("100"),
        equity=Decimal("40"),
    )
    assert any(check.check_name == "drawdown" and not check.passed for check in drawn.checks)


def _decide(intent: OrderIntent, limits: RiskLimits) -> RiskDecision:
    return RiskEngine(limits).evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )


def test_min_net_edge_rejects_a_missing_or_thin_estimate() -> None:
    limits = _limits().model_copy(update={"min_net_edge": Decimal(0)})
    missing = _decide(_intent(quantity="1.00", price="0.4500"), limits)
    assert any(check.check_name == "min_net_edge" and not check.passed for check in missing.checks)
    assert not missing.approved
    thin = _decide(
        _intent(
            quantity="1.00",
            price="0.4500",
            edge=EdgeEstimate(
                outcome_probability=Decimal("0.70"),
                price_per_contract=Decimal("0.6900"),
                fee_per_contract=Decimal("0.020000"),
            ),
        ),
        limits,
    )
    assert any(check.check_name == "min_net_edge" and not check.passed for check in thin.checks)
    wide = _decide(
        _intent(
            quantity="1.00",
            price="0.4500",
            edge=EdgeEstimate(
                outcome_probability=Decimal("0.80"),
                price_per_contract=Decimal("0.4000"),
                fee_per_contract=Decimal(0),
            ),
        ),
        limits,
    )
    assert wide.approved
    untouched = _decide(_intent(quantity="1.00", price="0.4500"), _limits())
    assert all(check.check_name != "min_net_edge" for check in untouched.checks)
    assert untouched.approved


def test_max_open_orders_leaves_room_for_one_more() -> None:
    limits = _limits().model_copy(update={"max_open_orders": 1})
    intent = _intent(quantity="1.00", price="0.4500")
    full = RiskEngine(limits).evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
        open_orders=1,
    )
    assert any(check.check_name == "max_open_orders" and not check.passed for check in full.checks)
    assert not full.approved
    room = RiskEngine(_limits().model_copy(update={"max_open_orders": 2})).evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
        open_orders=1,
    )
    assert room.approved
    unset = _decide(intent, _limits())
    assert all(check.check_name != "max_open_orders" for check in unset.checks)


def test_order_rate_rejects_a_full_window() -> None:
    intent = _intent(quantity="1.00", price="0.4500")
    limited = _limits().model_copy(update={"max_order_rate": 1})
    full = RiskEngine(limited).evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
        orders_in_window=1,
    )
    assert any(check.check_name == "order_rate" and not check.passed for check in full.checks)
    assert not full.approved
    room = RiskEngine(_limits().model_copy(update={"max_order_rate": 2})).evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
        orders_in_window=1,
    )
    assert room.approved
    unset = _decide(intent, _limits())
    assert all(check.check_name != "order_rate" for check in unset.checks)


def test_max_slippage_rejects_a_missing_or_large_reserve() -> None:
    limits = _limits().model_copy(update={"max_slippage": Decimal("0.010000")})
    intent = _intent(quantity="1.00", price="0.4500")
    missing = _decide(intent, limits)
    assert any(check.check_name == "max_slippage" and not check.passed for check in missing.checks)
    assert not missing.approved
    wide = _decide(
        _intent(
            quantity="1.00",
            price="0.4500",
            edge=EdgeEstimate(
                outcome_probability=Decimal("0.80"),
                price_per_contract=Decimal("0.4000"),
                fee_per_contract=Decimal(0),
                expected_slippage=Decimal("0.020000"),
            ),
        ),
        limits,
    )
    assert any(check.check_name == "max_slippage" and not check.passed for check in wide.checks)
    tight = _decide(
        _intent(
            quantity="1.00",
            price="0.4500",
            edge=EdgeEstimate(
                outcome_probability=Decimal("0.80"),
                price_per_contract=Decimal("0.4000"),
                fee_per_contract=Decimal(0),
                expected_slippage=Decimal("0.010000"),
            ),
        ),
        limits,
    )
    assert tight.approved
    unset = _decide(intent, _limits())
    assert all(check.check_name != "max_slippage" for check in unset.checks)


def test_halt_file_and_the_environment_flag_reject_new_orders(tmp_path: Path) -> None:
    intent = _intent(quantity="1.00", price="0.4500")
    halt = halt_sentinel(tmp_path)
    assert halt.name == "HALT"
    halt.write_text("stop", encoding="utf-8")
    engine = RiskEngine(_limits(), halt_file=halt)
    decision = engine.evaluate(
        intent,
        portfolio=Ledger(Decimal("100"), as_of=NOW).snapshot(),
        book=_book(),
        now=NOW,
        event_deployed=ZERO,
        realized_pnl=ZERO,
        peak_equity=Decimal("100"),
        equity=Decimal("100"),
    )
    assert engine.halted()
    assert not decision.approved
    engine.resume()
    assert engine.halted()
    halt.unlink()
    assert not engine.halted()
    flagged = RiskEngine(_limits(), environ={"ENTROPYTRADE_TRADING_ENABLED": "false"})
    assert flagged.halted()
    disabled = RiskEngine(_limits(), trading_enabled=False)
    assert disabled.halted()


def test_reconcile_adopts_an_unknown_order_by_client_order_id() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    order = PaperBroker(ledger, _schedule()).submit(
        _approve(_intent(price="0.4000", post_only=True, quantity="1.00")),
        _book(),
        now=NOW,
    )
    unknown = order.with_state(OrderState.UNKNOWN, at=NOW)
    remote = order.revalidated(
        state=OrderState.FILLED,
        filled_quantity=order.requested_quantity,
        exchange_order_id="ex-1",
    )
    adopted = adopt_order(unknown, remote)
    assert adopted.state is OrderState.FILLED
    assert adopted.exchange_order_id == "ex-1"
    local = ledger.snapshot()
    remote_snapshot = PortfolioSnapshot(
        as_of=NOW,
        source=SnapshotSource.EXCHANGE,
        cash_balance=local.cash_balance,
        positions=local.positions,
    )
    assert compare_snapshots(local, remote_snapshot) == ()
    drifted = remote_snapshot.revalidated(cash_balance=Decimal("1"))
    assert compare_snapshots(local, drifted) != ()


def test_reconcile_refuses_a_smaller_fill_or_a_second_exchange_id() -> None:
    ledger = Ledger(Decimal("100"), as_of=NOW)
    order = PaperBroker(ledger, _schedule()).submit(
        _approve(_intent(price="0.4400", quantity="2.00")),
        _book(ask_qty="1.00"),
        now=NOW,
    )
    assert order.state is OrderState.PARTIALLY_FILLED
    smaller = order.revalidated(filled_quantity=Decimal("0.50"))
    with pytest.raises(ReconcileMismatchError, match="filled_quantity"):
        adopt_order(order, smaller)
    conflict = order.revalidated(exchange_order_id="ex-a")
    other_id = conflict.revalidated(exchange_order_id="ex-b")
    with pytest.raises(ReconcileMismatchError, match="exchange_order_id"):
        adopt_order(conflict, other_id)
    other_contract = order.revalidated(
        contract=Contract(market_ticker="OTHER", side=OutcomeSide.YES),
    )
    with pytest.raises(ReconcileMismatchError, match="contract"):
        adopt_order(order, other_contract)
    grown = order.revalidated(
        state=OrderState.FILLED,
        filled_quantity=Decimal("2.00"),
        exchange_order_id="ex-1",
    )
    adopted = adopt_order(order, grown)
    assert adopted.state is OrderState.FILLED
    assert adopted.filled_quantity == Decimal("2.00")
    assert adopted.exchange_order_id == "ex-1"
