"""Candlestick bids of exactly 0. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.zero_bids import load_zero_bids, zero_bids_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "zero_bids.py"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_zero_bids_are_not_a_fill() -> None:
    found = load_zero_bids(PUBLIC)
    assert found.bids == 5529
    assert found.zeros == 1912
    assert found.first == "KXHIGHPHIL-26AUG23-B82.5#21"
    assert found.last == "KXHIGHPHIL-26SEP30-T83#24"
    assert found.traded is False
    assert found.promoted is False
    note = zero_bids_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| Kalshi bid | no stored value |" in text
    assert "0.0000 is not a fill." in note
    assert "A candle is not an order book." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
