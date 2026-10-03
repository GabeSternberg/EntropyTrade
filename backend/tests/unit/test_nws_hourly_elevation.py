"""Stored NWS hourly elevation. No socket and no converted number."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_hourly_elevation import (
    load_nws_hourly_elevation,
    nws_hourly_elevation_note,
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
    / "nws_hourly_elevation.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "load_nws_forecast" not in text
    assert "Celsius" not in text
    assert "1.8" not in text
    assert "0.3048" not in text
    assert "load_nws_hourly" in text
    assert 'properties.get("elevation")' in text


def test_hourly_elevation_is_not_converted() -> None:
    found = load_nws_hourly_elevation(PUBLIC)
    assert found.text is None
    assert found.number == "0.9144"
    assert found.unit == "wmoUnit:m"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_hourly_elevation_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored number is 0.9144 and the stored unit is wmoUnit:m." in note
    assert "The 14-period forecast body was not used." in note
    assert "The number was not converted." in note
    assert "A unit was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
