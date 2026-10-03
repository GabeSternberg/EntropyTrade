"""Stored candlestick closes. No socket and no order book."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_quotes import candle_quotes_note, load_candle_quotes
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "candle_quotes.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_candle_closes_are_not_an_order_book() -> None:
    found = load_candle_quotes(PUBLIC)
    assert found.files == 230
    assert found.candlesticks == 5529
    assert found.bids == 5529
    assert found.asks == 5529
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    folder = PUBLIC / "kalshi-public" / "cli-window" / "candles"
    assert any("0.0000" in path.read_text(encoding="utf-8") for path in folder.glob("*.json"))
    note = candle_quotes_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| Kalshi bid | no stored value |" in text
    assert "| Kalshi ask | no stored value |" in text
    assert "A candle is not an order book." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
