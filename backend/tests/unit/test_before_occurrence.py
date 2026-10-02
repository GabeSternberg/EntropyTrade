"""A print before occurrence is still a print, not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.before_occurrence import load_before_occurrence_score
from entropytrade.weather.last_print import GUESS_YES_AT
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "before_occurrence.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_yes_line_is_still_one_half() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "before_occurrence" not in _SCORE.read_text(encoding="utf-8")


def test_pre_occurrence_prints_are_not_fills() -> None:
    scored = load_before_occurrence_score(ROOT)
    assert scored.markets == 3720
    assert scored.with_occurrence == 642
    assert scored.without_occurrence == 3078
    assert scored.with_prints == 642
    assert scored.without_prints == 0
    assert scored.guesses_yes == 75
    assert scored.agreements == 544
    assert scored.fidelity == "trade-print"
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
