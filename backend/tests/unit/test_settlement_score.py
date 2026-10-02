"""Baselines and replay on CLI labels. The test does not open a socket."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_cli_aligned_baselines_do_not_fit_or_trade() -> None:
    score = load_aligned_score(ROOT)
    assert score.scored_days == 40
    assert score.mae == Decimal("2.9925")
    assert score.mae_first_half == Decimal("2.94")
    assert score.mae_second_half == Decimal("3.045")
    assert score.probability_days == 39
    assert score.brier_raw == Decimal("0.05128205128205128205128205128")
    assert score.brier_climatology == Decimal("0.06005699903574191900593262792")
    assert score.brier_calibrated == Decimal("0.05280102438781537178926993164")
    assert score.forecast_signal_days == 0
    assert score.sized_books_in_window == 0
    assert score.replay_fills == 0
    assert score.replay_equity == Decimal("100.000000")
    assert score.model_gate_open is True
    assert score.fitted_model is False
    assert score.promoted is False


def test_the_scorer_does_not_fetch() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/settlement_score.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "import socket", "api.elections.kalshi.com"):
        assert name not in text
