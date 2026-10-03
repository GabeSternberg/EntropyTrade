"""Stored candlestick asks of exactly 1. This module does not open a socket.

An ask of 1 is not a settlement, not a probability, and not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import _close, _decimal

_CANDLES = Path("kalshi-public/cli-window/candles")
_ONE = Decimal(1)


@dataclass(frozen=True)
class UnitAsks:
    """Asks of 1. ``traded`` and ``promoted`` stay false."""

    asks: int
    ones: int
    first: str
    last: str
    traded: bool
    promoted: bool


def load_unit_asks(root: Path) -> UnitAsks:
    """Apply the written count. A missing ask is not a one."""
    folder = root / _CANDLES
    asks = 0
    ones: list[str] = []
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
            ask = _decimal(_close(row, "yes_ask"))
            if ask is None:
                continue
            asks += 1
            if ask == _ONE:
                ones.append(f"{label}#{index}")
    if not ones:
        raise ValueError("no stored ask of 1")
    return UnitAsks(
        asks=asks,
        ones=len(ones),
        first=ones[0],
        last=ones[-1],
        traded=False,
        promoted=False,
    )


def unit_asks_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_unit_asks(root)
    if found.traded or found.promoted:
        raise ValueError("the unit-ask note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick asks include",
            f"{found.ones} closes of 1.0000.",
            f"The first is {found.first} and the last is {found.last}.",
            "1.0000 is not a settlement and is not a probability.",
            "A candle is not an order book.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
