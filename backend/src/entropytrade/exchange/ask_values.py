"""Distinct stored candlestick ask closes. This module does not open a socket.

An ask counts only when ``yes_ask.close_dollars`` is a decimal string. It is
not an order book and it is not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import _close, _decimal

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class AskValues:
    """Distinct asks. ``traded`` and ``promoted`` stay false."""

    asks: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_ask_values(root: Path) -> AskValues:
    """Apply the written count. A missing ask is named, not invented."""
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
                skipped.append(f"{label}#{index}: missing ask close")
                continue
            ask = _decimal(_close(row, "yes_ask"))
            if ask is None:
                skipped.append(f"{label}#{index}: missing ask close")
                continue
            found.append(ask)
    if not found:
        raise ValueError("no stored ask close")
    ordered = tuple(sorted(set(found)))
    return AskValues(
        asks=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def ask_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_ask_values(root)
    if found.traded or found.promoted:
        raise ValueError("the ask-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick ask closes have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} asks were missing and were not filled in.",
            "A candle is not an order book.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
