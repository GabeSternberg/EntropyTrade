"""Stored candlestick price closes. No socket and no probability."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_price import candle_price_note, load_candle_prices
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "candle_price.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_price_closes_are_not_a_probability() -> None:
    found = load_candle_prices(PUBLIC)
    assert found.files == 230
    assert found.candlesticks == 5529
    assert found.closes == 4064
    assert len(found.skipped) == 1465
    assert found.skipped[0] == "KXHIGHPHIL-26AUG23-B82.5#1: missing price close"
    assert found.traded is False
    assert found.promoted is False
    note = candle_price_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| market probability | no stored value |" in text
    assert "It was not called a probability." in note
    assert "A close was not compared to 0.40." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
