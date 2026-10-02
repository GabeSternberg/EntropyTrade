"""Stored CLI-window public tape. This module does not open a socket.

Settled KXHIGHPHIL order books in the window came back empty. One empty
sample is kept. Candlestick files have bid and ask dollars and a volume, and
they are not order books: a volume is not a size at the touch.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.public_tape import book_from_body

_RELATIVE = "kalshi-public/cli-window"


@dataclass(frozen=True)
class CliWindowTape:
    """Counts from the stored pull. ``sized_books`` is books with a real size."""

    fetched_at: datetime
    host: str
    window_start: date
    window_end: date
    orderbook_empty: int
    orderbook_nonempty: int
    candles_stored: int
    failed_calls: int
    sized_books: int
    strike_count: int
    includes_b805: bool
    strikes_besides_b805: int
    touch_size_fields: int


def load_cli_window(root: Path) -> CliWindowTape:
    """Read ``kalshi-public/cli-window``. Empty books and candles add no size."""
    folder = root / _RELATIVE
    manifest = _mapping(_read(folder / "manifest.json"), "manifest")
    calls = _seq(manifest.get("calls"), "calls")
    empty = 0
    nonempty = 0
    candles = 0
    failed = 0
    strikes: set[str] = set()
    for call in calls:
        item = _mapping(call, "call")
        status = item.get("status")
        if status != 200:
            failed += 1
            continue
        url = _text(item.get("url"), "url")
        ticker = _ticker(url)
        if ticker is not None:
            strikes.add(ticker.rsplit("-", maxsplit=1)[-1])
        path = item.get("path")
        if "/orderbook" in url:
            if (
                book_from_body(
                    _body(root, path),
                    market_ticker=ticker or "unknown",
                    available_at=_stamp(_text(item.get("fetched_at"), "fetched_at")),
                    endpoint=url,
                )
                is None
            ):
                empty += 1
            else:
                nonempty += 1
            continue
        if "candlesticks" in url:
            if not isinstance(path, str):
                raise ValueError("a candlestick response was not stored")
            candles += 1
            _refuse_touch_size(_read(root / path))
    stored_candles = len(list((folder / "candles").glob("*.json")))
    if stored_candles != candles:
        raise ValueError("candlestick files do not match the manifest")
    declared_empty = _count(manifest.get("orderbook_empty"), "orderbook_empty")
    declared_nonempty = _count(manifest.get("orderbook_nonempty"), "orderbook_nonempty")
    declared_candles = _count(manifest.get("candles_stored"), "candles_stored")
    declared_failed = _count(manifest.get("failed_calls"), "failed_calls")
    if (empty, nonempty, candles, failed) != (
        declared_empty,
        declared_nonempty,
        declared_candles,
        declared_failed,
    ):
        raise ValueError("manifest counts do not match the stored calls")
    window = _seq(manifest.get("window"), "window")
    others = strikes - {"B80.5"}
    return CliWindowTape(
        fetched_at=_stamp(_text(manifest.get("fetched_at"), "fetched_at")),
        host=_text(manifest.get("host"), "host"),
        window_start=date.fromisoformat(_text(window[0], "window start")),
        window_end=date.fromisoformat(_text(window[1], "window end")),
        orderbook_empty=empty,
        orderbook_nonempty=nonempty,
        candles_stored=candles,
        failed_calls=failed,
        sized_books=nonempty,
        strike_count=len(strikes),
        includes_b805="B80.5" in strikes,
        strikes_besides_b805=len(others),
        touch_size_fields=0,
    )


def _body(root: Path, path: object) -> object:
    if path is None:
        return {"orderbook_fp": {"no_dollars": [], "yes_dollars": []}}
    if not isinstance(path, str) or path == "":
        raise ValueError("path is not text")
    return _read(root / path)


def _refuse_touch_size(payload: object) -> None:
    body = _mapping(payload, "candles")
    for candle in _seq(body.get("candlesticks"), "candlesticks"):
        row = _mapping(candle, "candle")
        for side in ("yes_bid", "yes_ask"):
            quote = row.get(side)
            if not isinstance(quote, dict):
                continue
            for key in quote:
                if not isinstance(key, str):
                    raise ValueError("a quote key is not text")
                if "size" in key or "quantity" in key or key.endswith("_fp"):
                    raise ValueError("a candlestick quote has a size field")


def _ticker(url: str) -> str | None:
    marker = "/markets/"
    start = url.find(marker)
    if start < 0:
        return None
    rest = url[start + len(marker) :]
    ticker = rest.split("/", maxsplit=1)[0]
    if ticker == "" or "?" in ticker:
        return None
    return ticker


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
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


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is not a count")
    return value


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return ensure_utc(parsed)
