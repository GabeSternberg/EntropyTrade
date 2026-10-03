"""The stored Philadelphia cloud-cover archive. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.cloud_cover import cloud_cover_note, load_cloud_cover
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "cloud_cover.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_cloud_cover_is_stored_and_not_traded() -> None:
    archive = load_cloud_cover(PUBLIC)
    assert archive.http_status == 200
    assert archive.field == "cloud_cover_previous_day1"
    assert archive.hours == 960
    assert archive.nulls == 0
    assert len(archive.times) == 960
    assert len(archive.values) == 960
    assert archive.first_time == "2026-08-24T00:00"
    assert archive.last_time == "2026-10-02T23:00"
    assert archive.first_value == Decimal(76)
    assert archive.last_value == Decimal(100)
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
    humidity = (PUBLIC / "open-meteo" / "humidity-previous-day1.json").read_text(encoding="utf-8")
    assert "cloud_cover_previous_day1" not in previous
    assert "cloud_cover_previous_day1" not in humidity
    note = cloud_cover_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| cloud cover | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
