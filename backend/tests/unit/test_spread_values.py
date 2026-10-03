"""Distinct candlestick spreads. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.spread_values import load_spread_values, spread_values_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "spread_values.py"
)
_VALUES = (
    "0.0100",
    "0.0200",
    "0.0300",
    "0.0400",
    "0.0500",
    "0.0600",
    "0.0700",
    "0.0800",
    "0.0900",
    "0.1000",
    "0.1100",
    "0.1200",
    "0.1300",
    "0.1400",
    "0.1500",
    "0.1600",
    "0.1700",
    "0.1900",
    "0.2000",
    "0.2100",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_distinct_spreads_are_not_a_threshold() -> None:
    found = load_spread_values(PUBLIC)
    assert found.spreads == 5529
    assert found.distinct == 20
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.smallest == Decimal("0.0100")
    assert found.largest == Decimal("0.2100")
    assert "0.1800" not in _VALUES
    assert found.traded is False
    assert found.promoted is False
    note = spread_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| spread | no stored value |" in text
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
