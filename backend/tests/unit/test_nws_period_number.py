"""Distinct NWS period numbers. No socket and no invented integers."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_period_number import (
    load_nws_period_number,
    nws_period_number_note,
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
    / "nws_period_number.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert 'period.get("number")' in text
    assert "isinstance(raw, bool)" in text


def test_period_numbers_are_not_a_threshold() -> None:
    found = load_nws_period_number(PUBLIC)
    assert found.periods == 156
    assert found.values == tuple(range(1, 157))
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_period_number_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "156 distinct values." in note
    assert "In ascending order they are 1, 2, 3," in note
    assert note.endswith("Nothing was promoted.")
    assert ", 156." in note
    assert "A missing number was not invented." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
