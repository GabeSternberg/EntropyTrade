"""Distinct candlestick volumes. No socket and no threshold."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.volume_values import load_volume_values, volume_values_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "volume_values.py"
)
_SHA256 = "4cc28b60c016a333deb76eb2be4c421b143d73a267ed42e3e7866bad531fb9bf"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_distinct_volumes_are_not_a_threshold() -> None:
    found = load_volume_values(PUBLIC)
    assert found.volumes == 5529
    assert found.distinct == 3023
    assert found.skipped == ()
    assert found.smallest == Decimal("0.00")
    assert found.largest == Decimal("35960.16")
    digest = "\n".join(format(item, "f") for item in found.values)
    assert hashlib.sha256(digest.encode()).hexdigest() == _SHA256
    assert found.traded is False
    assert found.promoted is False
    note = volume_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| trade volume | no stored value |" in text
    assert "Volume is not a size at the touch." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
