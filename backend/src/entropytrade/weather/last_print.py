"""Last historical print versus the stored market result.

A YES price at or above 0.50 is a YES guess. Anything lower is a NO guess.
If several prints share the last timestamp, the guess uses the highest YES
price among them. This is not a fill and it is not promoted. The 0.50 line
is fixed. This module does not open a socket.
"""

import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

GUESS_YES_AT = Decimal("0.50")
_PRICE = Decimal(10000)


@dataclass(frozen=True)
class LastPrintScore:
    """How often the last print's side matches the stored result."""

    markets: int
    with_prints: int
    without_prints: int
    guesses_yes: int
    agreements: int
    fidelity: str
    guaranteed_fill: bool
    promoted: bool


def load_last_print_score(root: Path) -> LastPrintScore:
    """Score stored results. Markets with no print are not given a guess."""
    results = _results(root)
    last = _last_prices(root)
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
    with_prints = sum(1 for ticker in results if ticker in last)
    return LastPrintScore(
        markets=len(results),
        with_prints=with_prints,
        without_prints=len(results) - with_prints,
        guesses_yes=guesses_yes,
        agreements=agreements,
        fidelity="trade-print",
        guaranteed_fill=False,
        promoted=False,
    )


def _results(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
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
            found[ticker] = result
    return found


def _last_prices(root: Path) -> Mapping[str, Decimal]:
    database = root / "kalshi-public" / "historical-trades" / "prints.sqlite"
    query = """
        select tickers.ticker, max(prints.yes_price)
        from prints
        join tickers on tickers.id = prints.ticker_id
        join (
            select ticker_id, max(created_us) as created_us
            from prints
            group by ticker_id
        ) latest
          on latest.ticker_id = prints.ticker_id
         and latest.created_us = prints.created_us
        group by tickers.ticker
    """
    found: dict[str, Decimal] = {}
    with closing(sqlite3.connect(database)) as conn, conn:
        for ticker, scaled in conn.execute(query):
            found[str(ticker)] = Decimal(int(scaled)) / _PRICE
    return found
