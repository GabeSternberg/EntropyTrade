"""Stored NWS hourly coordinate count. No socket and no snapped point."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_hourly_coordinate_count import (
    load_nws_hourly_coordinate_count,
    nws_hourly_coordinate_count_note,
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
    / "nws_hourly_coordinate_count.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "load_nws_forecast" not in text
    assert "format(" not in text
    assert "load_nws_hourly" in text
    assert 'geometry.get("coordinates")' in text


def test_hourly_coordinate_count_is_not_a_grid() -> None:
    found = load_nws_hourly_coordinate_count(PUBLIC)
    assert found.rings == 1
    assert found.positions == 5
    assert found.skipped == 0
    assert found.reason is None
    assert found.traded is False
    assert found.promoted is False
    note = nws_hourly_coordinate_count_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "1 rings were stored." in note
    assert "5 positions were lists of numbers." in note
    assert "0 positions were not lists of numbers." in note
    assert "The 14-period forecast body was not used." in note
    assert "A longitude was not recorded." in note
    assert "A latitude was not recorded." in note
    assert "The NWS polygon was not snapped to the HRRR/ECMWF/ensemble grid." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
