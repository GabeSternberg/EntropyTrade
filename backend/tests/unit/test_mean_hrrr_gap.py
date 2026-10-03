"""Ensemble mean minus HRRR. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.mean_hrrr_gap import load_mean_hrrr_gap, mean_hrrr_gap_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "mean_hrrr_gap.py"
)
_DIFFERENCES = (
    "0.07741935483870967741935484",
    "-1.43225806451612903225806452",
    "-0.65161290322580645161290323",
    "-0.03870967741935483870967742",
    "-1.14516129032258064516129032",
    "-1.94193548387096774193548387",
    "-0.24838709677419354838709677",
    "0.97419354838709677419354839",
    "0.96774193548387096774193548",
    "0.69677419354838709677419355",
    "1.46451612903225806451612903",
    "1.67741935483870967741935484",
    "2.01612903225806451612903226",
    "2.45161290322580645161290323",
    "2.82580645161290322580645161",
    "2.67096774193548387096774194",
    "2.00322580645161290322580645",
    "1.13225806451612903225806452",
    "0.74516129032258064516129032",
    "0.17741935483870967741935484",
    "0.46129032258064516129032258",
    "0.30967741935483870967741935",
    "1.31612903225806451612903226",
    "0.91290322580645161290322581",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_ensemble_mean_minus_hrrr_is_not_a_threshold() -> None:
    found = load_mean_hrrr_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-03T00:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.ensemble_latitude == Decimal("39.75")
    assert found.ensemble_longitude == Decimal("-75.25")
    assert found.hrrr_latitude == Decimal("39.863625")
    assert found.hrrr_longitude == Decimal("-75.22328")
    assert found.ensemble_latitude != found.hrrr_latitude
    assert found.traded is False
    assert found.promoted is False
    note = mean_hrrr_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast mean | no stored value |" in text
    assert "The grid points were not snapped together." in note
    assert "The mean still uses all 31 temperature series." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
