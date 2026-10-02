"""Listed Chicago results match the CLI bracket. Missing markets stay missing."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_result_check
from entropytrade.weather.informational_rules import BRACKET_CAP, BRACKET_FLOOR

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_listed_results_match_the_bracket() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    check = load_chicago_result_check(ROOT)
    assert check.markets == 40
    assert check.found == 11
    assert check.missing == 29
    assert check.yes_results == 6
    assert check.no_results == 5
    assert check.agreements == 11
    assert check.disagreements == 0
    assert check.promoted is False
