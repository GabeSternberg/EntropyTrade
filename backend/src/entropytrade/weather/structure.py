"""Structural scan of stored KXHIGHPHIL strikes. No order is submitted.

A threshold ladder uses a YES ask only when a stored book has a size. A
candle or a trade print is flagged non-executable and is not a price in
that check. Between-bins are not a greater-than ladder.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.market_data import OrderBook
from entropytrade.exchange.public_tape import load_books
from entropytrade.strategies.scanner import ThresholdMark, Violation, scan_thresholds

_WINDOW = Path("kalshi-public/cli-window")
_TRADES = Path("kalshi-public/trades/manifest.json")


@dataclass(frozen=True)
class StructuralScan:
    """Findings only. ``orders_submitted`` stays zero."""

    monotonic: tuple[Violation, ...]
    non_executable: tuple[Violation, ...]
    executable_thresholds: int
    orders_submitted: int


def load_structural_scan(root: Path) -> StructuralScan:
    """Scan stored strikes. Nothing is sent to a broker."""
    books = {item.market_ticker: item.book for item in load_books(root)}
    monotonic: list[Violation] = []
    executable = 0
    for marks in _threshold_groups(books).values():
        executable += len(marks)
        monotonic.extend(item for item in scan_thresholds(marks) if item.kind == "monotonic")
    flagged = [
        Violation(
            kind="non_executable",
            tickers=(ticker,),
            detail="candle or trade only; not used as a price",
        )
        for ticker in _window_tickers(root)
        if ticker not in books and (_has_candle(root, ticker) or ticker in _trade_tickers(root))
    ]
    return StructuralScan(
        monotonic=tuple(monotonic),
        non_executable=tuple(flagged),
        executable_thresholds=executable,
        orders_submitted=0,
    )


def _threshold_groups(books: Mapping[str, OrderBook]) -> dict[str, tuple[ThresholdMark, ...]]:
    grouped: dict[str, list[ThresholdMark]] = {}
    for ticker, book in books.items():
        floor = _threshold_floor(ticker)
        if floor is None:
            continue
        event = ticker.rsplit("-", 1)[0]
        grouped.setdefault(event, []).append(ThresholdMark(floor=floor, ticker=ticker, book=book))
    return {event: tuple(marks) for event, marks in grouped.items()}


def _threshold_floor(ticker: str) -> Decimal | None:
    suffix = ticker.rsplit("-", 1)[-1]
    if len(suffix) < 2 or not suffix.startswith("T") or not suffix[1:].isdigit():
        return None
    return Decimal(suffix[1:])


def _window_tickers(root: Path) -> tuple[str, ...]:
    manifest = _mapping(_read(root / _WINDOW / "manifest.json"), "cli-window manifest")
    found: list[str] = []
    seen: set[str] = set()
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        url = item.get("url")
        if not isinstance(url, str) or "/orderbook" not in url:
            continue
        ticker = url.split("/markets/", maxsplit=1)[-1].split("/", maxsplit=1)[0]
        if ticker not in seen:
            seen.add(ticker)
            found.append(ticker)
    return tuple(found)


def _trade_tickers(root: Path) -> set[str]:
    manifest = _mapping(_read(root / _TRADES), "trades manifest")
    found: set[str] = set()
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        path = item.get("path")
        size = item.get("bytes")
        if not isinstance(path, str) or "/trades/pages/" not in path:
            continue
        if isinstance(size, bool) or not isinstance(size, int) or size <= 80:
            continue
        name = path.rsplit("/", 1)[-1].removesuffix(".json")
        ticker, page = name.rsplit("-", 1)
        if page.isdigit():
            found.add(ticker)
    return found


def _has_candle(root: Path, ticker: str) -> bool:
    return (root / _WINDOW / "candles" / f"{ticker}.json").is_file()


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
