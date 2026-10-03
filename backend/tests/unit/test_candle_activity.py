"""Stored candlestick volume and open interest. No socket and no touch size."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_activity import candle_activity_note, load_candle_activity
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "candle_activity.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_candle_activity_is_not_a_touch_size() -> None:
    found = load_candle_activity(PUBLIC)
    assert found.files == 230
    assert found.candlesticks == 5529
    assert found.volumes == 5529
    assert found.open_interest == 5529
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    folder = PUBLIC / "kalshi-public" / "cli-window" / "candles"
    assert any('"0.00"' in path.read_text(encoding="utf-8") for path in folder.glob("*.json"))
    note = candle_activity_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| trade volume | no stored value |" in text
    assert "| open interest | no stored value |" in text
    assert "Volume is not a size at the touch." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
