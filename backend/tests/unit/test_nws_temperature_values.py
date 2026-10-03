"""Distinct NWS hourly temperatures. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_temperature_values import (
    load_nws_temperature_values,
    nws_temperature_values_note,
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
    / "nws_temperature_values.py"
)
_VALUES = tuple(str(value) for value in range(46, 74))


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_nws_hourly_temperatures_are_not_a_threshold() -> None:
    found = load_nws_temperature_values(PUBLIC)
    assert found.periods == 156
    assert found.skipped == ()
    assert len(found.values) == 28
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.traded is False
    assert found.promoted is False
    note = nws_temperature_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The smallest is 46 and the largest is 73." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
