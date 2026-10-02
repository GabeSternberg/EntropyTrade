"""Live ``/markets/trades`` for the markets short of historical volume.

The lists are empty in the stored pull. They are not added to the historical
table, they are not fills, and they are not joined to the 2026 CLI replay.
This module does not open a socket.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class LiveTradesShort:
    """How many live trade prints came back for the short markets."""

    markets: int
    trades: int
    empty: int
    added_to_historical_table: bool
    joined_to_cli_replay: bool
    guaranteed_fill: bool
    promoted: bool


def load_live_trades_short(root: Path) -> LiveTradesShort:
    """Read the stored live-trades manifest. Do not invent a size."""
    path = root / "kalshi-public" / "historical-trades" / "live-trades-short.json"
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("live trades manifest is not an object")
    if payload.get("added_to_historical_table") is not False:
        raise ValueError("live trades must stay out of the historical table")
    if payload.get("joined_to_cli_replay") is not False:
        raise ValueError("live trades must stay out of the CLI replay")
    rows = payload.get("tickers")
    if not isinstance(rows, list) or len(rows) == 0:
        raise ValueError("live trades manifest has no tickers")
    trades = 0
    empty = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("a live trades row is not an object")
        count = row.get("trades")
        fresh = _decimal(row.get("fresh_sum"))
        if isinstance(count, bool) or not isinstance(count, int) or fresh is None:
            raise ValueError("a live trades row has no count")
        if (count == 0) != (fresh == 0):
            raise ValueError("a live trades count and size disagree")
        trades += count
        if count == 0 and row.get("cursor_empty") is True:
            empty += 1
    return LiveTradesShort(
        markets=len(rows),
        trades=trades,
        empty=empty,
        added_to_historical_table=False,
        joined_to_cli_replay=False,
        guaranteed_fill=False,
        promoted=False,
    )


def _decimal(value: object) -> Decimal | None:
    if not isinstance(value, str) or value == "":
        return None
    try:
        return Decimal(value)
    except ArithmeticError:
        return None
