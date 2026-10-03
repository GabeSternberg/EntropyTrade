"""Distinct NWS precipitation probabilities. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_precipitation_probability import (
    load_nws_precipitation_probability,
    nws_precipitation_probability_note,
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
    / "nws_precipitation_probability.py"
)
_VALUES = ("0", "1", "2", "3", "4", "5", "7", "9", "11", "12", "15", "30", "39", "66")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "/ 100" not in text
    assert " / Decimal(100)" not in text


def test_precipitation_probabilities_are_not_a_market_probability() -> None:
    found = load_nws_precipitation_probability(PUBLIC)
    assert found.periods == 156
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.traded is False
    assert found.promoted is False
    note = nws_precipitation_probability_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The smallest is 0 and the largest is 66." in note
    assert "was not divided by 100" in note
    assert "was not called a market probability." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
