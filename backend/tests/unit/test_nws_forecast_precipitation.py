"""Distinct NWS forecast precipitation probabilities. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_precipitation import (
    load_nws_forecast_precipitation,
    nws_forecast_precipitation_note,
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
    / "nws_forecast_precipitation.py"
)
_VALUES = (0, 1, 4, 5, 60, 66)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "/ 100" not in text
    assert "probabilityOfPrecipitation" in text


def test_forecast_precipitation_integers_are_not_a_market_probability() -> None:
    found = load_nws_forecast_precipitation(PUBLIC)
    assert found.periods == 14
    assert found.skipped == ()
    assert found.values == _VALUES
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_precipitation_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "6 distinct values." in note
    assert "In ascending order they are 0, 1, 4, 5, 60, 66." in note
    assert "The hourly body was not used." in note
    assert "was not divided by 100" in note
    assert "was not called a market probability." in note
    assert "A missing integer was not invented." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
