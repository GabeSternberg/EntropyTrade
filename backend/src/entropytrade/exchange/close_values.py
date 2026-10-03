"""Distinct stored candlestick price closes. This module does not open a socket.

A close counts only when ``price.close_dollars`` is a decimal string. It is
not called a probability and it is not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_price import _close

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CloseValues:
    """Distinct closes. ``traded`` and ``promoted`` stay false."""

    closes: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_close_values(root: Path) -> CloseValues:
    """Apply the written count. A missing close is named, not invented."""
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
            close = _close(row)
            if close is None:
                skipped.append(f"{label}#{index}: missing price close")
                continue
            found.append(close)
    if not found:
        raise ValueError("no stored price close")
    ordered = tuple(sorted(set(found)))
    return CloseValues(
        closes=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def close_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_close_values(root)
    if found.traded or found.promoted:
        raise ValueError("the close-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick price closes have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} closes were missing and were not filled in.",
            "A close was not called a probability.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
