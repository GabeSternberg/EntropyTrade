"""Recorded weather bodies and baseline probabilities. No live HTTP."""

from datetime import timedelta
from decimal import Decimal

import pytest

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.weather.probability import (
    MIN_ML_OBSERVATIONS,
    InsufficientHistoryError,
    brier_score,
    calibrate,
    climatology_hit_rate,
    market_implied_probability,
    raw_forecast_probability,
    refuse_fitted_model,
)
from entropytrade.weather.recorded import (
    RecordedBodyError,
    parse_cli_daily_high,
    parse_recorded_forecast,
    parse_weather_company_high,
)
from tests.support import utc

STATION = "CLIPHL"
STRIKE = Strike(strike_type=StrikeType.GREATER, floor=Decimal(89))
CLI = """
CLIPHL
CLIMATE REPORT
NATIONAL WEATHER SERVICE MOUNT HOLLY NJ
...THE PHILADELPHIA PA CLIMATE SUMMARY FOR OCTOBER 2 2026...
HOURLY TEMPERATURES
  1 PM 95
  2 PM 96
TEMPERATURE (F)
 YESTERDAY
  MAXIMUM         91    345 PM
  MINIMUM         64
"""


def _book(bid: str, ask: str) -> OrderBook:
    return OrderBook(
        market_ticker="KXHIGHPHIL-26OCT02-T89",
        bids=(OrderBookLevel(price=Decimal(bid), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal(ask), quantity=Decimal("5")),),
        received_at=utc(2026, 10, 2, 15),
    )


def test_cli_label_is_the_maximum_line_not_the_hourly_peak() -> None:
    high = parse_cli_daily_high(CLI, station=STATION, available_at=utc(2026, 10, 3, 10))
    assert high.high_f == Decimal(91)
    assert high.valid_on.isoformat() == "2026-10-02"
    assert high.source_id == "nws-cli"
    assert high.available_at == utc(2026, 10, 3, 10)


def test_cli_without_a_maximum_line_is_not_a_label() -> None:
    hourly = "CLIPHL\nFOR OCTOBER 2 2026\nHOURLY TEMPERATURES\n  2 PM 96\n"
    with pytest.raises(RecordedBodyError, match="MAXIMUM"):
        parse_cli_daily_high(hourly, station=STATION, available_at=utc(2026, 10, 3, 10))


def test_cli_is_not_available_on_the_observation_day() -> None:
    with pytest.raises(RecordedBodyError, match="observation day"):
        parse_cli_daily_high(CLI, station=STATION, available_at=utc(2026, 10, 2, 23))


def test_weather_company_body_rejects_a_float_high() -> None:
    body = (
        '{"source": "weather_company", "station": "CLIPHL", '
        '"valid_on": "2026-10-02", "high_f": 91.0}'
    )
    with pytest.raises(RecordedBodyError, match="high_f"):
        parse_weather_company_high(body, available_at=utc(2026, 10, 3, 10))


def test_weather_company_string_high_parses() -> None:
    body = (
        '{"source": "weather_company", "station": "CLIPHL", '
        '"valid_on": "2026-10-02", "high_f": "91"}'
    )
    high = parse_weather_company_high(body, available_at=utc(2026, 10, 3, 10))
    assert high.high_f == Decimal(91)
    assert high.source_id == "weather-company"


def test_recorded_forecast_keeps_run_time_before_availability() -> None:
    body = """
    {
      "provider": "fixture",
      "model": "recorded",
      "location_id": "CLIPHL",
      "variable": "daily_high_f",
      "run_time": "2026-10-02T08:00:00+00:00",
      "available_at": "2026-10-02T08:00:00+00:00",
      "valid_on": "2026-10-02",
      "value": "90",
      "unit": "degF"
    }
    """
    forecast = parse_recorded_forecast(body)
    assert forecast.value == Decimal(90)
    assert forecast.run_time == forecast.available_at
    leaked = body.replace(
        '"available_at": "2026-10-02T08:00:00+00:00"',
        '"available_at": "2026-10-02T07:00:00+00:00"',
    )
    with pytest.raises(ValueError, match="run time"):
        parse_recorded_forecast(leaked)


def test_a_later_label_does_not_change_climatology() -> None:
    decision = utc(2026, 10, 2, 15)
    labels = (
        (utc(2026, 10, 1, 10), Decimal(92)),
        (utc(2026, 10, 2, 10), Decimal(88)),
        (utc(2026, 10, 3, 10), Decimal(100)),
    )
    rate = climatology_hit_rate(labels, decision_time=decision, strike=STRIKE)
    assert rate == Decimal("0.5")
    assert raw_forecast_probability(Decimal(90), STRIKE) == Decimal(1)
    assert raw_forecast_probability(Decimal(89), STRIKE) == Decimal(0)
    assert calibrate(Decimal(1), rate) == Decimal("0.75")


