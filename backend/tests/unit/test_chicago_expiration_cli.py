"""Chicago expiration values equal the CLI highs. CLI is not settlement."""

from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_expiration_cli

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_expiration_matches_the_cli_high_in_degrees() -> None:
    check = load_chicago_expiration_cli(ROOT)
    assert check.listed == 11
    assert check.omitted == 29
    assert check.equal == 11
    assert check.differ == 0
    assert check.cli_is_settlement_source is False
    assert check.promoted is False
