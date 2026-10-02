"""Later KXHIGH tickers use the registered thresholds. A print is not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_walk_forward
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
)
from entropytrade.weather.kxhigh_scan import load_kxhigh_scan, render_kxhigh_scan
from entropytrade.weather.newyork_rules import load_newyork_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "kxhigh_scan.py"
)
_NOTE = Path(__file__).resolve().parents[3] / "docs" / "research" / "kxhigh-scan.md"


def test_scan_thresholds_stay_frozen() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("80.5") == MIDPOINT
    assert Decimal("0.4000") == PRICE_THRESHOLD
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "102.43" not in text


def test_scan_note_matches_the_stored_rows() -> None:
    cities = load_kxhigh_scan(ROOT)
    assert cities
    assert _NOTE.read_text(encoding="utf-8") == render_kxhigh_scan(ROOT)
    assert "Optimistic trade-print equity is not a fill." in _NOTE.read_text(encoding="utf-8")
    assert "Nothing is promoted." in _NOTE.read_text(encoding="utf-8")
    for city in cities:
        assert city.promoted is False
        assert city.holdout_scored is False
        if not city.scored:
            assert city.hypotheses == 0
            assert city.walked is False
            continue
        assert city.hypotheses == 4
        assert city.walked is True
        for rule in city.rules + city.validation:
            assert rule.scenarios[0].guaranteed_fill is False
            assert rule.scenarios[1].equity == Decimal("100.000000")
            assert rule.scenarios[2].equity == Decimal("100.000000")
    chicago = load_chicago_walk_forward(ROOT)
    validation = {rule.name: rule for rule in chicago.validation}
    assert validation["forecast_gap"].scenarios[0].equity == Decimal("99.920000")
    newyork = {rule.name: rule for rule in load_newyork_score(ROOT).rules}
    assert newyork["forecast_gap"].scenarios[0].equity == Decimal("100.450000")
