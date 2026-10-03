"""The stored ncep_hrrr_conus previous day. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.ncep_hrrr_previous import (
    load_ncep_hrrr_previous,
    ncep_hrrr_previous_note,
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
    / "ncep_hrrr_previous.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_hrrr_previous_day_is_stored_and_not_traded() -> None:
    found = load_ncep_hrrr_previous(PUBLIC)
    assert found.http_status == 200
    assert found.model == "ncep_hrrr_conus"
    assert found.hours == 24
    assert found.nulls == 0
    assert found.first_time == "2026-10-02T00:00"
    assert found.last_time == "2026-10-02T23:00"
    assert found.first_value == Decimal("70.4")
    assert found.last_value == Decimal("78.8")
    assert found.unit == "°F"
    assert found.requested_latitude == "39.87"
    assert found.requested_longitude == "-75.23"
    assert found.response_latitude == Decimal("39.863625")
    assert found.response_longitude == Decimal("-75.22328")
    assert found.timezone == "GMT"
    assert found.traded is False
    assert found.promoted is False
    note = ncep_hrrr_previous_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| HRRR where available | no stored value |" in text
    assert "| forecast changes/revisions | no stored value |" in text
    assert "It was not aligned to the CLI decision clock." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
