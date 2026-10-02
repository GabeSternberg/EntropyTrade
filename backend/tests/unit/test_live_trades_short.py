"""The live trade list for the short markets is empty, and it is not a fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.historical_trades import load_historical_tape
from entropytrade.weather.live_trades_short import load_live_trades_short
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "live_trades_short.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "live_trades_short" not in _SCORE.read_text(encoding="utf-8")


def test_live_trades_for_the_short_markets_are_empty() -> None:
    scored = load_live_trades_short(ROOT)
    assert scored.markets == 18
    assert scored.trades == 0
    assert scored.empty == 18
    assert scored.added_to_historical_table is False
    assert scored.joined_to_cli_replay is False
    assert scored.guaranteed_fill is False
    assert scored.promoted is False
    tape = load_historical_tape(ROOT)
    assert tape.trade_count == 1018012
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
