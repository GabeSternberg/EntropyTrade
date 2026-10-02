"""Walk-forward on stored CLI days. The holdout is not run."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.weather.walk_forward import (
    load_rule_walk_forward,
    load_stored_walk_forward,
    reject_holdout,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_stored_days_walk_forward_skips_the_holdout() -> None:
    result = load_stored_walk_forward(ROOT)
    assert result.train_days == 20
    assert result.validation_days == 10
    assert result.holdout_days == 10
    assert result.ran_splits == ("train", "validation")
    assert result.holdout_blocked is True
    assert result.replay_fills == 0
    assert result.replay_equity == Decimal("100.000000")
    assert result.promoted is False
    assert result.train_mae == Decimal("2.94")
    assert result.validation_mae == Decimal("2.53")


def test_registered_rules_walk_forward_skips_the_holdout() -> None:
    result = load_rule_walk_forward(ROOT)
    assert result.train_days == 20
    assert result.validation_days == 10
    assert result.holdout_days == 10
    assert result.ran_splits == ("train", "validation")
    assert result.holdout_blocked is True
    assert result.holdout_scored is False
    assert result.promoted is False
    train = {item.name: item for item in result.train}
    validation = {item.name: item for item in result.validation}
    assert train["forecast_inside"].fires == 0
    assert train["forecast_above"].fires == 15
    assert train["forecast_above"].scenarios[0].assumed_fills == 0
    assert train["forecast_below"].fires == 5
    assert train["forecast_gap"].fires == 15
    assert train["forecast_gap"].scenarios[0].assumed_fills == 2
    assert train["forecast_gap"].scenarios[0].equity == Decimal("99.910000")
    assert validation["forecast_above"].fires == 4
    assert validation["forecast_above"].claim_hits == 4
    assert validation["forecast_below"].fires == 6
    assert validation["forecast_gap"].fires == 4
    assert validation["forecast_gap"].scenarios[0].assumed_fills == 1
    assert validation["forecast_gap"].scenarios[0].equity == Decimal("99.990000")
    assert validation["forecast_gap"].scenarios[0].guaranteed_fill is False
    for rule in (*result.train, *result.validation):
        assert rule.promoted is False
        assert rule.scenarios[1].equity == Decimal("100.000000")
        assert rule.scenarios[2].assumed_fills == 0
    with pytest.raises(ValueError, match="holdout"):
        reject_holdout({date(2026, 8, 23)}, {date(2026, 8, 23)})


def test_walk_forward_does_not_call_a_provider() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/walk_forward.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "pydantic_ai", "openai", "anthropic"):
        assert name not in text
