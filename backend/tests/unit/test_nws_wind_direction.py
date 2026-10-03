"""Distinct NWS wind directions. No socket and no degree conversion."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_wind_direction import (
    load_nws_wind_direction,
    nws_wind_direction_note,
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
    / "nws_wind_direction.py"
)
_VALUES = ("E", "N", "NE", "NW", "S", "SW", "W")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_wind_directions_are_not_degrees() -> None:
    found = load_nws_wind_direction(PUBLIC)
    assert found.periods == 156
    assert len(found.skipped) == 52
    assert found.skipped[0].start == "2026-10-04T22:00:00-04:00"
    assert found.skipped[-1].start == "2026-10-09T06:00:00-04:00"
    assert {item.reason for item in found.skipped} == {"missing wind direction"}
    assert found.values == _VALUES
    assert found.traded is False
    assert found.promoted is False
    note = nws_wind_direction_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| wind | no stored value |" in text
    assert "In alphabetical order they are E, N, NE, NW, S, SW, W." in note
    assert "A direction was not converted into degrees." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
