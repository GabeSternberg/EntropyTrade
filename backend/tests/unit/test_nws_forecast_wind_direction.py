"""Distinct NWS forecast wind directions. No socket and no degrees."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_wind_direction import (
    load_nws_forecast_wind_direction,
    nws_forecast_wind_direction_note,
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
    / "nws_forecast_wind_direction.py"
)
_VALUES = ("E", "N", "NE", "NW", "SW", "W")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "windDirection" in text


def test_directions_are_not_converted_into_degrees() -> None:
    found = load_nws_forecast_wind_direction(PUBLIC)
    assert found.periods == 14
    assert found.values == _VALUES
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_wind_direction_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| wind | no stored value |" in text
    assert "6 distinct values." in note
    assert "In alphabetical order they are E, N, NE, NW, SW, W." in note
    assert "The hourly body was not used." in note
    assert "A direction was not converted into degrees." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
