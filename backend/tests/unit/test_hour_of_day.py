"""Hour of day from stored timestamps. No socket and no trade."""

from collections import Counter
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.hour_of_day import hour_of_day_note, load_hour_of_day
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "hour_of_day.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_hour_of_day_is_the_timestamp_hour() -> None:
    found = load_hour_of_day(PUBLIC)
    assert found.count == 960
    assert len(found.hours) == 960
    assert found.first_hour == 0
    assert found.last_hour == 23
    assert found.traded is False
    assert found.promoted is False
    assert Counter(found.hours) == dict.fromkeys(range(24), 40)
    note = hour_of_day_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| hour of day | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
