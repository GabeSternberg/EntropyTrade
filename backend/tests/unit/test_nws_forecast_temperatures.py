"""Distinct NWS forecast-period temperatures. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_temperatures import (
    load_nws_forecast_temperatures,
    nws_forecast_temperatures_note,
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
    / "nws_forecast_temperatures.py"
)
_VALUES = ("45", "49", "53", "58", "59", "61", "62", "65", "68", "70", "71", "73")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "The hourly body is not used." in text


def test_nws_forecast_temperatures_are_not_a_threshold() -> None:
    found = load_nws_forecast_temperatures(PUBLIC)
    assert found.periods == 14
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_temperatures_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The smallest is 45 and the largest is 73." in note
    assert "The hourly body was not used." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
