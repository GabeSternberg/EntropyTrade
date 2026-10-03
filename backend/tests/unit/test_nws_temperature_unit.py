"""Distinct NWS temperature units. No socket and no scale conversion."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_temperature_unit import (
    load_nws_temperature_unit,
    nws_temperature_unit_note,
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
    / "nws_temperature_unit.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "temperatureUnit" in text
    assert "Celsius" not in text
    assert "1.8" not in text


def test_the_unit_string_is_not_converted() -> None:
    found = load_nws_temperature_unit(PUBLIC)
    assert found.periods == 156
    assert found.values == ("F",)
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_temperature_unit_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "1 distinct values." in note
    assert "In alphabetical order they are F." in note
    assert "A unit was not converted into another scale." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
