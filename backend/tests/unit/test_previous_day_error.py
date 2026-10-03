"""Previous-day temperature errors from stored series. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.previous_day_error import (
    load_previous_day_errors,
    previous_day_error_note,
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
    / "previous_day_error.py"
)
_ERRORS = (
    ("2026-08-24", "-2.1"),
    ("2026-08-25", "0.0"),
    ("2026-08-26", "-0.8"),
    ("2026-08-27", "-2.9"),
    ("2026-08-28", "-0.1"),
    ("2026-08-29", "3.0"),
    ("2026-08-30", "-0.6"),
    ("2026-08-31", "0.6"),
    ("2026-09-01", "-1.8"),
    ("2026-09-02", "-2.8"),
    ("2026-09-03", "2.8"),
    ("2026-09-04", "1.1"),
    ("2026-09-05", "2.7"),
    ("2026-09-06", "0.7"),
    ("2026-09-07", "1.3"),
    ("2026-09-08", "0.3"),
    ("2026-09-09", "0.8"),
    ("2026-09-10", "0.4"),
    ("2026-09-11", "0.1"),
    ("2026-09-12", "0.5"),
    ("2026-09-13", "-0.6"),
    ("2026-09-14", "1.2"),
    ("2026-09-15", "2.1"),
    ("2026-09-16", "-0.3"),
    ("2026-09-17", "0.6"),
    ("2026-09-18", "4.2"),
    ("2026-09-19", "0.8"),
    ("2026-09-20", "0.0"),
    ("2026-09-21", "-2.0"),
    ("2026-09-22", "-1.2"),
    ("2026-09-23", "1.6"),
    ("2026-09-24", "1.0"),
    ("2026-09-25", "-1.2"),
    ("2026-09-26", "3.0"),
    ("2026-09-27", "2.7"),
    ("2026-09-28", "3.9"),
    ("2026-09-29", "2.4"),
    ("2026-09-30", "0.9"),
    ("2026-10-01", "2.4"),
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_previous_day_errors_are_not_a_threshold() -> None:
    found = load_previous_day_errors(PUBLIC)
    assert found.traded is False
    assert found.promoted is False
    assert len(found.errors) == 39
    assert [(item.day, format(item.error, "f")) for item in found.errors] == list(_ERRORS)
    assert [(item.day, item.reason) for item in found.skipped] == [
        ("2026-08-23", "missing from the observed series"),
        ("2026-10-02", "missing from the previous-day series"),
    ]
    assert found.observed_latitude != found.previous_latitude
    assert found.observed_longitude != found.previous_longitude
    assert found.observed_latitude == Decimal("39.89455")
    assert found.previous_latitude == Decimal("39.863625")
    note = previous_day_error_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| previous day's errors | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
