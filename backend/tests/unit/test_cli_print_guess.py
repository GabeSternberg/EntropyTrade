"""The 15:00 print on the 2026 tape is a guess, not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.cli_print_guess import DECISION_HOUR, load_cli_print_guess
from entropytrade.weather.last_print import GUESS_YES_AT
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "cli_print_guess.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_line_and_the_clock_stay_put() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    assert DECISION_HOUR == 15
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "historical_trades" not in text
    assert "cli_print_guess" not in _SCORE.read_text(encoding="utf-8")


def test_the_pre_decision_print_is_not_a_fill() -> None:
    scored = load_cli_print_guess(ROOT)
    assert scored.days == 40
    assert scored.with_prints == 10
    assert scored.without_prints == 30
    assert scored.guesses_yes == 0
    assert scored.agreements == 9
    assert scored.fidelity == "trade-print"
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
