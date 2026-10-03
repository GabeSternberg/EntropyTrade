"""Stored candlestick price changes. No socket and no comparison to 0.40."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_change import candle_change_note, load_candle_changes
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "candle_change.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_price_changes_are_not_compared_to_the_print_threshold() -> None:
    found = load_candle_changes(PUBLIC)
    assert found.files == 230
    assert found.candlesticks == 5529
    assert found.changes == 4064
    assert found.zeros == 1237
    assert found.negatives == 1433
    assert len(found.skipped) == 1465
    assert found.skipped[0] == "KXHIGHPHIL-26AUG23-B82.5#1: missing price change"
    assert found.first_time == "KXHIGHPHIL-26AUG23-B82.5#0"
    assert found.first_change == Decimal("-0.0200")
    assert found.last_time == "KXHIGHPHIL-26SEP30-T83#21"
    assert found.last_change == Decimal("0.0000")
    assert found.traded is False
    assert found.promoted is False
    note = candle_change_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| market price change | no stored value |" in text
    assert "A change was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
