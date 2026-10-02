"""Print sizes are not fills, and they are not a substitute for volume."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.settlement_score import load_aligned_score
from entropytrade.weather.volume_check import load_volume_check

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "volume_check.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_check_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "volume_check" not in _SCORE.read_text(encoding="utf-8")


def test_print_sizes_match_volume_except_eighteen_short_markets() -> None:
    scored = load_volume_check(ROOT)
    assert scored.markets == 3720
    assert scored.missing_volume == 0
    assert scored.equal == 3702
    assert scored.short == 18
    assert scored.long == 0
    assert scored.zero_prints == 54
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
