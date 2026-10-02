"""Property tests for the invariants the domain types already enforce."""

from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from entropytrade.domain.enums import OutcomeSide, StrikeType
from entropytrade.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    LifecycleState,
    requires_human_approval,
)
from entropytrade.domain.market import Strike
from entropytrade.domain.numeric import (
    ONE,
    ZERO,
    complement,
    notional,
    parse_price,
    parse_quantity,
)
from entropytrade.domain.observations import FeatureObservation, select_as_of
from entropytrade.domain.orders import ORDER_TRANSITIONS, OrderState
from entropytrade.domain.portfolio import settlement_payout
from entropytrade.domain.signals import EdgeEstimate
from tests.support import utc

price_ticks = st.integers(min_value=0, max_value=10_000)
order_price_ticks = st.integers(min_value=1, max_value=9_999)
quantity_ticks = st.integers(min_value=0, max_value=10_000)
positive_quantity_ticks = st.integers(min_value=1, max_value=10_000)
money_units = st.integers(min_value=0, max_value=1_000_000)


def _price(ticks: int) -> Decimal:
    return Decimal(ticks) / Decimal(10_000)


def _qty(ticks: int) -> Decimal:
    return Decimal(ticks) / Decimal(100)


@given(price_ticks)
def test_complement_is_an_involution_on_the_price_grid(ticks: int) -> None:
    price = _price(ticks)
    assert complement(complement(price)) == price
    assert complement(price) + price == ONE
    parse_price(price)


@given(order_price_ticks, positive_quantity_ticks)
def test_notional_is_exact_money(price_tick: int, quantity_tick: int) -> None:
    price, quantity = _price(price_tick), _qty(quantity_tick)
    assert notional(price, quantity) == price * quantity


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_floats_are_rejected_for_prices_and_quantities(value: float) -> None:
    with pytest.raises(ValueError, match="not accepted"):
        parse_price(value)
    with pytest.raises(ValueError, match="not accepted"):
        parse_quantity(value)


@given(st.integers(min_value=-10_000, max_value=10_000), st.sampled_from(list(StrikeType)))
def test_threshold_strikes_partition_the_line(reading: int, strike_type: StrikeType) -> None:
    value = Decimal(reading)
    floor, cap = Decimal(70), Decimal(80)
    strike = _strike(strike_type, floor, cap)
    if not strike.is_evaluable:
        return
    answer = strike.resolves_yes(value)
    assert answer is True or answer is False
    if strike_type is StrikeType.GREATER:
        assert answer is (value > floor)
    elif strike_type is StrikeType.LESS:
        assert answer is (value < cap)
    elif strike_type is StrikeType.BETWEEN:
        assert answer is (floor <= value <= cap)


def _strike(strike_type: StrikeType, floor: Decimal, cap: Decimal) -> Strike:
    if strike_type in (StrikeType.GREATER, StrikeType.GREATER_OR_EQUAL):
        return Strike(strike_type=strike_type, floor=floor)
    if strike_type in (StrikeType.LESS, StrikeType.LESS_OR_EQUAL):
        return Strike(strike_type=strike_type, cap=cap)
    if strike_type is StrikeType.BETWEEN:
        return Strike(strike_type=strike_type, floor=floor, cap=cap)
    return Strike(strike_type=strike_type)


@given(st.sampled_from(list(OutcomeSide)), positive_quantity_ticks, price_ticks)
def test_settlement_payout_is_bounded_by_quantity(
    side: OutcomeSide, qty_ticks: int, value_ticks: int
) -> None:
    quantity = _qty(qty_ticks)
    payout = settlement_payout(side, quantity, _price(value_ticks))
    assert ZERO <= payout <= notional(ONE, quantity)
    if side is OutcomeSide.YES:
        other = settlement_payout(OutcomeSide.NO, quantity, _price(value_ticks))
    else:
        other = settlement_payout(OutcomeSide.YES, quantity, _price(value_ticks))
    assert payout + other == notional(ONE, quantity)


@given(price_ticks, order_price_ticks, money_units, money_units)
def test_net_edge_is_raw_edge_minus_every_cost(
    probability_ticks: int,
    price_tick: int,
    fee_units: int,
    reserve_units: int,
) -> None:
    estimate = EdgeEstimate(
        outcome_probability=_price(probability_ticks),
        price_per_contract=_price(price_tick),
        fee_per_contract=Decimal(fee_units) / Decimal(1_000_000),
        expected_slippage=Decimal(reserve_units) / Decimal(1_000_000),
    )
    assert estimate.net_edge == estimate.raw_edge - estimate.total_costs
    assert estimate.total_costs >= ZERO


@given(st.sampled_from(list(OrderState)), st.sampled_from(list(OrderState)))
def test_terminal_orders_have_no_exit(source: OrderState, target: OrderState) -> None:
    if source.is_terminal:
        assert target not in ORDER_TRANSITIONS[source]


@given(st.sampled_from(list(LifecycleState)), st.sampled_from(list(LifecycleState)))
def test_real_capital_only_grows_with_approval(
    source: LifecycleState, target: LifecycleState
) -> None:
    if target not in ALLOWED_TRANSITIONS[source]:
        return
    increased = target in (LifecycleState.LIVE_SMALL, LifecycleState.LIVE) and source not in (
        LifecycleState.LIVE_SMALL,
        LifecycleState.LIVE,
    )
    # DEGRADED -> LIVE_SMALL is an increase and must require approval; LIVE -> LIVE_SMALL must not.
    if increased or (source is LifecycleState.DEGRADED and target is LifecycleState.LIVE_SMALL):
        assert requires_human_approval(source, target)
    if target is LifecycleState.DEGRADED or target is LifecycleState.PAUSED:
        assert not requires_human_approval(source, target)


@given(
    st.lists(st.integers(min_value=0, max_value=48), min_size=1, max_size=12), st.integers(0, 48)
)
@settings(max_examples=50)
def test_as_of_selection_ignores_later_data(hours: list[int], cutoff_hour: int) -> None:
    records = [_feature(hour) for hour in hours]
    cutoff = utc(2026, 10, 1, 0) + timedelta(hours=cutoff_hour)
    selected = select_as_of(records, cutoff, key=lambda row: row.entity_id)
    for record in selected.values():
        assert record.available_at <= cutoff
    later = [_feature(hour) for hour in hours if hour > cutoff_hour]
    again = select_as_of([*records, *later], cutoff, key=lambda row: row.entity_id)
    assert list(again) == list(selected)
    for key, record in again.items():
        assert record == selected[key]


def _feature(hour: int) -> FeatureObservation:
    moment = utc(2026, 10, 1, 0) + timedelta(hours=hour)
    return FeatureObservation(
        source_id="open-meteo",
        revision_id=str(hour),
        event_time=moment,
        published_at=moment,
        available_at=moment,
        ingested_at=moment,
        feature_name="forecast_high_f",
        feature_version="v1",
        entity_id="CLIPHL",
        value=Decimal(hour),
    )