def test_market_implied_probability_is_the_midpoint_not_the_ask() -> None:
    implied = market_implied_probability(_book("0.3000", "0.4000"))
    assert implied == Decimal("0.35")
    assert implied != Decimal("0.4000")
    with pytest.raises(ValueError, match="uncrossed"):
        market_implied_probability(_book("0.4000", "0.4000"))


def test_brier_and_the_fitted_model_gate() -> None:
    score = brier_score(((Decimal("0.35"), True), (Decimal("0.20"), False)))
    assert score == (Decimal("0.65") ** 2 + Decimal("0.20") ** 2) / 2
    with pytest.raises(InsufficientHistoryError, match="30"):
        refuse_fitted_model(MIN_ML_OBSERVATIONS - 1)
    refuse_fitted_model(MIN_ML_OBSERVATIONS)


def test_less_and_between_strikes_follow_the_contract() -> None:
    less = Strike(strike_type=StrikeType.LESS, cap=Decimal(82))
    between = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(88), cap=Decimal(89))
    assert raw_forecast_probability(Decimal(82), less) == Decimal(0)
    assert raw_forecast_probability(Decimal(81), less) == Decimal(1)
    assert raw_forecast_probability(Decimal(88), between) == Decimal(1)
    assert raw_forecast_probability(Decimal(90), between) == Decimal(0)


def test_fee_and_latency_change_the_paper_result() -> None:
    from entropytrade.backtest.replay import DecisionView, run_replay
    from entropytrade.domain.enums import FeeType, MarketResult, OutcomeSide, TimeInForce
    from entropytrade.domain.market import Contract
    from entropytrade.domain.observations import FeatureObservation
    from entropytrade.domain.orders import OrderIntent
    from entropytrade.domain.runs import SampleSplit, SplitWindow
    from entropytrade.execution.fees import FeeSchedule
    from entropytrade.execution.paper import PaperBroker
    from entropytrade.portfolio.ledger import Ledger
    from entropytrade.risk.engine import RiskEngine, RiskLimits

    decision = utc(2026, 10, 2, 15)
    record = FeatureObservation(
        source_id="persistence",
        event_time=utc(2026, 10, 2, 8),
        available_at=utc(2026, 10, 2, 8),
        ingested_at=utc(2026, 10, 2, 8),
        feature_name="forecast_high",
        feature_version="persistence",
        entity_id="KXHIGHPHIL-26OCT02-T89",
        value=Decimal(90),
    )
    book = _book("0.3000", "0.4000")

    def trade(view: DecisionView, seen: OrderBook) -> OrderIntent | None:
        vintage = view.feature("forecast_high", seen.market_ticker)
        if vintage is None or vintage.value is None:
            return None
        if raw_forecast_probability(vintage.value, STRIKE) != Decimal(1):
            return None
        ask = seen.best_ask
        if ask is None:
            return None
        return OrderIntent(
            strategy_id="raw-forecast",
            strategy_version=1,
            contract=Contract(market_ticker=seen.market_ticker, side=OutcomeSide.YES),
            yes_price=ask.price,
            quantity=Decimal("1.00"),
            time_in_force=TimeInForce.FILL_OR_KILL,
            decision_time=seen.received_at,
        )

    def cash_for(*, coefficient: Decimal, latency: timedelta) -> Decimal:
        ledger = Ledger(Decimal("100"), as_of=decision)
        limits = RiskLimits(
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
        run_replay(
            books=(book,),
            records=(record,),
            strategy=trade,
            ledger=ledger,
            broker=PaperBroker(
                ledger,
                FeeSchedule(
                    fee_type=FeeType.QUADRATIC,
                    fee_multiplier=Decimal(1),
                    maker_pays=False,
                    quadratic_coefficient=coefficient,
                ),
            ),
            engine=RiskEngine(limits),
            latency=latency,
            window=SplitWindow(
                split=SampleSplit.TRAIN,
                start=utc(2026, 10, 2, 12),
                end=utc(2026, 10, 3, 12),
            ),
            settlements=((utc(2026, 10, 3, 10), book.market_ticker, MarketResult.YES),),
        )
        return ledger.cash

    assert cash_for(coefficient=Decimal(0), latency=timedelta(0)) == Decimal("100.60")
    assert cash_for(coefficient=Decimal("0.02"), latency=timedelta(0)) == Decimal("100.59")
    assert cash_for(coefficient=Decimal(0), latency=timedelta(hours=2)) == Decimal("100")
