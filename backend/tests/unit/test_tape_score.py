"""Rescore on the CLI labels and the broader tape. No socket and no promotion."""

from decimal import Decimal
from pathlib import Path

from entropytrade.execution.published_fees import QUADRATIC_COEFFICIENT
from entropytrade.weather.tape_score import load_tape_rescore

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_the_broader_tape_still_does_not_trade() -> None:
    score = load_tape_rescore(ROOT)
    assert score.scored_days == 40
    assert score.mae == Decimal("2.9925")
    assert score.forecast_signal_days == 0
    assert score.sized_books_before_label == 0
    assert score.empty_books_in_window == 240
    assert score.candles_stored == 230
    assert score.replay_fills == 0
    assert score.replay_equity == Decimal("100.000000")
    assert score.equity_at_two_hour_latency == Decimal("100.000000")
    assert score.trades is False
    assert score.fee_model_version == "series-fields-v1"
    assert score.published_fee_version == "kalshi-docs-maker-fractions-v1"
    assert score.series_fee_type == "quadratic"
    assert score.maker_fraction == Decimal(0)
    assert score.quadratic_coefficient is None
    assert QUADRATIC_COEFFICIENT is None
    assert score.fitted_model is False
    assert score.promoted is False
    predictive, incremental, edge, stability, sensitivity = score.questions()
    assert "0 days" in predictive
    assert "does not beat the raw forecast" in incremental
    assert "does not trade" in edge
    assert "2.94" in stability
    assert "3.045" in stability
    assert "unpublished coefficient was not swept" in sensitivity


def test_the_rescore_does_not_fetch() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/tape_score.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "import socket", "0.07"):
        assert name not in text
