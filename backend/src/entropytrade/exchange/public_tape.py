"""Stored public Kalshi books. This module does not open a socket.

An order book is kept only when the response has at least one price-and-size
pair. The size is the second field of that pair. A candle has no size at the
touch, so candles are not turned into books. An empty ``orderbook_fp`` is
skipped.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.time import ensure_utc

_SOURCE = "kalshi-public"


@dataclass(frozen=True)
class PublicBook:
    """One non-empty book from a stored order-book response."""

    available_at: datetime
    source: str
    endpoint: str
    market_ticker: str
    book: OrderBook


def load_books(root: Path) -> tuple[PublicBook, ...]:
    """Read ``kalshi-public/orderbooks``. Empty responses contribute nothing."""
    manifest = _mapping(_read(root / "kalshi-public" / "manifest.json"), "manifest")
    fetched = _stamp(_text(manifest.get("fetched_at"), "fetched_at"))
    endpoints = _endpoints(manifest)
    books: list[PublicBook] = []
    folder = root / "kalshi-public" / "orderbooks"
    for path in sorted(folder.glob("*.json")):
        relative = path.relative_to(root).as_posix()
        built = book_from_body(
            _read(path),
            market_ticker=path.stem,
            available_at=fetched,
            endpoint=endpoints[relative],
        )
        if built is not None:
            books.append(built)
    return tuple(books)


def book_from_body(
    payload: object,
    *,
    market_ticker: str,
    available_at: datetime,
    endpoint: str,
) -> PublicBook | None:
    """Build a book from price-and-size pairs. ``None`` when both sides are empty."""
    body = _mapping(payload, "orderbook")
    raw = _mapping(body.get("orderbook_fp"), "orderbook_fp")
    yes = _levels(_seq(raw.get("yes_dollars"), "yes_dollars"))
    no = _levels(_seq(raw.get("no_dollars"), "no_dollars"))
    if not yes and not no:
        return None
    book = OrderBook.from_yes_and_no_bids(
        market_ticker,
        yes,
        no,
        received_at=available_at,
        exchange_ts=None,
    )
    return PublicBook(
        available_at=ensure_utc(available_at),
        source=_SOURCE,
        endpoint=endpoint,
        market_ticker=market_ticker,
        book=book,
    )


def _levels(pairs: Sequence[object]) -> tuple[OrderBookLevel, ...]:
    levels: list[OrderBookLevel] = []
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) < 2:
            raise ValueError("an order-book level needs a price and a size")
        price = _decimal(pair[0], "price")
        size = _decimal(pair[1], "size")
        if size <= 0:
            continue
        levels.append(OrderBookLevel(price=price, quantity=size))
    return tuple(levels)


def _endpoints(manifest: Mapping[str, object]) -> dict[str, str]:
    found: dict[str, str] = {}
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        path = item.get("path")
        url = item.get("url")
        if isinstance(path, str) and isinstance(url, str):
            found[path] = url
    return found


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return payload


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{what} has a non-string key")
        mapped[key] = item
    return mapped


def _seq(value: object, what: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return tuple(value)


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return ensure_utc(parsed)


def _decimal(value: object, what: str) -> Decimal:
    if isinstance(value, bool | float):
        raise ValueError(f"{what} is not an exact decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError(f"{what} is not an exact decimal")
