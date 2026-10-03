"""Stored order books. No socket and no invented level."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.book_imbalance import book_imbalance_note, load_book_imbalance
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "book_imbalance.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_empty_books_do_not_get_an_imbalance() -> None:
    found = load_book_imbalance(PUBLIC)
    assert found.books == 240
    assert found.imbalances == 0
    assert len(found.skipped) == 240
    assert found.skipped[0] == "KXHIGHPHIL-26AUG23-B80.5: empty side"
    assert sum(item.endswith("no stored body") for item in found.skipped) == 239
    assert sum(item.endswith("empty side") for item in found.skipped) == 1
    assert found.traded is False
    assert found.promoted is False
    note = book_imbalance_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| order-book imbalance | no stored value |" in text
    assert "so no imbalance was computed." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
