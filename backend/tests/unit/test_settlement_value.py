"""Settlement dollars are the stored payout, not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.settlement_score import load_aligned_score
from entropytrade.weather.settlement_value import load_settlement_value_check

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_value.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_check_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "settlement_value" not in _SCORE.read_text(encoding="utf-8")


def test_settlement_dollars_match_every_stored_result() -> None:
    scored = load_settlement_value_check(ROOT)
    assert scored.markets == 3720
    assert scored.agreements == 3720
    assert scored.mismatches == 0
    assert scored.unevaluable == 0
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
