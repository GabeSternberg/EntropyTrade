"""Distinct candlestick ask closes. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.ask_values import ask_values_note, load_ask_values
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "ask_values.py"
)
_VALUES = (
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
    "0.3500",
    "0.3600",
    "0.3700",
    "0.3800",
    "0.3900",
    "0.4000",
    "0.4100",
    "0.4200",
    "0.4300",
    "0.4400",
    "0.4500",
    "0.4600",
    "0.4700",
    "0.4800",
    "0.4900",
    "0.5000",
    "0.5100",
    "0.5200",
    "0.5300",
    "0.5400",
    "0.5500",
    "0.5600",
    "0.5700",
    "0.5800",
    "0.5900",
    "0.6000",
    "0.6100",
    "0.6200",
    "0.6300",
    "0.6400",
    "0.6500",
    "0.6600",
    "0.6700",
    "0.6800",
    "0.6900",
    "0.7000",
    "0.7100",
    "0.7200",
    "0.7300",
    "0.7400",
    "0.7500",
    "0.7600",
    "0.7700",
    "0.7800",
    "0.7900",
    "0.8000",
    "0.8100",
    "0.8200",
    "0.8300",
    "0.8400",
    "0.8500",
    "0.8600",
    "0.8700",
    "0.8800",
    "0.8900",
    "0.9000",
    "0.9100",
    "0.9200",
    "0.9300",
    "0.9400",
    "0.9500",
    "0.9600",
    "0.9700",
    "0.9800",
    "0.9900",
    "1.0000",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_distinct_ask_closes_are_not_a_threshold() -> None:
    found = load_ask_values(PUBLIC)
    assert found.asks == 5529
    assert found.distinct == 100
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.smallest == Decimal("0.0100")
    assert found.largest == Decimal("1.0000")
    assert "0.0000" not in _VALUES
    assert found.traded is False
    assert found.promoted is False
    note = ask_values_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| Kalshi ask | no stored value |" in text
    assert "A candle is not an order book." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
