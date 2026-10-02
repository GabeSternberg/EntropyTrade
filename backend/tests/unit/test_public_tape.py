"""Stored public order books. Empty books are skipped. Sizes are not invented."""

import json
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.public_tape import book_from_body, load_books

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_sized_books_keep_the_response_size() -> None:
    books = load_books(ROOT)
    assert len(books) == 12
    sample = next(item for item in books if item.market_ticker == "KXHIGHPHIL-26OCT03-B74.5")
    assert sample.source == "kalshi-public"
    assert sample.endpoint.startswith("https://api.elections.kalshi.com/trade-api/v2/markets/")
    assert sample.available_at.isoformat() == "2026-10-02T15:48:09.632726+00:00"
    quantities = [level.quantity for level in (*sample.book.bids, *sample.book.asks)]
    assert Decimal("47.00") in quantities or Decimal("6.00") in quantities
    assert all(qty > 0 for qty in quantities)
    assert sample.book.bids or sample.book.asks


def test_an_empty_book_is_not_a_level() -> None:
    body = (ROOT / "kalshi-public" / "orderbook-empty-sample.json").read_text(encoding="utf-8")
    assert (
        book_from_body(
            json.loads(body),
            market_ticker="KXHIGHPHIL-26OCT01-T85",
            available_at=load_books(ROOT)[0].available_at,
            endpoint="https://api.elections.kalshi.com/trade-api/v2/markets/KXHIGHPHIL-26OCT01-T85/orderbook",
        )
        is None
    )


def test_candles_are_not_turned_into_books() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/exchange/public_tape.py")
        .read_text(encoding="utf-8")
    )
    assert "candlesticks" not in text
    assert "import urllib" not in text
    assert "import httpx" not in text
