"""Stored candlestick spreads. No socket and no comparison to 0.40."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import candle_spread_note, load_candle_spreads
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "candle_spread.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_spreads_are_not_compared_to_the_print_threshold() -> None:
    found = load_candle_spreads(PUBLIC)
    assert found.files == 230
    assert found.candlesticks == 5529
    assert found.spreads == 5529
    assert found.zeros == 0
    assert found.negatives == 0
    assert found.skipped == ()
    assert found.first_time == "KXHIGHPHIL-26AUG23-B82.5#0"
    assert found.first_spread == Decimal("0.0300")
    assert found.last_time == "KXHIGHPHIL-26SEP30-T83#24"
    assert found.last_spread == Decimal("0.0100")
    assert found.traded is False
    assert found.promoted is False
    note = candle_spread_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| spread | no stored value |" in text
    assert "The spread was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
