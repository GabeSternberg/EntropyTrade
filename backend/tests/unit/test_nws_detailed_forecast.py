"""Distinct NWS detailed forecasts. No socket and no rewritten words."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_detailed_forecast import (
    load_nws_detailed_forecast,
    nws_detailed_forecast_note,
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
    / "nws_detailed_forecast.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "detailedForecast" in text


def test_empty_detailed_forecasts_are_not_filled_in() -> None:
    found = load_nws_detailed_forecast(PUBLIC)
    assert found.periods == 156
    assert found.values == ()
    assert len(found.skipped) == 156
    assert found.skipped[0].start == "2026-10-03T03:00:00-04:00"
    assert found.skipped[-1].start == "2026-10-09T14:00:00-04:00"
    assert {item.reason for item in found.skipped} == {"missing detailed forecast"}
    assert found.traded is False
    assert found.promoted is False
    note = nws_detailed_forecast_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "0 distinct values." in note
    assert "In alphabetical order there are no strings." in note
    assert "A forecast was not rewritten into another word." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
