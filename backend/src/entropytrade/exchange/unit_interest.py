"""Stored open interest of exactly 1. This module does not open a socket.

An open interest of 1 is not a size at the touch and it is not compared
to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")
_FIELD = "open_interest_fp"
_ONE = Decimal(1)


@dataclass(frozen=True)
class UnitInterest:
    """Open interest of 1. ``traded`` and ``promoted`` stay false."""

    rows: int
    ones: int
    first: str
    last: str
    traded: bool
    promoted: bool


def load_unit_interest(root: Path) -> UnitInterest:
    """Apply the written count. A missing value is not a one."""
    folder = root / _CANDLES
    rows_seen = 0
    ones: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
            continue
        ticker = payload.get("ticker")
        label = ticker if isinstance(ticker, str) and ticker != "" else path.name
        candles: list[object] = payload["candlesticks"]
        for index, row in enumerate(candles):
            interest = _interest(row)
            if interest is None:
                continue
            rows_seen += 1
            if interest == _ONE:
                ones.append(f"{label}#{index}")
    if not ones:
        raise ValueError("no stored open interest of 1")
    return UnitInterest(
        rows=rows_seen,
        ones=len(ones),
        first=ones[0],
        last=ones[-1],
        traded=False,
        promoted=False,
    )


def unit_interest_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_unit_interest(root)
    if found.traded or found.promoted:
        raise ValueError("the unit-interest note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick open-interest values include",
            f"{found.ones} values of 1.00.",
            f"The first is {found.first} and the last is {found.last}.",
            "1.00 is not a size at the touch.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _interest(row: object) -> Decimal | None:
    if not isinstance(row, dict):
        return None
    value = row.get(_FIELD)
    if not isinstance(value, str) or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
