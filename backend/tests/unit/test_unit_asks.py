"""Candlestick asks of exactly 1. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.unit_asks import load_unit_asks, unit_asks_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "unit_asks.py"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_unit_asks_are_not_a_settlement() -> None:
    found = load_unit_asks(PUBLIC)
    assert found.asks == 5529
    assert found.ones == 143
    assert found.first == "KXHIGHPHIL-26AUG23-B84.5#22"
    assert found.last == "KXHIGHPHIL-26SEP30-B76.5#24"
    assert found.traded is False
    assert found.promoted is False
    note = unit_asks_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| Kalshi ask | no stored value |" in text
    assert "1.0000 is not a settlement and is not a probability." in note
    assert "A candle is not an order book." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
