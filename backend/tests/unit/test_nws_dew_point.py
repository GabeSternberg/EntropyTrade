"""Distinct NWS dew points. No socket and no unit conversion."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_dew_point import load_nws_dew_point, nws_dew_point_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_dew_point.py"
)
_VALUES = (
    "3.888888888888889",
    "4.444444444444445",
    "5",
    "5.555555555555555",
    "6.111111111111111",
    "6.666666666666667",
    "7.222222222222222",
    "7.777777777777778",
    "8.333333333333334",
    "8.88888888888889",
    "9.444444444444445",
    "10",
    "10.555555555555555",
    "11.11111111111111",
    "11.666666666666666",
    "12.222222222222221",
    "12.777777777777779",
    "13.333333333333334",
    "13.88888888888889",
    "14.444444444444445",
    "15",
    "15.555555555555555",
    "16.11111111111111",
    "16.666666666666668",
    "17.22222222222222",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "1.8" not in text
    assert "+ 32" not in text


def test_dew_points_are_not_converted() -> None:
    found = load_nws_dew_point(PUBLIC)
    assert found.periods == 156
    assert found.skipped == ()
    assert [format(item, "f") for item in found.values] == list(_VALUES)
    assert found.traded is False
    assert found.promoted is False
    note = nws_dew_point_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| dew point | no stored value |" in text
    assert "The smallest is 3.888888888888889 and the largest is 17.22222222222222." in note
    assert "The unit was not converted." in note
    assert "The count was not compared to 0.40." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
