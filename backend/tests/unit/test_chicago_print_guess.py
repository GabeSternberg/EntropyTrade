"""Chicago's pre-decision print uses the same 0.50 line. It is not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_print_guess
from entropytrade.weather.cli_print_guess import DECISION_HOUR, load_cli_print_guess
from entropytrade.weather.last_print import GUESS_YES_AT

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_chicago_pre_decision_print_is_not_a_fill() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    assert DECISION_HOUR == 15
    scored = load_chicago_print_guess(ROOT)
    assert scored.days == 40
    assert scored.with_prints == 11
    assert scored.without_prints == 29
    assert scored.guesses_yes == 5
    assert scored.agreements == 10
    assert scored.fidelity == "trade-print"
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    philadelphia = load_cli_print_guess(ROOT)
    assert philadelphia.with_prints == 10
    assert philadelphia.guesses_yes == 0
    assert philadelphia.agreements == 9
    assert philadelphia.promoted is False
