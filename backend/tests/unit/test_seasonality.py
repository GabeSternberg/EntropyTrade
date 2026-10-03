"""Calendar month from stored timestamps. No socket and no trade."""

from collections import Counter
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F
from entropytrade.weather.seasonality import load_seasonality, seasonality_note

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "seasonality.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_seasonality_is_the_timestamp_month() -> None:
    found = load_seasonality(PUBLIC)
    assert found.count == 960
    assert len(found.months) == 960
    assert found.first_month == 8
    assert found.last_month == 10
    assert found.traded is False
    assert found.promoted is False
    assert Counter(found.months) == {8: 192, 9: 720, 10: 48}
    note = seasonality_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| seasonality | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert "named seasons" in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
