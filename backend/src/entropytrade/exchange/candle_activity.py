"""Stored candlestick volume and open interest. This module does not open a socket.

A string field, including ``0.00``, is stored activity. Volume is not a size
at the touch. It is not aligned to 15:00 UTC and it is not a threshold.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class CandleActivity:
    """Counts from stored files. ``traded`` and ``promoted`` stay false."""

    files: int
    candlesticks: int
    volumes: int
    open_interest: int
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_candle_activity(root: Path) -> CandleActivity:
    """Apply the written count. A missing field is named, not invented."""
    folder = root / _CANDLES
    files = 0
    candlesticks = 0
    volumes = 0
    open_interest = 0
    skipped: list[str] = []
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
            if _text(row, "volume_fp"):
                volumes += 1
            else:
                skipped.append(f"{label}#{index}: missing volume")
            if _text(row, "open_interest_fp"):
                open_interest += 1
            else:
                skipped.append(f"{label}#{index}: missing open interest")
    return CandleActivity(
        files=files,
        candlesticks=candlesticks,
        volumes=volumes,
        open_interest=open_interest,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def candle_activity_note(root: Path) -> str:
    """One sentence. The CLI coverage rows stay unchanged."""
    found = load_candle_activity(root)
    if found.traded or found.promoted:
        raise ValueError("the candle-activity note must not trade")
    return " ".join(
        (
            "The stored Philadelphia candlestick files have",
            f"{found.files} files and {found.candlesticks} candlesticks.",
            f"{found.volumes} volumes and {found.open_interest} open-interest values are strings,",
            "including 0.00.",
            f"{len(found.skipped)} fields were missing and were not filled in.",
            "Volume is not a size at the touch.",
            "It was not aligned to 15:00 UTC.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _text(row: object, key: str) -> bool:
    if not isinstance(row, dict):
        return False
    value = row.get(key)
    return isinstance(value, str) and value != ""
