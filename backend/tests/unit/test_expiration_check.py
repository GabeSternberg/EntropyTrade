"""The expiration value is not a fill, and a missing value stays missing."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.expiration_check import load_expiration_check
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "expiration_check.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_check_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "expiration_check" not in _SCORE.read_text(encoding="utf-8")


def test_evaluable_expiration_values_match_the_stored_result() -> None:
    scored = load_expiration_check(ROOT)
    assert scored.markets == 3720
    assert scored.evaluable == 2887
    assert scored.unevaluable == 833
    assert scored.missing_expiration == 808
    assert scored.missing_strike == 25
    assert scored.agreements == 2887
    assert scored.mismatches == 0
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
