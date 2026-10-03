"""The stored Philadelphia humidity archive. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.humidity import humidity_note, load_humidity
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "humidity.py"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_humidity_is_stored_and_not_traded() -> None:
    archive = load_humidity(PUBLIC)
    assert archive.http_status == 200
    assert archive.field == "relative_humidity_2m_previous_day1"
    assert archive.hours == 960
    assert archive.nulls == 0
    assert len(archive.times) == 960
    assert len(archive.values) == 960
    assert archive.first_time == "2026-08-24T00:00"
    assert archive.last_time == "2026-10-02T23:00"
    assert archive.first_value == Decimal(65)
    assert archive.last_value == Decimal(65)
    assert archive.unit == "%"
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
    dew = (PUBLIC / "open-meteo" / "dew-point-previous-day1.json").read_text(encoding="utf-8")
    assert "relative_humidity_2m_previous_day1" not in previous
    assert "relative_humidity_2m_previous_day1" not in dew
    note = humidity_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| humidity | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
