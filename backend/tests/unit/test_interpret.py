"""StrategySpec interpreter: visible features only, and unsupported specs are refused."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from entropytrade.agents.fixture import TICKER, demo_specs, philadelphia_records
from entropytrade.backtest.replay import DecisionView
from entropytrade.domain.enums import FeeType
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.strategy import SizingMethod
from entropytrade.execution.fees import FeeSchedule
from entropytrade.strategies.interpret import UnsupportedSpecError, compile_strategy


def _book() -> OrderBook:
    return OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5")),),
        received_at=datetime(2026, 10, 2, 15, tzinfo=UTC),
    )


def test_a_later_cli_high_is_not_a_reason_to_trade() -> None:
    spec = next(item for item in demo_specs() if item.strategy_id == "phl-probability-055")
    compiled = compile_strategy(spec)
    early = DecisionView(philadelphia_records(), datetime(2026, 10, 2, 7, tzinfo=UTC))
    assert compiled(early, _book()) is None
    visible = DecisionView(
        philadelphia_records(),
        datetime(2026, 10, 2, 15, tzinfo=UTC),
        schedule=FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=Decimal(0),
        ),
    )
    intent = compiled(visible, _book())
    assert intent is not None
    assert intent.yes_price == Decimal("0.4000")
    leaked = visible.feature("cli_high", TICKER)
    assert leaked is None


def test_kelly_and_a_non_settlement_exit_are_not_half_run() -> None:
    kelly = next(item for item in demo_specs() if item.strategy_id == "phl-kelly")
    with pytest.raises(UnsupportedSpecError, match="fixed_contracts"):
        compile_strategy(kelly)
    early = kelly.revalidated(
        strategy_id="phl-early",
        position_sizing=kelly.position_sizing.revalidated(
            method=SizingMethod.FIXED_CONTRACTS,
            contracts=Decimal("1.00"),
            kelly_fraction=None,
        ),
        exit_rules=kelly.exit_rules.revalidated(description="Sell if the ask reaches 0.80."),
    )
    with pytest.raises(UnsupportedSpecError, match="settlement"):
        compile_strategy(early)
