"""Chicago walk-forward scores train and validation. The holdout is not scored."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_walk_forward
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
)
from entropytrade.weather.walk_forward import load_rule_walk_forward

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_chicago_holdout_is_not_scored() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("80.5") == MIDPOINT
    assert Decimal("0.4000") == PRICE_THRESHOLD
    walked = load_chicago_walk_forward(ROOT)
    assert walked.train_days == 20
    assert walked.validation_days == 10
    assert walked.holdout_days == 10
    assert walked.holdout_scored is False
    assert walked.promoted is False
    train = {rule.name: rule for rule in walked.train}
    validation = {rule.name: rule for rule in walked.validation}
    assert train["forecast_inside"].fires == 2
    assert train["forecast_inside"].claim_hits == 1
    assert train["forecast_inside"].scenarios[0].assumed_fills == 1
    assert train["forecast_inside"].scenarios[0].equity == Decimal("100.750000")
    assert train["forecast_above"].fires == 14
    assert train["forecast_above"].claim_hits == 10
    assert train["forecast_above"].scenarios[0].assumed_fills == 2
    assert train["forecast_above"].scenarios[0].equity == Decimal("99.400000")
    assert train["forecast_below"].fires == 4
    assert train["forecast_below"].claim_hits == 3
    assert train["forecast_below"].scenarios[0].assumed_fills == 1
    assert train["forecast_below"].scenarios[0].equity == Decimal("99.660000")
    assert train["forecast_gap"].fires == 16
    assert train["forecast_gap"].claim_hits == 5
    assert train["forecast_gap"].scenarios[0].assumed_fills == 6
    assert train["forecast_gap"].scenarios[0].equity == Decimal("102.510000")
    assert validation["forecast_inside"].fires == 0
    assert validation["forecast_inside"].scenarios[0].assumed_fills == 0
    assert validation["forecast_inside"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_above"].fires == 3
    assert validation["forecast_above"].claim_hits == 2
    assert validation["forecast_above"].scenarios[0].assumed_fills == 0
    assert validation["forecast_above"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_below"].fires == 7
    assert validation["forecast_below"].claim_hits == 6
    assert validation["forecast_below"].scenarios[0].assumed_fills == 0
    assert validation["forecast_below"].scenarios[0].equity == Decimal("100.000000")
    assert validation["forecast_gap"].fires == 3
    assert validation["forecast_gap"].claim_hits == 0
    assert validation["forecast_gap"].scenarios[0].assumed_fills == 1
    assert validation["forecast_gap"].scenarios[0].equity == Decimal("99.920000")
    for rule in walked.train + walked.validation:
        assert rule.promoted is False
        assert rule.scenarios[0].guaranteed_fill is False
        assert rule.scenarios[1].assumed_fills == 0
        assert rule.scenarios[1].equity == Decimal("100.000000")
        assert rule.scenarios[2].assumed_fills == 0
        assert rule.scenarios[2].equity == Decimal("100.000000")
    philadelphia = load_rule_walk_forward(ROOT)
    assert philadelphia.holdout_scored is False
    assert philadelphia.promoted is False
