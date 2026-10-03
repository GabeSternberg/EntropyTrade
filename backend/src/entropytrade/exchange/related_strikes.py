"""Stored candlestick strike suffixes. This module does not open a socket.

The strike is the suffix after the last hyphen. A missing ticker is named.
No neighbor bracket is invented. This is not a trade.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_CANDLES = Path("kalshi-public/cli-window/candles")


@dataclass(frozen=True)
class RelatedStrikes:
    """Distinct suffixes. ``traded`` and ``promoted`` stay false."""

    files: int
    strikes: tuple[str, ...]
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_related_strikes(root: Path) -> RelatedStrikes:
    """Apply the written count. A ticker is not rewritten."""
    folder = root / _CANDLES
    files = 0
    found: set[str] = set()
    skipped: list[str] = []
    for path in sorted(folder.glob("*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            skipped.append(f"{path.name}: not a candlestick file")
            continue
        ticker = payload.get("ticker")
        if not isinstance(ticker, str) or "-" not in ticker:
            skipped.append(f"{path.name}: missing ticker")
            continue
        files += 1
        found.add(ticker.rsplit("-", maxsplit=1)[-1])
    return RelatedStrikes(
        files=files,
        strikes=tuple(sorted(found)),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def related_strikes_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_related_strikes(root)
    if found.traded or found.promoted:
        raise ValueError("the related-strike note must not trade")
    includes = "B80.5" in found.strikes
    return " ".join(
        (
            "The stored Philadelphia candlestick tickers have",
            f"{len(found.strikes)} distinct strikes across {found.files} files.",
            f"{len(found.skipped)} files had no ticker and were not filled in.",
            "B80.5 is present." if includes else "B80.5 is absent.",
            "No neighbor bracket was invented.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
