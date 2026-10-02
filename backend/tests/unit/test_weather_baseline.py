"""Philadelphia daily-high baseline. The CLI label is not a forecast."""

from datetime import timedelta
from decimal import Decimal

import pytest

from entropytrade.backtest.replay import DecisionView, run_replay
from entropytrade.domain.enums import FeeType, MarketResult, OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.exchange.settlement import parse_settlement
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.weather.baseline import (
    NoScoredForecastError,
    latest_before_label,
    mean_absolute_error,
    persistence_forecast,
)
from tests.support import utc

STATION = "CLIPHL"
DAY = utc(2026, 10, 2).date()
LABEL_AT = utc(2026, 10, 3, 10)
DECISION = utc(2026, 10, 2, 15)
TICKER = "KXHIGHPHIL-26OCT02-T89"


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


def test_a_forecast_issued_after_the_cli_does_not_score() -> None:
    honest = persistence_forecast(
        previous_high_f=Decimal(88),
        previous_available_at=utc(2026, 10, 2, 8),
        station=STATION,
        valid_on=DAY,
        run_time=utc(2026, 10, 2, 8),
        available_at=utc(2026, 10, 2, 8),
    )
    leaked = persistence_forecast(
        previous_high_f=Decimal(91),
        previous_available_at=LABEL_AT,
        station=STATION,
        valid_on=DAY,
        run_time=utc(2026, 10, 3, 11),
        available_at=utc(2026, 10, 3, 11),
    )
    chosen = latest_before_label(
        (honest, leaked),
        station=STATION,
        valid_on=DAY,
        label_available_at=LABEL_AT,
    )
    assert chosen is honest
    error = mean_absolute_error(
        (honest, leaked),
        ((DAY, Decimal(91), LABEL_AT),),
        station=STATION,
    )
    assert error == Decimal(3)


def test_persistence_cannot_use_a_cli_that_is_not_available_yet() -> None:
    with pytest.raises(ValueError, match="available"):
        persistence_forecast(
            previous_high_f=Decimal(91),
            previous_available_at=LABEL_AT,
            station=STATION,
            valid_on=DAY,
            run_time=DECISION,
            available_at=DECISION,
        )


def test_only_after_the_fact_forecasts_are_not_a_score() -> None:
    leaked = persistence_forecast(
        previous_high_f=Decimal(91),
        previous_available_at=LABEL_AT,
        station=STATION,
        valid_on=DAY,
        run_time=utc(2026, 10, 3, 11),
        available_at=utc(2026, 10, 3, 11),
    )
    with pytest.raises(NoScoredForecastError):
        mean_absolute_error((leaked,), ((DAY, Decimal(91), LABEL_AT),), station=STATION)


def test_paper_trade_sees_the_forecast_and_not_the_cli_label() -> None:
    forecast = persistence_forecast(
        previous_high_f=Decimal(90),
        previous_available_at=utc(2026, 10, 2, 8),
        station=STATION,
        valid_on=DAY,
        run_time=utc(2026, 10, 2, 8),
        available_at=utc(2026, 10, 2, 8),
    )
    records = (
        FeatureObservation(
            source_id="persistence",
            event_time=forecast.run_time,
            available_at=forecast.available_at,
            ingested_at=forecast.ingested_at,
            feature_name="forecast_high",
            feature_version="persistence",
            entity_id=TICKER,
            value=forecast.value,
        ),
        FeatureObservation(
            source_id="cli",
            event_time=LABEL_AT,
            available_at=LABEL_AT,
            ingested_at=LABEL_AT,
            feature_name="cli_high",
            feature_version="1",
            entity_id=TICKER,
            value=Decimal(91),
        ),
    )
    seen: list[Decimal | None] = []

    def trade(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        if book.received_at != DECISION:
            return None
        label = view.feature("cli_high", TICKER)
        vintage = view.feature("forecast_high", TICKER)
        seen.append(None if label is None else label.value)
        if vintage is None or vintage.value is None or vintage.value <= Decimal(89):
            return None
        return OrderIntent(
            strategy_id="persistence",
            strategy_version=1,
            contract=Contract(market_ticker=TICKER, side=OutcomeSide.YES),
            yes_price=Decimal("0.4000"),
            quantity=Decimal("1.00"),
            time_in_force=TimeInForce.FILL_OR_KILL,
            decision_time=book.received_at,
        )

    book = OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5")),),
        received_at=DECISION,
    )
    ledger = Ledger(Decimal("100"), as_of=DECISION)
    run_replay(
        books=(book,),
        records=records,
        strategy=trade,
        ledger=ledger,
        broker=PaperBroker(
            ledger,
            FeeSchedule(
                fee_type=FeeType.QUADRATIC,
                fee_multiplier=Decimal(1),
                maker_pays=False,
                quadratic_coefficient=Decimal(0),
            ),
        ),
        engine=RiskEngine(_limits()),
        latency=timedelta(0),
        window=SplitWindow(
            split=SampleSplit.TRAIN,
            start=utc(2026, 10, 2, 12),
            end=utc(2026, 10, 3, 12),
        ),
        settlements=((LABEL_AT, TICKER, MarketResult.YES),),
    )
    assert seen == [None]
    assert ledger.position(TICKER) is None
    assert ledger.cash == Decimal("100.60")
    parsed = parse_settlement("Highest temperature in Philadelphia.", "", TICKER)
    assert parsed.basis == "kxhigh_schedule"
    assert parsed.sources[0].name == "The Weather Company"
