"""Stored NWS forecast generator. No socket and no rewritten words."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_generator import (
    load_nws_forecast_generator,
    nws_forecast_generator_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "nws_forecast_generator.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert 'properties.get("forecastGenerator")' in text


def test_forecast_generator_is_not_rewritten() -> None:
    found = load_nws_forecast_generator(PUBLIC)
    assert found.value == "BaselineForecastGenerator"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_generator_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored string is BaselineForecastGenerator." in note
    assert "The hourly body was not used." in note
    assert "The string was not rewritten into another word." in note
    assert "A missing string was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
