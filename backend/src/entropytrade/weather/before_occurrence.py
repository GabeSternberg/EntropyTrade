"""Last print strictly before occurrence_datetime, versus the stored result.

The YES line is the same 0.50 used for the last print in the tape. A print
at the occurrence instant is too late. Markets with no earlier print, and
markets whose occurrence time was not stored, get no guess. A missing time
is not replaced. This is not a fill and it is not promoted. This module
does not open a socket.
"""

import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.historical_trades import _encode_time
from entropytrade.weather.last_print import GUESS_YES_AT

_PRICE = Decimal(10000)


@dataclass(frozen=True)
class BeforeOccurrenceScore:
    """How often a pre-occurrence print matches the stored result."""

    markets: int
    with_occurrence: int
    without_occurrence: int
    with_prints: int
    without_prints: int
    guesses_yes: int
    agreements: int
    fidelity: str
    guaranteed_fill: bool
    promoted: bool


def load_before_occurrence_score(root: Path) -> BeforeOccurrenceScore:
    """Score prints from before each market's occurrence time."""
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
    return BeforeOccurrenceScore(
        markets=len(results),
        with_occurrence=len(cutoffs),
        without_occurrence=len(results) - len(cutoffs),
        with_prints=with_prints,
        without_prints=len(cutoffs) - with_prints,
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
            occurrence = market.get("occurrence_datetime")
            if not isinstance(occurrence, str) or occurrence == "":
                continue
            cutoffs[ticker] = _encode_time(occurrence)
    return results, cutoffs


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
            where prints.created_us < cutoff.occurrence_us
            group by prints.ticker_id
        ) latest
          on latest.ticker_id = prints.ticker_id
         and latest.created_us = prints.created_us
        group by tickers.ticker
    """
    found: dict[str, Decimal] = {}
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute(
            "create temp table cutoff (ticker text primary key, occurrence_us integer not null)"
        )
        conn.executemany(
            "insert into cutoff (ticker, occurrence_us) values (?, ?)",
            cutoffs.items(),
        )
        for ticker, scaled in conn.execute(query):
            found[str(ticker)] = Decimal(int(scaled)) / _PRICE
    return found
