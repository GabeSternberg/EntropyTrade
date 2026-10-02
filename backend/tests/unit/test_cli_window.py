"""CLI-window public tape. Empty books stay empty. Candles are not books."""

from datetime import date
from pathlib import Path

from entropytrade.exchange.cli_window import load_cli_window
from entropytrade.exchange.public_tape import load_books

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_the_cli_window_has_no_sized_book() -> None:
    tape = load_cli_window(ROOT)
    assert tape.fetched_at.isoformat() == "2026-10-02T16:13:37.600569+00:00"
    assert tape.host == "https://api.elections.kalshi.com/trade-api/v2"
    assert tape.window_start == date(2026, 8, 23)
    assert tape.window_end == date(2026, 10, 1)
    assert tape.orderbook_empty == 240
    assert tape.orderbook_nonempty == 0
    assert tape.sized_books == 0
    assert tape.candles_stored == 230
    assert tape.failed_calls == 0
    assert tape.touch_size_fields == 0
    assert tape.includes_b805 is True
    assert tape.strike_count > 1
    assert tape.strikes_besides_b805 == tape.strike_count - 1


def test_live_books_are_unchanged_and_the_loader_does_not_fetch() -> None:
    assert len(load_books(ROOT)) == 12
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/exchange/cli_window.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "import socket"):
        assert name not in text
    sample = (ROOT / "kalshi-public" / "cli-window" / "orderbook-empty-sample.json").read_text(
        encoding="utf-8"
    )
    assert '"yes_dollars":[]' in sample.replace(" ", "")
