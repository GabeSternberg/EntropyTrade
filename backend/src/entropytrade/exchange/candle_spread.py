"""Stored candlestick spreads. This module does not open a socket.

The spread is the ask close minus the bid close. A zero spread is kept.
It is not compared to 0.40, it is not an order book, and it is not a threshold.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CandleSpreads:
    """Counts from stored files. ``traded`` and ``promoted`` stay false."""

    files: int
    candlesticks: int
    spreads: int
    zeros: int
    negatives: int
    first_time: str
    first_spread: Decimal
    last_time: str
    last_spread: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_candle_spreads(root: Path) -> CandleSpreads:
    """Apply the written rule. A bad string is named, not invented."""
    folder = root / _CANDLES
    files = 0
    candlesticks = 0
    spreads = 0
    zeros = 0
    negatives = 0
    skipped: list[str] = []
    first_time = ""
    first_spread = Decimal(0)
    last_time = ""
    last_spread = Decimal(0)
    seen = False
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
            spread = _spread(row)
            if spread is None:
                skipped.append(f"{label}#{index}: not a decimal close")
                continue
            spreads += 1
            if spread == 0:
                zeros += 1
            elif spread < 0:
                negatives += 1
            stamp = f"{label}#{index}"
            if not seen:
                first_time = stamp
                first_spread = spread
                seen = True
            last_time = stamp
            last_spread = spread
    if not seen:
        raise ValueError("no stored spread")
    return CandleSpreads(
        files=files,
        candlesticks=candlesticks,
        spreads=spreads,
        zeros=zeros,
        negatives=negatives,
        first_time=first_time,
        first_spread=first_spread,
        last_time=last_time,
        last_spread=last_spread,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def candle_spread_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_candle_spreads(root)
    if found.traded or found.promoted:
        raise ValueError("the candle-spread note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick spreads cover",
            f"{found.spreads} candlesticks.",
            f"{found.zeros} spreads are zero and {found.negatives} are negative.",
            f"{len(found.skipped)} closes were not decimals and were not filled in.",
            "A zero spread is kept.",
            "The spread was not compared to 0.40.",
            "A candle is not an order book.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _spread(row: object) -> Decimal | None:
    if not isinstance(row, dict):
        return None
    ask = _decimal(_close(row, "yes_ask"))
    bid = _decimal(_close(row, "yes_bid"))
    if ask is None or bid is None:
        return None
    return ask - bid


def _close(row: dict[str, object], side: str) -> str:
    quote = row.get(side)
    if not isinstance(quote, dict):
        return ""
    close = quote.get("close_dollars")
    if not isinstance(close, str):
        return ""
    return close


def _decimal(value: str) -> Decimal | None:
    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
