"""Distinct NWS wind-speed strings. No socket and no numeric parse."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_wind_speed import load_nws_wind_speed, nws_wind_speed_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_wind_speed.py"
)
_VALUES = ("0 mph", "10 mph", "5 mph")


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "int(" not in text
    assert "float(" not in text


def test_wind_speed_strings_are_not_parsed() -> None:
    found = load_nws_wind_speed(PUBLIC)
    assert found.periods == 156
    assert found.skipped == ()
    assert found.values == _VALUES
    assert found.traded is False
    assert found.promoted is False
    note = nws_wind_speed_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| wind | no stored value |" in text
    assert "In alphabetical order they are 0 mph, 10 mph, 5 mph." in note
    assert "A string was not parsed into a number." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
