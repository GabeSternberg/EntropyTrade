"""Order state machine, risk decisions, lifecycle and trading modes."""

from decimal import Decimal
from uuid import uuid4

import pytest

from entropytrade.domain.enums import (
    ActorKind,
    KalshiEnvironment,
    LiquidityRole,
    OutcomeSide,
    RiskSeverity,
    TimeInForce,
)
from entropytrade.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    Actor,
    HumanApproval,
    LifecycleState,
    LifecycleTransition,
    capital_rank,
    requires_human_approval,
)
from entropytrade.domain.market import Contract
from entropytrade.domain.modes import (
    DEFAULT_TRADING_MODE,
    LIVE_TRADING_ENV_FLAG,
    TradingMode,
    TradingModeError,
    resolve_trading_mode,
)
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.orders import (
    ORDER_TRANSITIONS,
    ApprovedOrderIntent,
    Fill,
    InvalidOrderTransitionError,
    Order,
    OrderIntent,
    OrderRequest,
    OrderState,
    check_order_transition,
)
from entropytrade.domain.risk import RiskCheckResult, RiskDecision, RiskEvent, RiskEventKind
from tests.support import utc


def _intent(**changes: object) -> OrderIntent:
    base: dict[str, object] = {
        "strategy_id": "s-1",
        "strategy_version": 1,
        "contract": Contract(market_ticker="M", side=OutcomeSide.YES),
        "yes_price": Decimal("0.40"),
        "quantity": Decimal("2.00"),
        "time_in_force": TimeInForce.GOOD_TILL_CANCELED,
        "decision_time": utc(2026, 10, 2, 15),
        "rationale": "test",
    }
    base.update(changes)
    return OrderIntent.model_validate(base)


def _decision(intent: OrderIntent, *, approved: bool, quantity: str) -> RiskDecision:
    return RiskDecision(
        intent_id=intent.intent_id,
        approved=approved,
        approved_quantity=Decimal(quantity),
        checks=(RiskCheckResult(check_name="max_order_dollars", passed=approved, detail="cap"),),
        risk_config_version="risk-v1",
        decided_at=utc(2026, 10, 2, 15, 1),
    )


def _order(state: OrderState, *, requested: str = "2.00", filled: str = "0") -> Order:
    return Order(
        client_order_id=uuid4(),
        intent_id=uuid4(),
        contract=Contract(market_ticker="M", side=OutcomeSide.YES),
        yes_price=Decimal("0.40"),
        requested_quantity=Decimal(requested),
        filled_quantity=Decimal(filled),
        state=state,
        created_at=utc(2026, 10, 2, 15),
        updated_at=utc(2026, 10, 2, 15),
    )


def test_default_mode_is_not_live_and_live_needs_three_agreements() -> None:
    assert DEFAULT_TRADING_MODE is TradingMode.READ_ONLY
    assert not DEFAULT_TRADING_MODE.submits_orders_to_exchange
    assert not DEFAULT_TRADING_MODE.uses_real_money
    demo = {TradingMode.DEMO, TradingMode.LIVE}
    assert {mode for mode in TradingMode if mode.submits_orders_to_exchange} == demo
    with pytest.raises(TradingModeError, match=LIVE_TRADING_ENV_FLAG):
        resolve_trading_mode(TradingMode.LIVE, KalshiEnvironment.PRODUCTION, {})
    with pytest.raises(TradingModeError, match="demo"):
        resolve_trading_mode(TradingMode.DEMO, KalshiEnvironment.PRODUCTION, {})
    with pytest.raises(TradingModeError, match="production"):
        resolve_trading_mode(
            TradingMode.LIVE,
            KalshiEnvironment.DEMO,
            {LIVE_TRADING_ENV_FLAG: "true"},
        )
    resolved = resolve_trading_mode(
        TradingMode.LIVE,
        KalshiEnvironment.PRODUCTION,
        {LIVE_TRADING_ENV_FLAG: "true"},
    )
    assert resolved is TradingMode.LIVE
    assert (
        resolve_trading_mode(TradingMode.PAPER, KalshiEnvironment.PRODUCTION, {})
        is TradingMode.PAPER
    )


