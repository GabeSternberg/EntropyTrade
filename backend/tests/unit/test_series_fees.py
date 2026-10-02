"""Stored series fee fields applied in replay. The test does not open a socket."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from entropytrade.backtest.replay import DecisionView, ReplayError, run_replay
from entropytrade.domain.enums import FeeType, LiquidityRole, OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.execution.paper import PaperBroker
from entropytrade.execution.series_fees import FEE_MODEL_VERSION, load_series_fees
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from tests.support import utc

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
TICKER = "KXHIGHPHIL-26OCT02-T89"
WHEN = utc(2026, 10, 2, 10)
COEFFICIENT = Decimal("0.20")


def test_kxhigh_makers_pay_nothing_and_a_maker_series_does_not() -> None:
    table = load_series_fees(ROOT)
    phil = table.match(TICKER)
    nhl = table.match("KXNHL-27-STANLEY")
    combo = table.match("KXMVECROSSCATEGORY-1")
    assert phil.fee_type is FeeType.QUADRATIC
    assert phil.fee_multiplier == Decimal(1)
    assert phil.maker_pays is False
    assert phil.endpoint.endswith("/series/KXHIGHPHIL")
    assert nhl.fee_type is FeeType.QUADRATIC_WITH_MAKER_FEES
    assert nhl.maker_fraction == Decimal("0.25")
    assert combo.maker_fraction == Decimal("0.5")
    price = Decimal("0.5000")
    quantity = Decimal("10.00")
    kx_maker = trade_fee(
        table.schedule(phil, coefficient=COEFFICIENT),
        yes_price=price,
        quantity=quantity,
        role=LiquidityRole.MAKER,
    )
    kx_taker = trade_fee(
        table.schedule(phil, coefficient=COEFFICIENT),
        yes_price=price,
        quantity=quantity,
        role=LiquidityRole.TAKER,
    )
    nhl_maker = trade_fee(
        table.schedule(nhl, coefficient=COEFFICIENT),
        yes_price=price,
        quantity=quantity,
        role=LiquidityRole.MAKER,
    )
    nhl_taker = trade_fee(
        table.schedule(nhl, coefficient=COEFFICIENT),
        yes_price=price,
        quantity=quantity,
        role=LiquidityRole.TAKER,
    )
    combo_maker = trade_fee(
        table.schedule(combo, coefficient=COEFFICIENT),
        yes_price=price,
        quantity=quantity,
        role=LiquidityRole.MAKER,
    )
    assert kx_maker == ZERO
    assert kx_taker == Decimal("0.500000")
    assert nhl_taker == kx_taker
    assert nhl_maker == Decimal("0.130000")
    assert combo_maker == Decimal("0.250000")


def test_replay_uses_the_stored_series_instead_of_the_broker_multiplier() -> None:
    table = load_series_fees(ROOT)
    ledger = Ledger(Decimal("100"), as_of=WHEN)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC_WITH_MAKER_FEES,
            fee_multiplier=Decimal(9),
            maker_pays=True,
            quadratic_coefficient=COEFFICIENT,
        ),
    )
    book = OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5.00")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5.00")),),
        received_at=WHEN,
    )

    def buy(view: DecisionView, seen: OrderBook) -> OrderIntent | None:
        del view
        return OrderIntent(
            intent_id=UUID(int=7),
            strategy_id="series-fee",
            strategy_version=1,
            contract=Contract(market_ticker=seen.market_ticker, side=OutcomeSide.YES),
            yes_price=Decimal("0.4000"),
            quantity=Decimal("1.00"),
            time_in_force=TimeInForce.FILL_OR_KILL,
            decision_time=seen.received_at,
        )

    result = run_replay(
        books=(book,),
        records=(),
        strategy=buy,
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(
            RiskLimits(
                bankroll=Decimal("100"),
                per_trade=Decimal("100"),
                per_event=Decimal("100"),
                total_deployed=Decimal("100"),
                max_loss=Decimal("50"),
                max_drawdown=Decimal("50"),
                max_book_age_seconds=3600,
                min_liquidity=Decimal("1.00"),
                max_spread=Decimal("0.2000"),
                config_version="series-fee-v1",
            )
        ),
        latency=timedelta(0),
        window=SplitWindow(split=SampleSplit.TRAIN, start=WHEN, end=utc(2026, 10, 2, 12)),
        series_fees=table,
    )
    fills = ledger.fills()
    assert len(fills) == 1
    assert fills[0].fee == Decimal("0.050000")
    assert fills[0].liquidity_role is LiquidityRole.TAKER
    assert result.fee_model_version == FEE_MODEL_VERSION
    assert len(result.fee_models) == 1
    assert result.fee_models[0].fee_type is FeeType.QUADRATIC
    assert result.fee_models[0].fee_multiplier == Decimal(1)
    assert result.fee_models[0].maker_pays is False
    assert result.fee_models[0].version == FEE_MODEL_VERSION


def test_an_unknown_series_is_not_given_a_fee() -> None:
    table = load_series_fees(ROOT)
    ledger = Ledger(Decimal("100"), as_of=WHEN)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=COEFFICIENT,
        ),
    )
    book = OrderBook(
        market_ticker="NOTASERIES-26OCT02-T89",
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5.00")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5.00")),),
        received_at=WHEN,
    )

    def hold(view: DecisionView, seen: OrderBook) -> OrderIntent | None:
        del view, seen
        return None

    with pytest.raises(ReplayError, match="no stored series fee"):
        run_replay(
            books=(book,),
            records=(),
            strategy=hold,
            ledger=ledger,
            broker=broker,
            engine=RiskEngine(
                RiskLimits(
                    bankroll=Decimal("100"),
                    per_trade=Decimal("100"),
                    per_event=Decimal("100"),
                    total_deployed=Decimal("100"),
                    max_loss=Decimal("50"),
                    max_drawdown=Decimal("50"),
                    max_book_age_seconds=3600,
                    min_liquidity=Decimal("1.00"),
                    max_spread=Decimal("0.2000"),
                    config_version="series-fee-v1",
                )
            ),
            latency=timedelta(0),
            window=SplitWindow(split=SampleSplit.TRAIN, start=WHEN, end=utc(2026, 10, 2, 12)),
            series_fees=table,
        )


def test_the_fee_loader_does_not_invent_a_coefficient() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/execution/series_fees.py")
        .read_text(encoding="utf-8")
    )
    manifest = (ROOT / "kalshi-fees" / "manifest.json").read_text(encoding="utf-8")
    error = (ROOT / "kalshi-fees" / "fee-schedule.error.html").read_text(encoding="utf-8")
    assert "0.07" not in text
    assert '"quadratic_coefficient": null' in manifest
    assert "Vercel Security Checkpoint" in error
    for name in ("import urllib", "import httpx", "import socket"):
        assert name not in text
