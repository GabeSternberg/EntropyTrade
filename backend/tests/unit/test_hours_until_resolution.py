"""Hours from the decision clock to stored CLI labels. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.hours_until_resolution import (
    hours_until_resolution_note,
    load_hours_until_resolution,
)
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import DECISION_HOUR_UTC, REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "hours_until_resolution.py"
)
_HOURS = (
    ("2026-08-23", "14.91666666666666666666666667"),
    ("2026-08-24", "15.01666666666666666666666667"),
    ("2026-08-25", "15.23333333333333333333333333"),
    ("2026-08-26", "15.05"),
    ("2026-08-27", "15.1"),
    ("2026-08-28", "15.18333333333333333333333333"),
    ("2026-08-29", "15.43333333333333333333333333"),
    ("2026-08-30", "15.3"),
    ("2026-08-31", "15.36666666666666666666666667"),
    ("2026-09-01", "15.75"),
    ("2026-09-02", "15.21666666666666666666666667"),
    ("2026-09-03", "14.91666666666666666666666667"),
    ("2026-09-04", "14.93333333333333333333333333"),
    ("2026-09-05", "14.88333333333333333333333333"),
    ("2026-09-06", "14.9"),
    ("2026-09-07", "14.96666666666666666666666667"),
    ("2026-09-08", "14.85"),
    ("2026-09-09", "14.9"),
    ("2026-09-10", "14.91666666666666666666666667"),
    ("2026-09-11", "14.98333333333333333333333333"),
    ("2026-09-12", "15"),
    ("2026-09-13", "14.76666666666666666666666667"),
    ("2026-09-14", "14.9"),
    ("2026-09-15", "14.88333333333333333333333333"),
    ("2026-09-16", "15.03333333333333333333333333"),
    ("2026-09-17", "15.1"),
    ("2026-09-18", "15"),
    ("2026-09-19", "15.33333333333333333333333333"),
    ("2026-09-20", "14.95"),
    ("2026-09-21", "15.41666666666666666666666667"),
    ("2026-09-22", "16"),
    ("2026-09-23", "15.5"),
    ("2026-09-24", "15.36666666666666666666666667"),
    ("2026-09-25", "14.91666666666666666666666667"),
    ("2026-09-26", "14.93333333333333333333333333"),
    ("2026-09-27", "15.01666666666666666666666667"),
    ("2026-09-28", "15.05"),
    ("2026-09-29", "14.98333333333333333333333333"),
    ("2026-09-30", "14.86666666666666666666666667"),
    ("2026-10-01", "15.36666666666666666666666667"),
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_hours_until_resolution_keep_negative_spans() -> None:
    found = load_hours_until_resolution(PUBLIC)
    assert len(found.rows) == 40
    assert found.negative == 0
    assert found.traded is False
    assert found.promoted is False
    paired = [(item.valid_on, format(item.hours, "f")) for item in found.rows]
    assert paired == list(_HOURS)
    note = hours_until_resolution_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| hours until resolution | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert DECISION_HOUR_UTC == 15
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
