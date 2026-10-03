"""NWS hourly minus the unrounded ensemble mean. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_mean_gap import load_nws_mean_gap, nws_mean_gap_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_mean_gap.py"
)
_OFF_HOUR = "does not land on a stored mean hour"
_DIFFERENCES = (
    "2.02580645161290322580645161",
    "0.83225806451612903225806452",
    "1.40322580645161290322580645",
    "-0.06451612903225806451612903",
    "0.22258064516129032258064516",
    "-0.21612903225806451612903226",
    "-0.95161290322580645161290323",
    "-1.42580645161290322580645161",
    "-1.47096774193548387096774194",
    "-0.70322580645161290322580645",
    "0.46774193548387096774193548",
    "2.15483870967741935483870968",
    "2.42258064516129032258064516",
    "4.13870967741935483870967742",
    "3.19032258064516129032258065",
    "4.78387096774193548387096774",
    "3.68709677419354838709677419",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "load_forecast_mean" in text
    assert "total / Decimal" not in text


def test_nws_hourly_minus_mean_is_not_a_threshold() -> None:
    found = load_nws_mean_gap(PUBLIC)
    assert len(found.hours) == 17
    assert len(found.skipped) == 139
    assert found.hours[0].start == "2026-10-03T03:00:00-04:00"
    assert found.hours[0].time == "2026-10-03T07:00"
    assert found.hours[-1].start == "2026-10-03T19:00:00-04:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.skipped[0].start == "2026-10-03T20:00:00-04:00"
    assert found.skipped[-1].start == "2026-10-09T14:00:00-04:00"
    assert {item.reason for item in found.skipped} == {_OFF_HOUR}
    assert found.latitude == Decimal("39.75")
    assert found.longitude == Decimal("-75.25")
    assert found.traded is False
    assert found.promoted is False
    note = nws_mean_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "The mean still uses all 31 temperature series." in note
    assert "The NWS polygon was not snapped to the ensemble grid." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
