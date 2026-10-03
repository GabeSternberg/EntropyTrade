"""Distinct stored candlestick spreads. This module does not open a socket.

A spread is the ask close minus the bid close. The count is not compared
to 0.40 and it is not a threshold.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_spread import _spread

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class SpreadValues:
    """Distinct spreads. ``traded`` and ``promoted`` stay false."""

    spreads: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_spread_values(root: Path) -> SpreadValues:
    """Apply the written count. A bad string is named, not invented."""
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
            spread = _spread(row)
            if spread is None:
                skipped.append(f"{label}#{index}: not a decimal close")
                continue
            found.append(spread)
    if not found:
        raise ValueError("no stored spread")
    ordered = tuple(sorted(set(found)))
    return SpreadValues(
        spreads=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def spread_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_spread_values(root)
    if found.traded or found.promoted:
        raise ValueError("the spread-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick spreads have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} closes were not decimals and were not filled in.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
