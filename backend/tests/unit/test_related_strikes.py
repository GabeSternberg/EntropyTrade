"""Stored candlestick strike suffixes. No socket and no invented bracket."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.related_strikes import load_related_strikes, related_strikes_note
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "exchange" / "related_strikes.py"
)
_STRIKES = (
    "B61.5",
    "B62.5",
    "B63.5",
    "B64.5",
    "B65.5",
    "B66.5",
    "B67.5",
    "B68.5",
    "B69.5",
    "B70.5",
    "B71.5",
    "B72.5",
    "B73.5",
    "B74.5",
    "B75.5",
    "B76.5",
    "B77.5",
    "B78.5",
    "B79.5",
    "B81.5",
    "B82.5",
    "B83.5",
    "B84.5",
    "B85.5",
    "B86.5",
    "B87.5",
    "B88.5",
    "B89.5",
    "B90.5",
    "B91.5",
    "B92.5",
    "B93.5",
    "B94.5",
    "B95.5",
    "T61",
    "T62",
    "T63",
    "T64",
    "T65",
    "T68",
    "T69",
    "T70",
    "T71",
    "T72",
    "T74",
    "T75",
    "T76",
    "T77",
    "T78",
    "T79",
    "T80",
    "T81",
    "T82",
    "T83",
    "T84",
    "T85",
    "T86",
    "T87",
    "T88",
    "T89",
    "T90",
    "T91",
    "T93",
    "T95",
    "T96",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_stored_strikes_do_not_invent_a_neighbor() -> None:
    found = load_related_strikes(PUBLIC)
    assert found.files == 230
    assert found.strikes == _STRIKES
    assert "B80.5" not in found.strikes
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = related_strikes_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| related temperature strikes | no stored value |" in text
    assert "B80.5 is absent." in note
    assert "No neighbor bracket was invented." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
