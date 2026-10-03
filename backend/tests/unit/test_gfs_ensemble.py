"""The stored GFS ensemble. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.gfs_ensemble import gfs_ensemble_note, load_gfs_ensemble
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "gfs_ensemble.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_gfs_ensemble_is_stored_and_not_traded() -> None:
    found = load_gfs_ensemble(PUBLIC)
    assert found.http_status == 200
    assert found.hours == 24
    assert found.series == 31
    assert found.nulls == 0
    assert found.first_time == "2026-10-03T00:00"
    assert found.last_time == "2026-10-03T23:00"
    assert found.first_control == Decimal("73.2")
    assert found.last_control == Decimal("64.6")
    assert found.unit == "°F"
    assert found.requested_latitude == "39.87"
    assert found.requested_longitude == "-75.23"
    assert found.response_latitude == Decimal("39.75")
    assert found.response_longitude == Decimal("-75.25")
    assert found.timezone == "GMT"
    assert found.traded is False
    assert found.promoted is False
    note = gfs_ensemble_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| GFS ensemble | no stored value |" in text
    assert "It was not aligned to the CLI decision clock." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
