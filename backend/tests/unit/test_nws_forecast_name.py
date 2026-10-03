"""Distinct NWS forecast names. No socket and no rewritten words."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_name import (
    load_nws_forecast_name,
    nws_forecast_name_note,
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
    / "nws_forecast_name.py"
)
_VALUES = (
    "Friday",
    "Monday",
    "Monday Night",
    "Saturday",
    "Saturday Night",
    "Sunday",
    "Sunday Night",
    "Thursday",
    "Thursday Night",
    "Tonight",
    "Tuesday",
    "Tuesday Night",
    "Wednesday",
    "Wednesday Night",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert 'period.get("name")' in text


def test_forecast_names_stay_in_alphabetical_order() -> None:
    found = load_nws_forecast_name(PUBLIC)
    assert found.periods == 14
    assert found.values == _VALUES
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_name_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "14 distinct values." in note
    assert "Friday, Monday, Monday Night" in note
    assert "The hourly body was not used." in note
    assert "A name was not rewritten into another word." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
