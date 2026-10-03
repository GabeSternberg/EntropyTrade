"""Stored candlestick volumes of exactly 0. This module does not open a socket.

A volume of 0 is not a missing field and it is not a size at the touch.
It is not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")
_FIELD = "volume_fp"
_ZERO = Decimal(0)


@dataclass(frozen=True)
class ZeroVolumes:
    """Zero volumes. ``traded`` and ``promoted`` stay false."""

    volumes: int
    zeros: int
    first: str
    last: str
    traded: bool
    promoted: bool


def load_zero_volumes(root: Path) -> ZeroVolumes:
    """Apply the written count. A missing volume is not a zero."""
    folder = root / _CANDLES
    volumes = 0
    zeros: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("candlesticks"), list):
            continue
        ticker = payload.get("ticker")
        label = ticker if isinstance(ticker, str) and ticker != "" else path.name
        rows: list[object] = payload["candlesticks"]
        for index, row in enumerate(rows):
            volume = _volume(row)
            if volume is None:
                continue
            volumes += 1
            if volume == _ZERO:
                zeros.append(f"{label}#{index}")
    if not zeros:
        raise ValueError("no stored zero volume")
    return ZeroVolumes(
        volumes=volumes,
        zeros=len(zeros),
        first=zeros[0],
        last=zeros[-1],
        traded=False,
        promoted=False,
    )


def zero_volumes_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_zero_volumes(root)
    if found.traded or found.promoted:
        raise ValueError("the zero-volume note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick volumes include",
            f"{found.zeros} values of 0.00.",
            f"The first is {found.first} and the last is {found.last}.",
            "0.00 is not a missing volume.",
            "Volume is not a size at the touch.",
            "The count was not compared to 0.40.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _volume(row: object) -> Decimal | None:
    if not isinstance(row, dict):
        return None
    value = row.get(_FIELD)
    if not isinstance(value, str) or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None
