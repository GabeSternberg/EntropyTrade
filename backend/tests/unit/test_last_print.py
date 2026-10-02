"""The last historical print is a guess, not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.last_print import GUESS_YES_AT, load_last_print_score
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "last_print.py"
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_yes_line_stays_at_one_half() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "last_print" not in _SCORE.read_text(encoding="utf-8")


def test_last_print_agrees_often_and_is_not_a_fill() -> None:
    scored = load_last_print_score(ROOT)
    assert scored.markets == 3720
    assert scored.with_prints == 3666
    assert scored.without_prints == 54
    assert scored.guesses_yes == 621
    assert scored.agreements == 3661
    assert scored.fidelity == "trade-print"
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
