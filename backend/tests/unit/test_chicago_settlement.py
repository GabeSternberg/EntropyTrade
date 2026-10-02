"""Listed Chicago settlement dollars and expiration values match the result."""

from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_settlement_check

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_the_compact_table_matches_result_and_strike() -> None:
    check = load_chicago_settlement_check(ROOT)
    assert check.listed == 11
    assert check.omitted == 29
    assert check.settlement_agreements == 11
    assert check.settlement_mismatches == 0
    assert check.settlement_unevaluable == 0
    assert check.expiration_agreements == 11
    assert check.expiration_mismatches == 0
    assert check.expiration_unevaluable == 0
    assert check.promoted is False
