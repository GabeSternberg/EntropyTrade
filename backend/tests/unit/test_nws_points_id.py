"""Stored NWS points id. No socket and no fetched URL."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_points_id import load_nws_points_id, nws_points_id_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_points_id.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "load_nws_forecast" not in text
    assert "load_nws_hourly" not in text
    assert "forecast-hourly" not in text
    assert "forecast-phi" not in text
    assert 'body.get("id")' in text


def test_points_id_is_not_fetched() -> None:
    found = load_nws_points_id(PUBLIC)
    assert found.value == "https://api.weather.gov/points/39.87,-75.23"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_points_id_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored string is https://api.weather.gov/points/39.87,-75.23." in note
    assert "The forecast body was not used." in note
    assert "The hourly body was not used." in note
    assert "A URL was not fetched." in note
    assert "The string was not rewritten into another word." in note
    assert "A missing string was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
