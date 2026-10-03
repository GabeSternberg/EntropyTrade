"""Ensemble mean minus ECMWF. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.mean_ecmwf_gap import load_mean_ecmwf_gap, mean_ecmwf_gap_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "mean_ecmwf_gap.py"
)
_DIFFERENCES = (
    "0.67741935483870967741935484",
    "-0.63225806451612903225806452",
    "0.44838709677419354838709677",
    "0.96129032258064516129032258",
    "0.25483870967741935483870968",
    "-0.44193548387096774193548387",
    "-0.74838709677419354838709677",
    "-0.62580645161290322580645161",
    "-0.63225806451612903225806452",
    "-0.60322580645161290322580645",
    "-0.93548387096774193548387097",
    "-0.02258064516129032258064516",
    "0.61612903225806451612903226",
    "1.75161290322580645161290323",
    "1.92580645161290322580645161",
    "1.07096774193548387096774194",
    "1.10322580645161290322580645",
    "0.33225806451612903225806452",
    "-0.45483870967741935483870968",
    "-0.52258064516129032258064516",
    "-0.93870967741935483870967742",
    "-1.29032258064516129032258065",
    "-1.18387096774193548387096774",
    "-0.28709677419354838709677419",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_ensemble_mean_minus_ecmwf_is_not_a_threshold() -> None:
    found = load_mean_ecmwf_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-03T00:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.ensemble_latitude == Decimal("39.75")
    assert found.ensemble_longitude == Decimal("-75.25")
    assert found.ecmwf_latitude == Decimal("39.89455")
    assert found.ecmwf_longitude == Decimal("-75.18826")
    assert found.ensemble_latitude != found.ecmwf_latitude
    assert found.traded is False
    assert found.promoted is False
    note = mean_ecmwf_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast mean | no stored value |" in text
    assert "The grid points were not snapped together." in note
    assert "The mean still uses all 31 temperature series." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
