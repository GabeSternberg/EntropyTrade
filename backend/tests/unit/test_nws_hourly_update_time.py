"""Stored NWS hourly updateTime. No socket and no parsed clock."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_hourly_update_time import (
    load_nws_hourly_update_time,
    nws_hourly_update_time_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"


def test_hourly_update_time_is_not_a_decision_clock() -> None:
    found = load_nws_hourly_update_time(PUBLIC)
    assert found.value == "2026-10-02T20:10:39+00:00"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_hourly_update_time_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored string is 2026-10-02T20:10:39+00:00." in note
    assert "The 14-period forecast body was not used." in note
    assert "The string was not parsed into a clock." in note
    assert "It was not used as a decision clock." in note
    assert "A missing string was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
