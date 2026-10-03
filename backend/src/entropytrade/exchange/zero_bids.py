"""Stored candlestick bids of exactly 0. This module does not open a socket.

A bid of 0 is not a fill, not an order book, and not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import _close, _decimal

_CANDLES = Path("kalshi-public/cli-window/candles")
_ZERO = Decimal(0)


@dataclass(frozen=True)
class ZeroBids:
    """Zero bids. ``traded`` and ``promoted`` stay false."""

    bids: int
    zeros: int
    first: str
    last: str
    traded: bool
    promoted: bool


def load_zero_bids(root: Path) -> ZeroBids:
    """Apply the written count. A missing bid is not a zero."""
    folder = root / _CANDLES
    bids = 0
    zeros: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
            continue
        ticker = payload.get("ticker")
        label = ticker if isinstance(ticker, str) and ticker != "" else path.name
        rows: list[object] = payload["candlesticks"]
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            bid = _decimal(_close(row, "yes_bid"))
            if bid is None:
                continue
            bids += 1
            if bid == _ZERO:
                zeros.append(f"{label}#{index}")
    if not zeros:
        raise ValueError("no stored zero bid")
    return ZeroBids(
        bids=bids,
        zeros=len(zeros),
        first=zeros[0],
        last=zeros[-1],
        traded=False,
        promoted=False,
    )


def zero_bids_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_zero_bids(root)
    if found.traded or found.promoted:
        raise ValueError("the zero-bid note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick bids include",
            f"{found.zeros} closes of 0.0000.",
            f"The first is {found.first} and the last is {found.last}.",
            "0.0000 is not a fill.",
            "A candle is not an order book.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
