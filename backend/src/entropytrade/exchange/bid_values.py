"""Distinct stored candlestick bid closes. This module does not open a socket.

A bid counts only when ``yes_bid.close_dollars`` is a decimal string. It is
not an order book and it is not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import _close, _decimal

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class BidValues:
    """Distinct bids. ``traded`` and ``promoted`` stay false."""

    bids: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_bid_values(root: Path) -> BidValues:
    """Apply the written count. A missing bid is named, not invented."""
    folder = root / _CANDLES
    found: list[Decimal] = []
    skipped: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
            skipped.append(f"{path.name}: not a candlestick file")
            continue
        ticker = payload.get("ticker")
        label = ticker if isinstance(ticker, str) and ticker != "" else path.name
        rows: list[object] = payload["candlesticks"]
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                skipped.append(f"{label}#{index}: missing bid close")
                continue
            bid = _decimal(_close(row, "yes_bid"))
            if bid is None:
                skipped.append(f"{label}#{index}: missing bid close")
                continue
            found.append(bid)
    if not found:
        raise ValueError("no stored bid close")
    ordered = tuple(sorted(set(found)))
    return BidValues(
        bids=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def bid_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_bid_values(root)
    if found.traded or found.promoted:
        raise ValueError("the bid-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick bid closes have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} bids were missing and were not filled in.",
            "A candle is not an order book.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
