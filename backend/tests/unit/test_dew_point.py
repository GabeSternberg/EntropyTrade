"""The stored Philadelphia dew-point archive. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.dew_point import dew_point_note, load_dew_point
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "dew_point.py"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_dew_point_is_stored_and_not_traded() -> None:
    archive = load_dew_point(PUBLIC)
    assert archive.http_status == 200
    assert archive.field == "dew_point_2m_previous_day1"
    assert archive.hours == 960
    assert archive.nulls == 0
    assert len(archive.times) == 960
    assert len(archive.values) == 960
    assert archive.first_time == "2026-08-24T00:00"
    assert archive.last_time == "2026-10-02T23:00"
    assert archive.first_value == Decimal("63.1")
    assert archive.last_value == Decimal("66.1")
    assert archive.unit == "°F"
    assert archive.requested_latitude == "39.87"
    assert archive.requested_longitude == "-75.23"
    assert archive.response_latitude == Decimal("39.863625")
    assert archive.response_longitude == Decimal("-75.22328")
    assert archive.timezone == "GMT"
    assert archive.has_issue_time is False
    assert archive.traded is False
    assert archive.promoted is False
    assert all(not item.startswith("2026-08-23") for item in archive.times)
    previous = (PUBLIC / "open-meteo" / "previous-runs.json").read_text(encoding="utf-8")
    vintages = (PUBLIC / "open-meteo" / "revision-vintages.json").read_text(encoding="utf-8")
    assert "dew_point_2m_previous_day1" not in previous
    assert "dew_point" not in vintages
    note = dew_point_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| dew point | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
