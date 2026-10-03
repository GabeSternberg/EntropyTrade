"""The mean of the stored previous-day errors. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F
from entropytrade.weather.station_bias import load_station_bias, station_bias_note

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "station_bias.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_station_bias_is_the_unrounded_mean() -> None:
    found = load_station_bias(PUBLIC)
    assert found.days == 39
    assert found.total == Decimal("24.7")
    assert found.mean == Decimal("24.7") / Decimal(39)
    assert format(found.mean, "f") == "0.6333333333333333333333333333"
    assert found.traded is False
    assert found.promoted is False
    note = station_bias_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| historical station/model bias | no stored value |" in text
    assert "It is not subtracted from a forecast." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
