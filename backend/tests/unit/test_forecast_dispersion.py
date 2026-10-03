"""GFS ensemble ranges. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.forecast_dispersion import (
    forecast_dispersion_note,
    load_forecast_dispersion,
)
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
    / "forecast_dispersion.py"
)
_RANGES = (
    ("2026-10-03T00:00", "1.0"),
    ("2026-10-03T01:00", "1.8"),
    ("2026-10-03T02:00", "3.3"),
    ("2026-10-03T03:00", "4.0"),
    ("2026-10-03T04:00", "3.3"),
    ("2026-10-03T05:00", "3.9"),
    ("2026-10-03T06:00", "5.3"),
    ("2026-10-03T07:00", "5.1"),
    ("2026-10-03T08:00", "4.4"),
    ("2026-10-03T09:00", "4.2"),
    ("2026-10-03T10:00", "4.5"),
    ("2026-10-03T11:00", "5.0"),
    ("2026-10-03T12:00", "4.6"),
    ("2026-10-03T13:00", "3.0"),
    ("2026-10-03T14:00", "3.0"),
    ("2026-10-03T15:00", "4.5"),
    ("2026-10-03T16:00", "5.1"),
    ("2026-10-03T17:00", "6.4"),
    ("2026-10-03T18:00", "7.9"),
    ("2026-10-03T19:00", "8.1"),
    ("2026-10-03T20:00", "8.3"),
    ("2026-10-03T21:00", "7.9"),
    ("2026-10-03T22:00", "5.9"),
    ("2026-10-03T23:00", "4.3"),
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_forecast_dispersion_is_the_range() -> None:
    found = load_forecast_dispersion(PUBLIC)
    assert len(found.ranges) == 24
    assert found.traded is False
    assert found.promoted is False
    paired = [
        (hour, format(item, "f")) for hour, item in zip(found.hours, found.ranges, strict=True)
    ]
    assert paired == list(_RANGES)
    note = forecast_dispersion_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast dispersion | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
