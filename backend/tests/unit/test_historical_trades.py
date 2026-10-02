"""Historical trade prints stay out of the 2026 CLI replay."""

from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.historical_trades import load_historical_print, load_historical_tape
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "exchange"
    / "historical_trades.py"
)
_SCORE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "settlement_score.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    ignore = Path(__file__).resolve().parents[3] / ".gitignore"
    assert "data/raw/**" in ignore.read_text(encoding="utf-8")


def test_historical_prints_are_not_fills_and_stay_out_of_the_replay() -> None:
    tape = load_historical_tape(ROOT)
    assert tape.tickers == 3720
    assert tape.tickers_ok == 3720
    assert tape.tickers_with_prints == 3666
    assert tape.failed_calls == 0
    assert tape.trade_count == 1018012
    assert tape.joined_to_cli_replay is False
    assert tape.endpoint.endswith("/historical/trades")
    item = load_historical_print(
        ROOT,
        ticker="KXHIGHPHIL-24DEC09-T53",
        created_at="2024-12-10T03:23:39.928667Z",
    )
    assert item.yes_price == Decimal("0.9900")
    assert item.count == Decimal("30.00")
    assert item.endpoint == tape.endpoint
    score_text = _SCORE.read_text(encoding="utf-8")
    assert "historical_trades" not in score_text
    scored = load_aligned_score(ROOT)
    assert scored.replay_equity == Decimal("100.000000")
    assert scored.sized_books_in_window == 0
