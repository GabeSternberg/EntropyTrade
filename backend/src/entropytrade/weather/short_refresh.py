"""Fresh historical trade sizes for the markets short of volume.

The rows are a second public pull of ``/historical/trades``. A print is not
a fill. These rows are not an input to the 2026 CLI replay. Raw pages stay
under ``data/raw``. This module does not open a socket.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_COUNT = Decimal(100)


@dataclass(frozen=True)
class ShortRefresh:
    """Whether a second pull changed the size sum or closed the volume gap."""

    markets: int
    unchanged: int
    changed: int
    still_short: int
    now_equal: int
    now_long: int
    cursor_empty: int
    joined_to_cli_replay: bool
    guaranteed_fill: bool
    promoted: bool


def load_short_refresh(root: Path) -> ShortRefresh:
    """Compare the fresh sums with the stored tape and with volume."""
    manifest = _manifest(root)
    if manifest.get("joined_to_cli_replay") is not False:
        raise ValueError("the refresh must stay out of the CLI replay")
    rows = manifest.get("tickers")
    if not isinstance(rows, list) or len(rows) == 0:
        raise ValueError("the refresh has no tickers")
    stored = _stored_sums(root)
    volumes = _volumes(root)
    unchanged = 0
    still_short = 0
    now_equal = 0
    now_long = 0
    cursor_empty = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("a refresh row is not an object")
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or ticker == "":
            raise ValueError("a refresh row has no ticker")
        fresh = _decimal(row.get("fresh_sum"))
        volume = volumes.get(ticker)
        if fresh is None or volume is None or ticker not in stored:
            raise ValueError(f"{ticker} cannot be compared")
        if fresh == stored[ticker]:
            unchanged += 1
        if fresh < volume:
            still_short += 1
        elif fresh == volume:
            now_equal += 1
        else:
            now_long += 1
        if row.get("cursor_empty") is True:
            cursor_empty += 1
    markets = len(rows)
    return ShortRefresh(
        markets=markets,
        unchanged=unchanged,
        changed=markets - unchanged,
        still_short=still_short,
        now_equal=now_equal,
        now_long=now_long,
        cursor_empty=cursor_empty,
        joined_to_cli_replay=False,
        guaranteed_fill=False,
        promoted=False,
    )


def load_fresh_sum(root: Path, ticker: str) -> Decimal:
    """The size sum from the second pull. Not a fill."""
    for row in _rows(root):
        if row.get("ticker") == ticker:
            fresh = _decimal(row.get("fresh_sum"))
            if fresh is None:
                raise ValueError(f"{ticker} has no fresh sum")
            return fresh
    raise ValueError(f"{ticker} was not refreshed")


def _manifest(root: Path) -> dict[str, object]:
    path = root / "kalshi-public" / "historical-trades" / "short-refresh.json"
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("refresh manifest is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError("refresh manifest has a non-string key")
        mapped[key] = item
    return mapped


def _rows(root: Path) -> tuple[dict[str, object], ...]:
    rows = _manifest(root).get("tickers")
    if not isinstance(rows, list):
        raise ValueError("the refresh has no tickers")
    found: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("a refresh row is not an object")
        mapped: dict[str, object] = {}
        for key, item in row.items():
            if not isinstance(key, str):
                raise ValueError("a refresh row has a non-string key")
            mapped[key] = item
        found.append(mapped)
    return tuple(found)


def _stored_sums(root: Path) -> dict[str, Decimal]:
    database = root / "kalshi-public" / "historical-trades" / "prints.sqlite"
    found: dict[str, Decimal] = {}
    with closing(sqlite3.connect(database)) as conn, conn:
        query = """
            select tickers.ticker, sum(prints.count)
            from prints
            join tickers on tickers.id = prints.ticker_id
            group by tickers.ticker
        """
        for ticker, scaled in conn.execute(query):
            if isinstance(scaled, bool) or not isinstance(scaled, int):
                raise ValueError(f"{ticker} print sizes are not an integer sum")
            found[str(ticker)] = Decimal(scaled) / _COUNT
    return found


def _volumes(root: Path) -> dict[str, Decimal]:
    found: dict[str, Decimal] = {}
    folder = root / "kalshi-public"
    for path in sorted(folder.glob("historical-*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} is not an object")
        markets = payload.get("markets")
        if not isinstance(markets, list):
            raise ValueError(f"{path.name} has no markets")
        for market in markets:
            if not isinstance(market, dict):
                continue
            ticker = market.get("ticker")
            if not isinstance(ticker, str):
                continue
            volume = _decimal(market.get("volume_fp"))
            if volume is not None:
                found[ticker] = volume
    return found


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool | float) or value is None or value == "":
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
