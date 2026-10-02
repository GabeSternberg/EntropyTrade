"""A print before close is the last print in this tape, and it is not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.before_close import load_before_close_score
from entropytrade.weather.last_print import GUESS_YES_AT, load_last_print_score
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "before_close.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_yes_line_is_still_one_half() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "before_close" not in _SCORE.read_text(encoding="utf-8")


def test_every_stored_print_is_before_close() -> None:
    scored = load_before_close_score(ROOT)
    last = load_last_print_score(ROOT)
    assert scored.markets == 3720
    assert scored.with_close == 3720
    assert scored.without_close == 0
    assert scored.with_prints == 3666
    assert scored.without_prints == 54
    assert scored.prints_at_or_after_close == 0
    assert scored.guesses_yes == 621
    assert scored.agreements == 3661
    assert scored.guesses_yes == last.guesses_yes
    assert scored.agreements == last.agreements
    assert scored.fidelity == "trade-print"
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
