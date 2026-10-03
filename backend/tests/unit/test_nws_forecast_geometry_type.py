"""Stored NWS forecast geometry type. No socket and no snapped polygon."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_geometry_type import (
    load_nws_forecast_geometry_type,
    nws_forecast_geometry_type_note,
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
    / "nws_forecast_geometry_type.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert '.get("coordinates")' not in text
    assert 'key == "coordinates"' in text
    assert 'geometry.get("type")' in text


def test_geometry_type_is_not_snapped() -> None:
    found = load_nws_forecast_geometry_type(PUBLIC)
    assert found.value == "Polygon"
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_geometry_type_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The stored string is Polygon." in note
    assert "The hourly body was not used." in note
    assert "Coordinates were not read." in note
    assert "The NWS polygon was not snapped to the HRRR/ECMWF/ensemble grid." in note
    assert "The string was not rewritten into another word." in note
    assert "A missing string was not invented." in note
    assert "It was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
