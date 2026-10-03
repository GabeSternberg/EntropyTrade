"""Distinct NWS forecast wind speeds. No socket and no parsed numbers."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_wind_speed import (
    load_nws_forecast_wind_speed,
    nws_forecast_wind_speed_note,
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
    / "nws_forecast_wind_speed.py"
)
_VALUES = ("0 to 10 mph", "0 to 5 mph", "5 mph", "5 to 10 mph")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "windSpeed" in text
    assert "int(" not in text
    assert "float(" not in text


def test_wind_speed_strings_are_not_parsed() -> None:
    found = load_nws_forecast_wind_speed(PUBLIC)
    assert found.periods == 14
    assert found.values == _VALUES
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_wind_speed_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| wind | no stored value |" in text
    assert "4 distinct values." in note
    assert "0 to 10 mph, 0 to 5 mph, 5 mph, 5 to 10 mph." in note
    assert "The hourly body was not used." in note
    assert "A string was not parsed into a number." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
