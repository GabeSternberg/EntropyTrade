"""The stored public pull. The test reads files and does not open a socket."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.public_dataset import load_study

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
FAILURE_BODY = (
    '{"reason":"Invalid value: Cannot initialize ForecastVariableDaily from invalid '
    'String value temperature_2m_max_previous_day1","error":true}'
)


def test_rows_keep_availability_source_and_endpoint() -> None:
    study = load_study(ROOT)
    assert study.failures[0].status == 400
    assert study.failures[0].body == FAILURE_BODY
    assert "api.elections.kalshi.com" not in study.failures[0].endpoint
    kinds = {row.kind for row in study.rows}
    assert kinds == {"forecast_hour", "archive_day", "market", "candle", "orderbook"}
    for row in study.rows:
        assert row.available_at.tzinfo is not None
        assert row.source in {"open-meteo", "kalshi-demo"}
        assert row.endpoint.startswith("https://")
        assert row.available_at_basis
    orderbook = next(row for row in study.rows if row.kind == "orderbook")
    assert orderbook.yes_bid is None
    assert orderbook.yes_ask is None
    for archive in (row for row in study.rows if row.kind == "archive_day"):
        hours = [
            row
            for row in study.rows
            if row.kind == "forecast_hour" and row.record_id.startswith(archive.record_id)
        ]
        assert hours
        assert all(hour.available_at + timedelta(days=1) < archive.available_at for hour in hours)


def test_baselines_and_replay_use_only_the_stored_rows() -> None:
    study = load_study(ROOT)
    assert study.scored_days == 40
    assert study.mae == Decimal("1.4725")
    assert study.mae_first_half == Decimal("1.315")
    assert study.mae_second_half == Decimal("1.63")
    assert study.probability_days == 39
    assert study.brier_raw == Decimal("0.05128205128205128205128205128")
    assert study.brier_climatology == Decimal("0.05036444892650982740970468118")
    assert study.brier_calibrated == Decimal("0.05072391959520405119825128533")
    assert study.brier_market == Decimal("0.7744")
    assert study.market_days == 1
    assert study.fitted_model_refused is False
    assert study.official_days == 9
    assert study.official_disagreements == 1
    assert study.sized_books == 1
    assert study.forecast_signal_days == 0
    assert study.label_hidden_at_decision is True
    assert study.forecast_latency_0_fee_0.fills == 0
    assert study.forecast_latency_0_fee_0.ending_equity == Decimal("100")
    assert study.forecast_latency_0_fee_002.ending_equity == Decimal("100")
    assert study.forecast_latency_2h_fee_0.ending_equity == Decimal("100")
    assert study.ask_probe_latency_0_fee_0.fills == 1
    assert study.ask_probe_latency_0_fee_0.ending_equity == Decimal("100.85")
    assert study.ask_probe_latency_0_fee_002.fills == 1
    assert study.ask_probe_latency_0_fee_002.ending_equity == Decimal("100.84")
    assert study.ask_probe_latency_2h_fee_0.fills == 0
    assert study.ask_probe_latency_2h_fee_0.ending_equity == Decimal("100")


def test_the_loader_does_not_name_a_client() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/public_dataset.py")
        .read_text(encoding="utf-8")
    )
    for name in (
        "import urllib",
        "import httpx",
        "import socket",
        "api.elections.kalshi.com",
        "attempt_submit",
    ):
        assert name not in text
