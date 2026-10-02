"""Last print strictly before close_time, versus the stored result.

The YES line is the same 0.50 used for the last print in the tape. A print
at the close instant is too late. Markets with no earlier print, and
markets whose close time was not stored, get no guess. A missing time is
not replaced. This is not a fill and it is not promoted. This module does
not open a socket.
"""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.historical_trades import _encode_time
from entropytrade.weather.last_print import GUESS_YES_AT

_PRICE = Decimal(10000)


@dataclass(frozen=True)
class BeforeCloseScore:
    """How often a pre-close print matches the stored result."""

    markets: int
    with_close: int
    without_close: int
    with_prints: int
    without_prints: int
    prints_at_or_after_close: int
    guesses_yes: int
    agreements: int
    fidelity: str
    guaranteed_fill: bool
    promoted: bool


def load_before_close_score(root: Path) -> BeforeCloseScore:
    """Score prints from before each market's close time."""
    results, cutoffs = _markets(root)
    last = _prices_before(root, cutoffs)
    guesses_yes = 0
    agreements = 0
    for ticker, result in results.items():
        price = last.get(ticker)
        if price is None:
            continue
        guess_yes = price >= GUESS_YES_AT
        if guess_yes:
            guesses_yes += 1
        if (guess_yes and result == "yes") or (not guess_yes and result == "no"):
            agreements += 1
    with_prints = sum(1 for ticker in cutoffs if ticker in last)
    return BeforeCloseScore(
        markets=len(results),
        with_close=len(cutoffs),
        without_close=len(results) - len(cutoffs),
        with_prints=with_prints,
        without_prints=len(cutoffs) - with_prints,
        prints_at_or_after_close=_late_prints(root, cutoffs),
        guesses_yes=guesses_yes,
        agreements=agreements,
        fidelity="trade-print",
        guaranteed_fill=False,
        promoted=False,
    )


def _markets(root: Path) -> tuple[dict[str, str], dict[str, int]]:
    results: dict[str, str] = {}
    cutoffs: dict[str, int] = {}
    folder = root / "kalshi-public"
    for path in sorted(folder.glob("historical-*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} is not an object")
        markets = payload.get("markets")
        if not isinstance(markets, list):
            raise ValueError(f"{path.name} has no markets")
        for market in markets:
            if not isinstance(market, dict):
                continue
            ticker = market.get("ticker")
            result = market.get("result")
            if not isinstance(ticker, str) or not ticker.startswith("KXHIGHPHIL-"):
                continue
            if result not in ("yes", "no"):
                continue
            results[ticker] = result
            close = market.get("close_time")
            if not isinstance(close, str) or close == "":
                continue
            cutoffs[ticker] = _encode_time(close)
    return results, cutoffs


def _late_prints(root: Path, cutoffs: Mapping[str, int]) -> int:
    database = root / "kalshi-public" / "historical-trades" / "prints.sqlite"
    with sqlite3.connect(database) as conn:
        _cutoff_table(conn, cutoffs)
        row = conn.execute(
            """
            select count(*)
            from prints
            join tickers on tickers.id = prints.ticker_id
            join cutoff on cutoff.ticker = tickers.ticker
            where prints.created_us >= cutoff.close_us
            """
        ).fetchone()
    if row is None or isinstance(row[0], bool) or not isinstance(row[0], int):
        raise ValueError("late prints are not a count")
    return row[0]


def _cutoff_table(conn: sqlite3.Connection, cutoffs: Mapping[str, int]) -> None:
    conn.execute("create temp table cutoff (ticker text primary key, close_us integer not null)")
    conn.executemany(
        "insert into cutoff (ticker, close_us) values (?, ?)",
        cutoffs.items(),
    )


def _prices_before(root: Path, cutoffs: Mapping[str, int]) -> Mapping[str, Decimal]:
    database = root / "kalshi-public" / "historical-trades" / "prints.sqlite"
    query = """
        select tickers.ticker, max(prints.yes_price)
        from prints
        join tickers on tickers.id = prints.ticker_id
        join cutoff on cutoff.ticker = tickers.ticker
        join (
            select prints.ticker_id as ticker_id, max(prints.created_us) as created_us
            from prints
            join tickers on tickers.id = prints.ticker_id
            join cutoff on cutoff.ticker = tickers.ticker
            where prints.created_us < cutoff.close_us
            group by prints.ticker_id
        ) latest
          on latest.ticker_id = prints.ticker_id
         and latest.created_us = prints.created_us
        group by tickers.ticker
    """
    found: dict[str, Decimal] = {}
    with sqlite3.connect(database) as conn:
        _cutoff_table(conn, cutoffs)
        for ticker, scaled in conn.execute(query):
            found[str(ticker)] = Decimal(int(scaled)) / _PRICE
    return found
