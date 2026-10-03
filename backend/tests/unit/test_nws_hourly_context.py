"""Stored NWS hourly context. No socket and no fetched URL."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_hourly_context import (
    load_nws_hourly_context,
    nws_hourly_context_note,
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
    / "nws_hourly_context.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "load_nws_forecast" not in text
    assert "load_nws_hourly" in text
    assert 'body.get("@context")' in text


def test_hourly_mixed_context_is_not_fetched() -> None:
    found = load_nws_hourly_context(PUBLIC)
    assert found.values == ()
    assert found.reason == "context is not a string"
    assert found.traded is False
    assert found.promoted is False
    note = nws_hourly_context_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "0 strings were stored." in note
    assert "In alphabetical order there are no strings." in note
    assert "The 14-period forecast body was not used." in note
    assert "A URL was not fetched." in note
    assert "A string was not rewritten." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
