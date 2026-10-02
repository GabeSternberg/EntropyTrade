"""Fold equity comes from the frozen rules. The full-window 102.43 is not a threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_score, load_chicago_walk_forward

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
_RULES = ROOT / "backend" / "src" / "entropytrade" / "weather" / "informational_rules.py"
_CHICAGO = ROOT / "backend" / "src" / "entropytrade" / "weather" / "chicago_rules.py"


def test_folds_report_base_and_conservative_without_the_full_window_number() -> None:
    assert "102.43" not in _RULES.read_text(encoding="utf-8")
    assert "102.43" not in _CHICAGO.read_text(encoding="utf-8")
    full = {rule.name: rule for rule in load_chicago_score(PUBLIC).rules}
    assert full["forecast_gap"].scenarios[0].equity == Decimal("102.430000")
    walked = load_chicago_walk_forward(PUBLIC)
    assert walked.holdout_scored is False
    assert walked.promoted is False
    train = {rule.name: rule for rule in walked.train}
    validation = {rule.name: rule for rule in walked.validation}
    assert train["forecast_gap"].scenarios[0].equity != full["forecast_gap"].scenarios[0].equity
    for fold in (train, validation):
        for rule in fold.values():
            assert rule.promoted is False
            optimistic, base, conservative = rule.scenarios
            assert optimistic.name == "optimistic"
            assert optimistic.guaranteed_fill is False
            assert base.name == "base"
            assert base.assumed_fills == 0
            assert base.equity == Decimal("100.000000")
            assert conservative.name == "conservative"
            assert conservative.assumed_fills == 0
            assert conservative.equity == Decimal("100.000000")
    assert train["forecast_inside"].fires == 2
    assert train["forecast_inside"].claim_hits == 1
    assert train["forecast_inside"].scenarios[0].equity == Decimal("100.750000")
    assert train["forecast_above"].fires == 14
    assert train["forecast_above"].claim_hits == 10
    assert train["forecast_above"].scenarios[0].equity == Decimal("99.400000")
    assert train["forecast_below"].fires == 4
    assert train["forecast_below"].claim_hits == 3
    assert train["forecast_below"].scenarios[0].equity == Decimal("99.660000")
    assert train["forecast_gap"].fires == 16
    assert train["forecast_gap"].claim_hits == 5
    assert train["forecast_gap"].scenarios[0].equity == Decimal("102.510000")
    assert validation["forecast_inside"].fires == 0
    assert validation["forecast_inside"].claim_hits == 0
    assert validation["forecast_inside"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_above"].fires == 3
    assert validation["forecast_above"].claim_hits == 2
    assert validation["forecast_above"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_below"].fires == 7
    assert validation["forecast_below"].claim_hits == 6
    assert validation["forecast_below"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_gap"].fires == 3
    assert validation["forecast_gap"].claim_hits == 0
    assert validation["forecast_gap"].scenarios[0].equity == Decimal("99.920000")
