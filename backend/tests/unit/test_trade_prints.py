"""Public trade prints are prices, not fills."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.observations import Forecast
from entropytrade.exchange.trade_prints import TradePrint, load_trade_tape
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.trade_score import load_trade_score, score_scenarios

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "trade_prints.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text


def test_stored_prints_keep_the_reported_size() -> None:
    tape = load_trade_tape(ROOT)
    assert tape.trade_count == 104442
    assert tape.tickers == 240
    assert tape.tickers_with_trades == 240
    assert tape.failed_calls == 0
    known = next(
        item for item in tape.b805_prints if item.trade_id == "0720cbcd-9999-ba7f-4ea9-d00b5031b7aa"
    )
    assert known.count == Decimal("7.08")
    assert known.yes_price == Decimal("0.9900")
    assert known.ticker == "KXHIGHPHIL-26AUG25-B80.5"


def test_a_print_after_the_decision_is_not_an_optimistic_fill() -> None:
    valid_on = date(2026, 8, 25)
    label = CliLabel(
        available_at=datetime(2026, 8, 26, 8, tzinfo=UTC),
        source="test",
        endpoint="test",
        valid_on=valid_on,
        high_f=Decimal(82),
        header="KPHI 260800",
    )
    forecast = Forecast(
        source_id="open-meteo",
        event_time=datetime(2026, 8, 24, 6, tzinfo=UTC),
        available_at=datetime(2026, 8, 24, 7, tzinfo=UTC),
        ingested_at=datetime(2026, 8, 24, 7, tzinfo=UTC),
        provider="open-meteo",
        model="gfs",
        run_time=datetime(2026, 8, 24, 6, tzinfo=UTC),
        location_id="CLIPHL",
        variable="temperature_2m_max",
        valid_from=datetime(2026, 8, 25, tzinfo=UTC),
        valid_to=datetime(2026, 8, 26, tzinfo=UTC),
        value=Decimal("80.5"),
        unit="F",
    )
    late = _print(created=datetime(2026, 8, 25, 16, tzinfo=UTC), price="0.2000")
    _fires, _visible, late_scenarios = score_scenarios((label,), {valid_on: forecast}, (late,))
    assert late_scenarios[0].assumed_fills == 0
    early = _print(created=datetime(2026, 8, 25, 14, tzinfo=UTC), price="0.2000")
    _fires, visible, scenarios = score_scenarios((label,), {valid_on: forecast}, (early,))
    optimistic, base, conservative = scenarios
    assert visible == 1
    assert optimistic.rule_fires == 1
    assert optimistic.assumed_fills == 1
    assert optimistic.equity == Decimal("99.800000")
    assert optimistic.guaranteed_fill is False
    assert optimistic.fidelity == "trade-print"
    assert base.assumed_fills == 0
    assert base.equity == Decimal("100.000000")
    assert conservative.assumed_fills == 0
    assert conservative.equity == Decimal("100.000000")


def test_stored_forecast_rule_does_not_fire_on_trade_prints() -> None:
    scored = load_trade_score(ROOT)
    assert scored.trade_count == 104442
    assert scored.b805_prints_before_decision == 2665
    assert scored.fee_applied is False
    for scenario in scored.scenarios:
        assert scenario.rule_fires == 0
        assert scenario.assumed_fills == 0
        assert scenario.equity == Decimal("100.000000")
        assert scenario.guaranteed_fill is False
        assert scenario.fidelity == "trade-print"


def _print(*, created: datetime, price: str) -> TradePrint:
    return TradePrint(
        trade_id="synthetic",
        ticker="KXHIGHPHIL-26AUG25-B80.5",
        created_at=created,
        fetched_at=created + timedelta(days=30),
        endpoint="https://example.test/markets/trades",
        yes_price=Decimal(price),
        count=Decimal("5.00"),
    )
