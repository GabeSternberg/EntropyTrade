"""ECMWF minus HRRR on the stored previous day. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.previous_model_gap import (
    load_previous_model_gap,
    previous_model_gap_note,
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
    / "previous_model_gap.py"
)
_DIFFERENCES = (
    "1.8",
    "1.7",
    "2.8",
    "3.1",
    "2.8",
    "2.6",
    "2.5",
    "3.2",
    "3.5",
    "3.5",
    "3.3",
    "3.2",
    "3.0",
    "1.6",
    "1.0",
    "1.5",
    "0.9",
    "0.5",
    "-0.7",
    "-0.8",
    "-1.3",
    "-2.1",
    "-1.4",
    "-1.9",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_previous_day_model_gap_is_not_a_threshold() -> None:
    found = load_previous_model_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-02T00:00"
    assert found.hours[-1].time == "2026-10-02T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.ecmwf_latitude == Decimal("39.89455")
    assert found.ecmwf_longitude == Decimal("-75.18826")
    assert found.hrrr_latitude == Decimal("39.863625")
    assert found.hrrr_longitude == Decimal("-75.22328")
    assert found.ecmwf_latitude != found.hrrr_latitude
    assert found.traded is False
    assert found.promoted is False
    note = previous_model_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast changes/revisions | no stored value |" in text
    assert "The grid points were not snapped together." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