def test_order_transition_table_is_closed() -> None:
    for source, targets in ORDER_TRANSITIONS.items():
        for target in OrderState:
            if target in targets:
                check_order_transition(source, target)
            else:
                with pytest.raises(InvalidOrderTransitionError):
                    check_order_transition(source, target)
        if source.is_terminal:
            assert targets == frozenset()


def test_fills_move_the_order_and_cannot_overfill() -> None:
    resting = _order(OrderState.RESTING)
    partial = resting.with_fill(Decimal("1.00"), at=utc(2026, 10, 2, 15, 2))
    assert partial.state is OrderState.PARTIALLY_FILLED
    assert partial.remaining_quantity == Decimal("1.00")
    filled = partial.with_fill(Decimal("1.00"), at=utc(2026, 10, 2, 15, 3))
    assert filled.state is OrderState.FILLED
    with pytest.raises(InvalidOrderTransitionError):
        filled.with_state(OrderState.CANCELLED, at=utc(2026, 10, 2, 16))
    with pytest.raises(ValueError, match="exceed"):
        partial.with_fill(Decimal("1.01"), at=utc(2026, 10, 2, 15, 4))
    with pytest.raises(ValueError, match="fills"):
        _order(OrderState.SUBMITTING, filled="1.00")


def test_unknown_state_returns_only_through_reconciliation() -> None:
    unknown = _order(OrderState.SUBMITTING).with_state(
        OrderState.UNKNOWN, at=utc(2026, 10, 2, 15, 1)
    )
    assert unknown.may_be_live_on_exchange
    reconciled = unknown.with_state(OrderState.RESTING, at=utc(2026, 10, 2, 15, 2))
    assert reconciled.state is OrderState.RESTING
    with pytest.raises(InvalidOrderTransitionError):
        unknown.with_state(OrderState.SUBMITTING, at=utc(2026, 10, 2, 15, 2))


def test_approval_cannot_exceed_or_precede_the_intent() -> None:
    intent = _intent()
    approved = ApprovedOrderIntent(
        intent=intent, decision=_decision(intent, approved=True, quantity="1.00")
    )
    assert approved.quantity == Decimal("1.00")
    built = OrderRequest.from_approved(approved, created_at=utc(2026, 10, 2, 15, 2))
    assert built.quantity == Decimal("1.00")
    assert built.intent_id == intent.intent_id
    with pytest.raises(ValueError, match="more than"):
        ApprovedOrderIntent(
            intent=intent, decision=_decision(intent, approved=True, quantity="3.00")
        )
    rejected = _decision(intent, approved=False, quantity="0")
    with pytest.raises(ValueError, match="did not approve"):
        ApprovedOrderIntent(intent=intent, decision=rejected)


def test_no_side_cost_is_the_complement() -> None:
    intent = _intent(contract=Contract(market_ticker="M", side=OutcomeSide.NO))
    assert intent.price_per_contract == Decimal("0.60")
    assert intent.max_cost == Decimal("1.200000")


def test_fill_cost_excludes_the_fee() -> None:
    fill = Fill(
        fill_id="f1",
        exchange_order_id="ex1",
        contract=Contract(market_ticker="M", side=OutcomeSide.NO),
        yes_price=Decimal("0.40"),
        quantity=Decimal("2.00"),
        fee=Decimal("0.030000"),
        liquidity_role=LiquidityRole.TAKER,
        executed_at=utc(2026, 10, 2, 15),
    )
    assert fill.cost == Decimal("1.200000")
    assert fill.fee == Decimal("0.03")


