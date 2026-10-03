"""Distinct NWS forecast icons. No socket and no fetched icons."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_icon import (
    load_nws_forecast_icon,
    nws_forecast_icon_note,
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
    / "nws_forecast_icon.py"
)
_DIGEST = "83d5b259c8c576b4dad34a1626c906a1b826c891631458a731a273e61c099df3"
_FIRST = "https://api.weather.gov/icons/land/day/bkn?size=medium"
_LAST = "https://api.weather.gov/icons/land/night/tsra,60/tsra,30?size=medium"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert 'period.get("icon")' in text


def test_forecast_icons_are_not_fetched() -> None:
    found = load_nws_forecast_icon(PUBLIC)
    assert found.periods == 14
    assert len(found.values) == 9
    assert found.values[0] == _FIRST
    assert found.values[-1] == _LAST
    digest = hashlib.sha256("\n".join(found.values).encode()).hexdigest()
    assert digest == _DIGEST
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_icon_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "9 distinct values." in note
    assert _FIRST in note
    assert _LAST in note
    assert "The hourly body was not used." in note
    assert "An icon was not fetched." in note
    assert "A string was not rewritten into another word." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
