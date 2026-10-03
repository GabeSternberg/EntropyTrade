"""Distinct candlestick price changes. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.change_values import change_values_note, load_change_values
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "change_values.py"
)
_VALUES = (
    "-0.9700",
    "-0.8600",
    "-0.7200",
    "-0.7000",
    "-0.6500",
    "-0.5100",
    "-0.4800",
    "-0.4300",
    "-0.4200",
    "-0.4100",
    "-0.4000",
    "-0.3900",
    "-0.3800",
    "-0.3300",
    "-0.3200",
    "-0.3100",
    "-0.3000",
    "-0.2800",
    "-0.2700",
    "-0.2600",
    "-0.2500",
    "-0.2400",
    "-0.2300",
    "-0.2200",
    "-0.2100",
    "-0.2000",
    "-0.1900",
    "-0.1800",
    "-0.1700",
    "-0.1600",
    "-0.1500",
    "-0.1400",
    "-0.1300",
    "-0.1200",
    "-0.1100",
    "-0.1000",
    "-0.0900",
    "-0.0800",
    "-0.0700",
    "-0.0600",
    "-0.0500",
    "-0.0400",
    "-0.0300",
    "-0.0200",
    "-0.0100",
    "0.0000",
    "0.0100",
    "0.0200",
    "0.0300",
    "0.0400",
    "0.0500",
    "0.0600",
    "0.0700",
    "0.0800",
    "0.0900",
    "0.1000",
    "0.1100",
    "0.1200",
    "0.1300",
    "0.1400",
    "0.1500",
    "0.1600",
    "0.1700",
    "0.1800",
    "0.1900",
    "0.2000",
    "0.2100",
    "0.2200",
    "0.2300",
    "0.2400",
    "0.2500",
    "0.2600",
    "0.2700",
    "0.2800",
    "0.2900",
    "0.3000",
    "0.3100",
    "0.3200",
    "0.3300",
    "0.3400",
    "0.3700",
    "0.3800",
    "0.3900",
    "0.4200",
    "0.4500",
    "0.4800",
    "0.5100",
    "0.5500",
    "0.5700",
    "0.6700",
    "0.6900",
    "0.7100",
    "0.8800",
    "0.9800",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_distinct_price_changes_are_not_a_threshold() -> None:
    found = load_change_values(PUBLIC)
    assert found.changes == 3372
    assert found.distinct == 94
    assert len(found.skipped) == 2157
    assert found.skipped[0] == "KXHIGHPHIL-26AUG23-B82.5#0: no previous close"
    assert found.skipped[-1] == "KXHIGHPHIL-26SEP30-T83#24: missing price close"
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.smallest == Decimal("-0.9700")
    assert found.largest == Decimal("0.9800")
    assert found.traded is False
    assert found.promoted is False
    note = change_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| market price change | no stored value |" in text
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
