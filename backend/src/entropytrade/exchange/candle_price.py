"""Stored candlestick price closes. This module does not open a socket.

A decimal ``price.close_dollars`` is stored as written. It is not divided,
it is not compared to 0.40, and it is not a probability.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CandlePrices:
    """Counts from stored files. ``traded`` and ``promoted`` stay false."""

    files: int
    candlesticks: int
    closes: int
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_candle_prices(root: Path) -> CandlePrices:
    """Apply the written count. A missing close is named, not invented."""
    folder = root / _CANDLES
    files = 0
    candlesticks = 0
    closes = 0
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
            if _close(row) is None:
                skipped.append(f"{label}#{index}: missing price close")
                continue
            closes += 1
    return CandlePrices(
        files=files,
        candlesticks=candlesticks,
        closes=closes,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def candle_price_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_candle_prices(root)
    if found.traded or found.promoted:
        raise ValueError("the candle-price note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick price closes cover",
            f"{found.closes} candlesticks.",
            f"{len(found.skipped)} closes were missing and were not filled in.",
            "A close was not divided.",
            "A close was not compared to 0.40.",
            "It was not called a probability.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _close(row: object) -> Decimal | None:
    if not isinstance(row, dict):
        return None
    price = row.get("price")
    if not isinstance(price, dict):
        return None
    close = price.get("close_dollars")
    if not isinstance(close, str) or close == "":
        return None
    try:
        return Decimal(close)
    except InvalidOperation:
        return None
