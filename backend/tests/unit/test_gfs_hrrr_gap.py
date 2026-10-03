"""GFS minus HRRR on the stored previous day. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.gfs_hrrr_gap import gfs_hrrr_gap_note, load_gfs_hrrr_gap
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "gfs_hrrr_gap.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_gfs_minus_hrrr_previous_day_is_not_a_threshold() -> None:
    found = load_gfs_hrrr_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-02T00:00"
    assert found.hours[-1].time == "2026-10-02T23:00"
    assert all(hour.difference == 0 for hour in found.hours)
    assert found.gfs_latitude == found.hrrr_latitude == Decimal("39.863625")
    assert found.gfs_longitude == found.hrrr_longitude == Decimal("-75.22328")
    assert found.traded is False
    assert found.promoted is False
    note = gfs_hrrr_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast changes/revisions | no stored value |" in text
    assert "The stored response grids are equal and were not rewritten." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
