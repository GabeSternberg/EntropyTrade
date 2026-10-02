"""A second pull of the short markets did not invent the missing size."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.settlement_score import load_aligned_score
from entropytrade.weather.short_refresh import load_fresh_sum, load_short_refresh

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "short_refresh.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "short_refresh" not in _SCORE.read_text(encoding="utf-8")


def test_the_second_pull_matches_the_stored_tape_and_stays_short() -> None:
    scored = load_short_refresh(ROOT)
    assert scored.markets == 18
    assert scored.unchanged == 18
    assert scored.changed == 0
    assert scored.still_short == 18
    assert scored.now_equal == 0
    assert scored.now_long == 0
    assert scored.cursor_empty == 18
    assert scored.joined_to_cli_replay is False
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    assert load_fresh_sum(ROOT, "KXHIGHPHIL-25JUN07-B77.5") == Decimal("5919.00")
    assert load_fresh_sum(ROOT, "KXHIGHPHIL-25OCT23-B60.5") == Decimal("9332.00")
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
