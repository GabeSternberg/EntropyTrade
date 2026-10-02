"""Stored IEM CLI products. The test does not open a socket."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.cli_observations import load_comparison

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_cli_labels_are_after_the_observation_day() -> None:
    labels, study = load_comparison(ROOT)
    assert study.final_labels == 40
    assert study.preliminary_skipped == 38
    assert study.revised_days == 0
    assert study.contract_source == "The Weather Company"
    for label in labels:
        assert label.source == "iem-nws-cli"
        assert label.endpoint.startswith("https://mesonet.agron.iastate.edu/")
        assert label.available_at.date() > label.valid_on
        assert "open-meteo" not in label.source
    august = next(label for label in labels if label.valid_on == date(2026, 8, 25))
    assert august.high_f == Decimal(80)
    assert august.available_at.isoformat() == "2026-08-26T06:14:00+00:00"


def test_cli_matches_official_results_and_open_meteo_does_not() -> None:
    _labels, study = load_comparison(ROOT)
    assert study.archive_days == 40
    assert study.archive_exact_disagreements == 40
    assert study.archive_rounded_disagreements == 39
    assert study.archive_mean_absolute_difference == Decimal("2.19")
    assert study.b80_markets == 9
    assert study.b80_cli_disagreements == 0
    assert study.b80_archive_disagreements == 1
    assert study.nearby_markets == 222
    assert study.nearby_cli_disagreements == 0
    assert study.nearby_archive_disagreements == 50


def test_the_loader_does_not_fetch() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/cli_observations.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "import socket", "api.elections.kalshi.com"):
        assert name not in text
