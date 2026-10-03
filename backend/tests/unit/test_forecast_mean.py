"""Unrounded GFS ensemble means. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.forecast_mean import forecast_mean_note, load_forecast_mean
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "forecast_mean.py"
)
_MEANS = (
    ("2026-10-03T00:00", "73.27741935483870967741935484"),
    ("2026-10-03T01:00", "71.96774193548387096774193548"),
    ("2026-10-03T02:00", "71.14838709677419354838709677"),
    ("2026-10-03T03:00", "70.06129032258064516129032258"),
    ("2026-10-03T04:00", "68.15483870967741935483870968"),
    ("2026-10-03T05:00", "65.95806451612903225806451613"),
    ("2026-10-03T06:00", "64.15161290322580645161290323"),
    ("2026-10-03T07:00", "62.97419354838709677419354839"),
    ("2026-10-03T08:00", "62.16774193548387096774193548"),
    ("2026-10-03T09:00", "61.59677419354838709677419355"),
    ("2026-10-03T10:00", "61.06451612903225806451612903"),
    ("2026-10-03T11:00", "60.77741935483870967741935484"),
    ("2026-10-03T12:00", "61.21612903225806451612903226"),
    ("2026-10-03T13:00", "62.95161290322580645161290323"),
    ("2026-10-03T14:00", "65.42580645161290322580645161"),
    ("2026-10-03T15:00", "67.47096774193548387096774194"),
    ("2026-10-03T16:00", "68.70322580645161290322580645"),
    ("2026-10-03T17:00", "69.53225806451612903225806452"),
    ("2026-10-03T18:00", "69.84516129032258064516129032"),
    ("2026-10-03T19:00", "69.57741935483870967741935484"),
    ("2026-10-03T20:00", "68.86129032258064516129032258"),
    ("2026-10-03T21:00", "67.80967741935483870967741935"),
    ("2026-10-03T22:00", "66.21612903225806451612903226"),
    ("2026-10-03T23:00", "64.31290322580645161290322581"),
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_forecast_mean_is_unrounded() -> None:
    found = load_forecast_mean(PUBLIC)
    assert len(found.means) == 24
    assert found.traded is False
    assert found.promoted is False
    paired = [
        (hour, format(mean, "f")) for hour, mean in zip(found.hours, found.means, strict=True)
    ]
    assert paired == list(_MEANS)
    note = forecast_mean_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| forecast mean | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
