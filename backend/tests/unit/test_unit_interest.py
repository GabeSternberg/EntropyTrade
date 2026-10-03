"""Open interest of exactly 1. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.unit_interest import load_unit_interest, unit_interest_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "unit_interest.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_unit_open_interest_is_not_a_touch_size() -> None:
    found = load_unit_interest(PUBLIC)
    assert found.rows == 5529
    assert found.ones == 1
    assert found.first == "KXHIGHPHIL-26SEP09-B84.5#0"
    assert found.last == found.first
    assert found.traded is False
    assert found.promoted is False
    note = unit_interest_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| open interest | no stored value |" in text
    assert "1.00 is not a size at the touch." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
