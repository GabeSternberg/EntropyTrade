"""Sum of historical print sizes versus the stored market volume.

``count`` in the print table is contracts times 100. ``volume_fp`` is the
market's reported contract volume. The comparison is exact. A missing
volume stays missing, and a ticker with no stored print sums to zero
because the pull stored an empty list. A print is not a fill. This module
does not open a socket.
"""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_COUNT = Decimal(100)


@dataclass(frozen=True)
class VolumeCheck:
    """How often the print sizes add up to the stored volume."""

    markets: int
    missing_volume: int
    equal: int
    short: int
    long: int
    zero_prints: int
    guaranteed_fill: bool
    promoted: bool


def load_volume_check(root: Path) -> VolumeCheck:
    """Compare each market's print-size sum with its stored volume."""
    sums = _print_sums(root)
    markets = 0
    missing_volume = 0
    equal = 0
    short = 0
    long = 0
    zero_prints = 0
    folder = root / "kalshi-public"
    for path in sorted(folder.glob("historical-*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} is not an object")
        rows = payload.get("markets")
        if not isinstance(rows, list):
            raise ValueError(f"{path.name} has no markets")
        for market in rows:
            if not isinstance(market, dict):
                continue
            ticker = market.get("ticker")
            result = market.get("result")
            if not isinstance(ticker, str) or not ticker.startswith("KXHIGHPHIL-"):
                continue
            if result not in ("yes", "no"):
                continue
            markets += 1
            printed = sums.get(ticker, Decimal(0))
            if printed == 0:
                zero_prints += 1
            volume = _decimal(market.get("volume_fp"))
            if volume is None:
                missing_volume += 1
                continue
            if printed == volume:
                equal += 1
            elif printed < volume:
                short += 1
            else:
                long += 1
    return VolumeCheck(
        markets=markets,
        missing_volume=missing_volume,
        equal=equal,
        short=short,
        long=long,
        zero_prints=zero_prints,
        guaranteed_fill=False,
        promoted=False,
    )


def _print_sums(root: Path) -> Mapping[str, Decimal]:
    database = root / "kalshi-public" / "historical-trades" / "prints.sqlite"
    found: dict[str, Decimal] = {}
    with sqlite3.connect(database) as conn:
        rows = conn.execute(
            """
            select tickers.ticker, sum(prints.count)
            from prints
            join tickers on tickers.id = prints.ticker_id
            group by tickers.ticker
            """
        )
        for ticker, scaled in rows:
            if isinstance(scaled, bool) or not isinstance(scaled, int):
                raise ValueError(f"{ticker} print sizes are not an integer sum")
            found[str(ticker)] = Decimal(scaled) / _COUNT
    return found


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool | float):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except ArithmeticError:
            return None
    return None
