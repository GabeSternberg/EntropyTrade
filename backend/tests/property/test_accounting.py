"""Accounting identities and the fee schedule."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from entropytrade.domain.enums import FeeType, LiquidityRole, OutcomeSide
from entropytrade.domain.market import Contract
from entropytrade.domain.numeric import ZERO, complement
from entropytrade.domain.orders import Fill
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.portfolio.ledger import Ledger
from tests.support import utc

NOW = utc(2026, 10, 2, 15)
price_ticks = st.integers(min_value=1, max_value=9_999)
quantity_ticks = st.integers(min_value=1, max_value=500)
coefficients = st.integers(min_value=0, max_value=20)


def _price(ticks: int) -> Decimal:
    return Decimal(ticks) / Decimal(10_000)


def _qty(ticks: int) -> Decimal:
    return Decimal(ticks) / Decimal(100)


def _coeff(ticks: int) -> Decimal:
    return Decimal(ticks) / Decimal(100)


@given(price_ticks, quantity_ticks, coefficients)
def test_makers_are_free_unless_the_schedule_charges_them(
    price_tick: int,
    quantity_tick: int,
    coefficient_tick: int,
) -> None:
    schedule = FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        quadratic_coefficient=_coeff(coefficient_tick),
    )
    fee = trade_fee(
        schedule,
        yes_price=_price(price_tick),
        quantity=_qty(quantity_tick),
        role=LiquidityRole.MAKER,
    )
    assert fee == ZERO


@given(price_ticks, quantity_ticks, coefficients)
def test_quadratic_fee_is_symmetric_in_the_yes_price(
    price_tick: int,
    quantity_tick: int,
    coefficient_tick: int,
) -> None:
    schedule = FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=True,
        quadratic_coefficient=_coeff(coefficient_tick),
    )
    price = _price(price_tick)
    quantity = _qty(quantity_tick)
    left = trade_fee(schedule, yes_price=price, quantity=quantity, role=LiquidityRole.TAKER)
    right = trade_fee(
        schedule,
        yes_price=complement(price),
        quantity=quantity,
        role=LiquidityRole.TAKER,
    )
    assert left == right


@given(st.lists(st.tuples(price_ticks, quantity_ticks), min_size=1, max_size=6))
def test_same_side_fills_keep_equity_equal_to_cash_plus_realized(
    fills: list[tuple[int, int]],
) -> None:
    ledger = Ledger(Decimal("1000000"), as_of=NOW)
    for index, (price_tick, quantity_tick) in enumerate(fills):
        applied = ledger.apply_fill(
            Fill(
                fill_id=f"p-{index}",
                exchange_order_id="paper",
                contract=Contract(market_ticker="M", side=OutcomeSide.YES),
                yes_price=_price(price_tick),
                quantity=_qty(quantity_tick),
                fee=ZERO,
                liquidity_role=LiquidityRole.TAKER,
                executed_at=NOW,
            )
        )
        assert applied
        assert ledger.apply_fill(ledger.fills()[-1]) is False
    assert ledger.equity() == ledger.cash + sum(item.total_cost for item in ledger.positions)
    assert ledger.equity() == ledger.starting_cash + ledger.realized_pnl
    assert ledger.realized_pnl == ZERO


@given(price_ticks, quantity_ticks)
def test_a_yes_and_no_pair_realizes_one_dollar_minus_both_costs(
    price_tick: int,
    quantity_tick: int,
) -> None:
    price = _price(price_tick)
    quantity = _qty(quantity_tick)
    ledger = Ledger(Decimal("1000000"), as_of=NOW)
    yes = Fill(
        fill_id="yes",
        exchange_order_id="paper",
        contract=Contract(market_ticker="M", side=OutcomeSide.YES),
        yes_price=price,
        quantity=quantity,
        fee=ZERO,
        liquidity_role=LiquidityRole.TAKER,
        executed_at=NOW,
    )
    no = Fill(
        fill_id="no",
        exchange_order_id="paper",
        contract=Contract(market_ticker="M", side=OutcomeSide.NO),
        yes_price=price,
        quantity=quantity,
        fee=ZERO,
        liquidity_role=LiquidityRole.TAKER,
        executed_at=NOW,
    )
    ledger.apply_fill(yes)
    ledger.apply_fill(no)
    assert ledger.position("M") is None
    assert ledger.equity() == ledger.starting_cash
    assert ledger.realized_pnl == ZERO
