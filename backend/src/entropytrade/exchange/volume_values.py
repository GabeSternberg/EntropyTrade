"""Distinct stored candlestick volumes. This module does not open a socket.

A volume counts only when ``volume_fp`` is a decimal string. It is not a
size at the touch and it is not compared to 0.40.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")
_FIELD = "volume_fp"


@dataclass(frozen=True)
class VolumeValues:
    """Distinct volumes. ``traded`` and ``promoted`` stay false."""

    volumes: int
    distinct: int
    values: tuple[Decimal, ...]
    smallest: Decimal
    largest: Decimal
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_volume_values(root: Path) -> VolumeValues:
    """Apply the written count. A missing volume is named, not invented."""
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
            volume = _volume(row)
            if volume is None:
                skipped.append(f"{label}#{index}: missing volume")
                continue
            found.append(volume)
    if not found:
        raise ValueError("no stored volume")
    ordered = tuple(sorted(set(found)))
    return VolumeValues(
        volumes=len(found),
        distinct=len(ordered),
        values=ordered,
        smallest=ordered[0],
        largest=ordered[-1],
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def volume_values_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_volume_values(root)
    if found.traded or found.promoted:
        raise ValueError("the volume-value note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick volumes have",
            f"{found.distinct} distinct values.",
            f"The smallest is {found.smallest} and the largest is {found.largest}.",
            f"{len(found.skipped)} volumes were missing and were not filled in.",
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
