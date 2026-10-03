"""Ensemble mean minus ensemble control. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.mean_control_gap import load_mean_control_gap, mean_control_gap_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "mean_control_gap.py"
)
_DIFFERENCES = (
    "0.07741935483870967741935484",
    "-0.03225806451612903225806452",
    "-0.15161290322580645161290323",
    "-0.23870967741935483870967742",
    "-0.44516129032258064516129032",
    "-0.74193548387096774193548387",
    "-0.84838709677419354838709677",
    "-0.82580645161290322580645161",
    "-0.63225806451612903225806452",
    "-0.50322580645161290322580645",
    "-0.13548387096774193548387097",
    "0.17741935483870967741935484",
    "0.11612903225806451612903226",
    "-0.34838709677419354838709677",
    "-1.17419354838709677419354839",
    "-1.82903225806451612903225806",
    "-2.09677419354838709677419355",
    "-2.26774193548387096774193548",
    "-2.15483870967741935483870968",
    "-1.92258064516129032258064516",
    "-1.43870967741935483870967742",
    "-0.99032258064516129032258065",
    "-0.58387096774193548387096774",
    "-0.28709677419354838709677419",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_ensemble_mean_minus_control_is_not_a_threshold() -> None:
    found = load_mean_control_gap(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-03T00:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert [format(hour.difference, "f") for hour in found.hours] == list(_DIFFERENCES)
    assert found.latitude == Decimal("39.75")
    assert found.longitude == Decimal("-75.25")
    assert found.traded is False
    assert found.promoted is False
    note = mean_control_gap_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast mean | no stored value |" in text
    assert "The stored response grid was not rewritten." in note
    assert "The mean still uses all 31 temperature series." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
