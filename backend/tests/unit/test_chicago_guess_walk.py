"""Chicago print-guess walk-forward leaves the holdout unscored."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_guess_walk_forward
from entropytrade.weather.cli_print_guess import DECISION_HOUR
from entropytrade.weather.last_print import GUESS_YES_AT
from entropytrade.weather.walk_forward import load_guess_walk_forward

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_chicago_guess_holdout_is_not_scored() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    assert DECISION_HOUR == 15
    walked = load_chicago_guess_walk_forward(ROOT)
    assert walked.train_days == 20
    assert walked.validation_days == 10
    assert walked.holdout_days == 10
    assert walked.holdout_scored is False
    assert walked.promoted is False
    assert walked.train.days == 20
    assert walked.train.with_prints == 8
    assert walked.train.without_prints == 12
    assert walked.train.guesses_yes == 5
    assert walked.train.agreements == 8
    assert walked.validation.days == 10
    assert walked.validation.with_prints == 2
    assert walked.validation.without_prints == 8
    assert walked.validation.guesses_yes == 0
    assert walked.validation.agreements == 2
    assert walked.train.guaranteed_fill is False
    assert walked.validation.guaranteed_fill is False
    assert walked.train.promoted is False
    assert walked.validation.promoted is False
    philadelphia = load_guess_walk_forward(ROOT)
    assert philadelphia.holdout_scored is False
    assert philadelphia.promoted is False
    assert philadelphia.train.with_prints == 5
    assert philadelphia.train.agreements == 4
    assert philadelphia.train.guesses_yes == 0
    assert philadelphia.validation.with_prints == 3
    assert philadelphia.validation.agreements == 3
    assert philadelphia.validation.guesses_yes == 0
