"""Distinct NWS relative humidity. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_relative_humidity import (
    load_nws_relative_humidity,
    nws_relative_humidity_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "nws_relative_humidity.py"
)
_VALUES = (
    "46",
    "48",
    "50",
    "51",
    "52",
    "53",
    "54",
    "55",
    "56",
    "57",
    "59",
    "60",
    "61",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "70",
    "71",
    "72",
    "73",
    "74",
    "75",
    "77",
    "78",
    "79",
    "80",
    "81",
    "83",
    "84",
    "86",
    "87",
    "89",
    "90",
    "93",
    "97",
    "100",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "/ 100" not in text
    assert " / Decimal(100)" not in text


def test_relative_humidity_is_not_a_threshold() -> None:
    found = load_nws_relative_humidity(PUBLIC)
    assert found.periods == 156
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.traded is False
    assert found.promoted is False
    note = nws_relative_humidity_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| humidity | no stored value |" in text
    assert "The smallest is 46 and the largest is 100." in note
    assert "A value was not divided by 100." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
