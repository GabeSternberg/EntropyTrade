"""Distinct stored candlestick price changes. This module does not open a socket.

A change is this close minus the immediately previous close in the same
file, when both ``price.close_dollars`` fields are decimal strings. It is
not compared to 0.40 and it is not a threshold.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.candle_price import _close

_CANDLES = Path("kalshi-public/cli-window/candles")
_NO_PREVIOUS = "no previous close"
_MISSING_CLOSE = "missing price close"
_MISSING_PREVIOUS = "missing previous close"


@dataclass(frozen=True)
class ChangeValues:
    """Distinct changes. ``traded`` and ``promoted`` stay false."""

    changes: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_change_values(root: Path) -> ChangeValues:
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
        previous: Decimal | None = None
        started = False
        for index, row in enumerate(rows):
            close = _close(row)
            if not started:
                skipped.append(f"{label}#{index}: {_NO_PREVIOUS}")
                previous = close
                started = True
                continue
            if close is None:
                skipped.append(f"{label}#{index}: {_MISSING_CLOSE}")
                previous = None
                continue
            if previous is None:
                skipped.append(f"{label}#{index}: {_MISSING_PREVIOUS}")
                previous = close
                continue
            found.append(close - previous)
            previous = close
    if not found:
        raise ValueError("no stored price change")
    ordered = tuple(sorted(set(found)))
    return ChangeValues(
        changes=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def change_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_change_values(root)
    if found.traded or found.promoted:
        raise ValueError("the change-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick price changes have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} changes were missing and were not filled in.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
