"""Stored candlestick bid and ask closes. This module does not open a socket.

A string close, including ``0.0000``, is a stored quote. It is not an order
book, it is not aligned to 15:00 UTC, and it is not a threshold.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CandleQuotes:
    """Counts from stored files. ``traded`` and ``promoted`` stay false."""

    files: int
    candlesticks: int
    bids: int
    asks: int
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_candle_quotes(root: Path) -> CandleQuotes:
    """Apply the written count. A missing close is named, not invented."""
    folder = root / _CANDLES
    files = 0
    candlesticks = 0
    bids = 0
    asks = 0
    skipped: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
            skipped.append(f"{path.name}: not a candlestick file")
            continue
        files += 1
        ticker = payload.get("ticker")
        label = ticker if isinstance(ticker, str) and ticker != "" else path.name
        rows: list[object] = payload["candlesticks"]
        for index, row in enumerate(rows):
            candlesticks += 1
            if _close(row, "yes_bid"):
                bids += 1
            else:
                skipped.append(f"{label}#{index}: missing bid")
            if _close(row, "yes_ask"):
                asks += 1
            else:
                skipped.append(f"{label}#{index}: missing ask")
    return CandleQuotes(
        files=files,
        candlesticks=candlesticks,
        bids=bids,
        asks=asks,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def candle_quotes_note(root: Path) -> str:
    """One sentence. The CLI coverage rows stay unchanged."""
    found = load_candle_quotes(root)
    if found.traded or found.promoted:
        raise ValueError("the candle-quote note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick files have",
            f"{found.files} files and {found.candlesticks} candlesticks.",
            f"{found.bids} bids and {found.asks} asks are strings, including 0.0000.",
            f"{len(found.skipped)} fields were missing and were not filled in.",
            "A candle is not an order book.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _close(row: object, side: str) -> bool:
    if not isinstance(row, dict):
        return False
    quote = row.get(side)
    if not isinstance(quote, dict):
        return False
    close = quote.get("close_dollars")
    return isinstance(close, str) and close != ""
