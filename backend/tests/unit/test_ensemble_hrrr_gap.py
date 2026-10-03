"""Ensemble control minus HRRR. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.ensemble_hrrr_gap import ensemble_hrrr_gap_note, load_ensemble_hrrr_gap
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "ensemble_hrrr_gap.py"
)
_DIFFERENCES = (
    "0.0",
    "-1.4",
    "-0.5",
    "0.2",
    "-0.7",
    "-1.2",
    "0.6",
    "1.8",
    "1.6",
    "1.2",
    "1.6",
    "1.5",
    "1.9",
    "2.8",
    "4.0",
    "4.5",
    "4.1",
    "3.4",
    "2.9",
    "2.1",
    "1.9",
    "1.3",
    "1.9",
    "1.2",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_ensemble_control_minus_hrrr_is_not_a_threshold() -> None:
    found = load_ensemble_hrrr_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-03T00:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.ensemble_latitude == Decimal("39.75")
    assert found.ensemble_longitude == Decimal("-75.25")
    assert found.hrrr_latitude == Decimal("39.863625")
    assert found.hrrr_longitude == Decimal("-75.22328")
    assert found.ensemble_latitude != found.hrrr_latitude
    assert found.traded is False
    assert found.promoted is False
    note = ensemble_hrrr_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast changes/revisions | no stored value |" in text
    assert "The grid points were not snapped together." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