def test_risk_decision_is_fail_closed() -> None:
    intent_id = uuid4()
    with pytest.raises(ValueError, match="failed"):
        RiskDecision(
            intent_id=intent_id,
            approved=True,
            approved_quantity=Decimal("1.00"),
            checks=(RiskCheckResult(check_name="spread", passed=False),),
            risk_config_version="risk-v1",
            decided_at=utc(2026, 10, 2, 15),
        )
    with pytest.raises(ValueError, match="zero"):
        RiskDecision(
            intent_id=intent_id,
            approved=False,
            approved_quantity=Decimal("1.00"),
            checks=(RiskCheckResult(check_name="spread", passed=False),),
            risk_config_version="risk-v1",
            decided_at=utc(2026, 10, 2, 15),
        )
    decision = RiskDecision(
        intent_id=intent_id,
        approved=False,
        approved_quantity=ZERO,
        checks=(
            RiskCheckResult(check_name="spread", passed=False, detail="too wide"),
            RiskCheckResult(check_name="staleness", passed=True),
        ),
        risk_config_version="risk-v1",
        decided_at=utc(2026, 10, 2, 15),
    )
    assert [check.check_name for check in decision.failed_checks] == ["spread"]


def test_capital_increases_need_a_human_and_decreases_do_not() -> None:
    assert DEFAULT_TRADING_MODE is TradingMode.READ_ONLY
    for source, targets in ALLOWED_TRANSITIONS.items():
        for target in LifecycleState:
            allowed = target in targets
            if allowed and requires_human_approval(source, target):
                assert capital_rank(target) > capital_rank(source)
    agent = Actor(kind=ActorKind.AGENT, actor_id="quant")
    human = Actor(kind=ActorKind.HUMAN, actor_id="gabe")
    with pytest.raises(ValueError, match="approval"):
        LifecycleTransition(
            strategy_id="s",
            strategy_version=1,
            from_state=LifecycleState.SHADOW_LIVE,
            to_state=LifecycleState.LIVE_SMALL,
            actor=human,
            reason="looks good",
            occurred_at=utc(2026, 6, 1),
        )
    with pytest.raises(ValueError, match="agent"):
        LifecycleTransition(
            strategy_id="s",
            strategy_version=1,
            from_state=LifecycleState.SHADOW_LIVE,
            to_state=LifecycleState.LIVE_SMALL,
            actor=agent,
            reason="promote",
            occurred_at=utc(2026, 6, 1),
            approval=HumanApproval(approver_id="gabe", approved_at=utc(2026, 6, 1)),
        )
    promoted = LifecycleTransition(
        strategy_id="s",
        strategy_version=1,
        from_state=LifecycleState.SHADOW_LIVE,
        to_state=LifecycleState.LIVE_SMALL,
        actor=human,
        reason="shadow sample passed",
        occurred_at=utc(2026, 6, 2),
        approval=HumanApproval(approver_id="gabe", approved_at=utc(2026, 6, 1), note="ok"),
    )
    assert promoted.approval is not None
    downgraded = LifecycleTransition(
        strategy_id="s",
        strategy_version=1,
        from_state=LifecycleState.LIVE,
        to_state=LifecycleState.DEGRADED,
        actor=Actor(kind=ActorKind.SYSTEM, actor_id="risk"),
        reason="drawdown",
        occurred_at=utc(2026, 6, 3),
    )
    assert downgraded.approval is None
    with pytest.raises(ValueError, match="not allowed"):
        LifecycleTransition(
            strategy_id="s",
            strategy_version=1,
            from_state=LifecycleState.RETIRED,
            to_state=LifecycleState.LIVE,
            actor=human,
            reason="no",
            occurred_at=utc(2026, 6, 4),
        )


def test_risk_event_records_a_halt() -> None:
    event = RiskEvent(
        kind=RiskEventKind.KILL_SWITCH,
        severity=RiskSeverity.HALT,
        occurred_at=utc(2026, 10, 2, 16),
        message="HALT file present",
    )
    assert event.severity is RiskSeverity.HALT
