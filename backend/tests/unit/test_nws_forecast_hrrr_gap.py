"""NWS forecast periods minus HRRR. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_hrrr_gap import (
    load_nws_forecast_hrrr_gap,
    nws_forecast_hrrr_gap_note,
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
    / "nws_forecast_hrrr_gap.py"
)
_OFF_HOUR = "does not land on a stored HRRR hour"
_DIFFERENCES = ("13.4", "-6.9")
_SKIPS = (
    "2026-10-02T19:00:00-04:00",
    "2026-10-04T06:00:00-04:00",
    "2026-10-04T18:00:00-04:00",
    "2026-10-05T06:00:00-04:00",
    "2026-10-05T18:00:00-04:00",
    "2026-10-06T06:00:00-04:00",
    "2026-10-06T18:00:00-04:00",
    "2026-10-07T06:00:00-04:00",
    "2026-10-07T18:00:00-04:00",
    "2026-10-08T06:00:00-04:00",
    "2026-10-08T18:00:00-04:00",
    "2026-10-09T06:00:00-04:00",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "The hourly body is not used." in text


def test_nws_forecast_periods_minus_hrrr_are_not_a_threshold() -> None:
    found = load_nws_forecast_hrrr_gap(PUBLIC)
    assert len(found.hours) == 2
    assert len(found.skipped) == 12
    assert found.hours[0].start == "2026-10-03T06:00:00-04:00"
    assert found.hours[0].time == "2026-10-03T10:00"
    assert found.hours[-1].start == "2026-10-03T18:00:00-04:00"
    assert found.hours[-1].time == "2026-10-03T22:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert tuple(item.start for item in found.skipped) == _SKIPS
    assert {item.reason for item in found.skipped} == {_OFF_HOUR}
    assert found.hrrr_latitude == Decimal("39.863625")
    assert found.hrrr_longitude == Decimal("-75.22328")
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_hrrr_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The hourly body was not used." in note
    assert "The NWS polygon was not snapped to the HRRR grid." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
