"""Distinct candlestick open interest. No socket and no threshold."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.interest_values import interest_values_note, load_interest_values
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "interest_values.py"
)
_SHA256 = "612efff39fa2ba61230bad93320693b06bdc7df130e01936dcb2cd353385d071"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_distinct_open_interest_is_not_a_threshold() -> None:
    found = load_interest_values(PUBLIC)
    assert found.rows == 5529
    assert found.distinct == 3846
    assert found.skipped == ()
    assert found.smallest == Decimal("1.00")
    assert found.largest == Decimal("39211.47")
    assert Decimal("0.00") not in found.values
    digest = "\n".join(format(item, "f") for item in found.values)
    assert hashlib.sha256(digest.encode()).hexdigest() == _SHA256
    assert found.traded is False
    assert found.promoted is False
    note = interest_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| open interest | no stored value |" in text
    assert "Open interest is not a size at the touch." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
