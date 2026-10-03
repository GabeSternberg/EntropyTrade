"""Stored candlestick price changes. This module does not open a socket.

The change is the close minus the previous close. A missing field is not
filled in. The change is not compared to 0.40 and it is not a threshold.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CandleChanges:
    """Counts from stored files. ``traded`` and ``promoted`` stay false."""

    files: int
    candlesticks: int
    changes: int
    zeros: int
    negatives: int
    first_time: str
    first_change: Decimal
    last_time: str
    last_change: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_candle_changes(root: Path) -> CandleChanges:
    """Apply the written rule. A missing previous is named, not invented."""
    folder = root / _CANDLES
    files = 0
    candlesticks = 0
    changes = 0
    zeros = 0
    negatives = 0
    skipped: list[str] = []
    first_time = ""
    first_change = Decimal(0)
    last_time = ""
    last_change = Decimal(0)
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
            change = _change(row)
            if change is None:
                skipped.append(f"{label}#{index}: missing price change")
                continue
            changes += 1
            if change == 0:
                zeros += 1
            elif change < 0:
                negatives += 1
            stamp = f"{label}#{index}"
            if not seen:
                first_time = stamp
                first_change = change
                seen = True
            last_time = stamp
            last_change = change
    if not seen:
        raise ValueError("no stored price change")
    return CandleChanges(
        files=files,
        candlesticks=candlesticks,
        changes=changes,
        zeros=zeros,
        negatives=negatives,
        first_time=first_time,
        first_change=first_change,
        last_time=last_time,
        last_change=last_change,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def candle_change_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_candle_changes(root)
    if found.traded or found.promoted:
        raise ValueError("the candle-change note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick price changes cover",
            f"{found.changes} candlesticks.",
            f"{found.zeros} changes are zero and {found.negatives} are negative.",
            f"{len(found.skipped)} fields were missing and were not filled in.",
            "A change was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _change(row: object) -> Decimal | None:
    if not isinstance(row, dict):
        return None
    price = row.get("price")
    if not isinstance(price, dict):
        return None
    close = _decimal(price.get("close_dollars"))
    previous = _decimal(price.get("previous_dollars"))
    if close is None or previous is None:
        return None
    return close - previous


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, str) or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
