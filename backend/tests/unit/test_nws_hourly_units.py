"""Stored NWS hourly units. No socket and no converted scale."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_hourly_units import (
    load_nws_hourly_units,
    nws_hourly_units_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"


def test_hourly_units_are_not_converted() -> None:
    found = load_nws_hourly_units(PUBLIC)
    assert found.value == "us"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_hourly_units_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored string is us." in note
    assert "The 14-period forecast body was not used." in note
    assert "A unit was not converted into another scale." in note
    assert "A missing string was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
