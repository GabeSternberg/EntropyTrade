"""Stored historical trade prints. This module does not open a socket.

The rows are prints from ``/historical/trades``. A print is not a fill.
These rows are not an input to the 2026 CLI replay. Raw response pages stay
on disk under ``data/raw`` and are not part of the commit.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

_RELATIVE = Path("kalshi-public/historical-trades")
_TABLE = "prints.sqlite"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_PRICE = Decimal(10000)
_COUNT = Decimal(100)


@dataclass(frozen=True)
class HistoricalPrint:
    """One reported historical trade. ``count`` is the reported size."""

    ticker: str
    created_at: datetime
    yes_price: Decimal
    count: Decimal
    endpoint: str


@dataclass(frozen=True)
class HistoricalTape:
    """Counts from the committed table. Not a book and not a fill."""

    fetched_at: str
    endpoint: str
    tickers: int
    tickers_ok: int
    tickers_with_prints: int
    failed_calls: int
    trade_count: int
    joined_to_cli_replay: bool


def load_historical_tape(root: Path) -> HistoricalTape:
    """Read the manifest and check it against the sqlite table."""
    folder = root / _RELATIVE
    manifest = _read_manifest(folder / "manifest.json")
    endpoint = _text(manifest.get("endpoint"), "endpoint")
    declared = _count(manifest.get("trade_count"), "trade_count")
    with closing(sqlite3.connect(folder / _TABLE)) as conn, conn:
        row = conn.execute("select count(*) from prints").fetchone()
        distinct = conn.execute("select count(*) from tickers").fetchone()
        stored_endpoint = conn.execute("select url from endpoint").fetchone()
    if row is None or distinct is None or stored_endpoint is None:
        raise ValueError("the historical table is empty")
    if int(row[0]) != declared:
        raise ValueError("the historical table does not match the trade count")
    with_prints = _count(manifest.get("tickers_with_prints"), "tickers_with_prints")
    if int(distinct[0]) != with_prints:
        raise ValueError("the historical table does not match the ticker count")
    if str(stored_endpoint[0]) != endpoint:
        raise ValueError("the historical table cites a different endpoint")
    if manifest.get("joined_to_cli_replay") is not False:
        raise ValueError("historical prints must stay out of the CLI replay")
    return HistoricalTape(
        fetched_at=_text(manifest.get("fetched_at"), "fetched_at"),
        endpoint=endpoint,
        tickers=_count(manifest.get("tickers"), "tickers"),
        tickers_ok=_count(manifest.get("tickers_ok"), "tickers_ok"),
        tickers_with_prints=_count(manifest.get("tickers_with_prints"), "tickers_with_prints"),
        failed_calls=_count(manifest.get("failed_calls"), "failed_calls"),
        trade_count=declared,
        joined_to_cli_replay=False,
    )


def load_historical_print(root: Path, *, ticker: str, created_at: str) -> HistoricalPrint:
    """One stored print. Used to prove a row was not invented."""
    folder = root / _RELATIVE
    micros = _encode_time(created_at)
    with closing(sqlite3.connect(folder / _TABLE)) as conn, conn:
        row = conn.execute(
            """
            select tickers.ticker, prints.created_us, prints.yes_price, prints.count, endpoint.url
            from prints
            join tickers on tickers.id = prints.ticker_id
            join endpoint
            where tickers.ticker = ? and prints.created_us = ?
            """,
            (ticker, micros),
        ).fetchone()
    if row is None:
        raise ValueError("that historical print is not stored")
    return HistoricalPrint(
        ticker=str(row[0]),
        created_at=_decode_time(int(row[1])),
        yes_price=Decimal(int(row[2])) / _PRICE,
        count=Decimal(int(row[3])) / _COUNT,
        endpoint=str(row[4]),
    )


def _read_manifest(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError("manifest has a non-string key")
        mapped[key] = item
    return mapped


def _encode_time(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    delta = parsed - _EPOCH
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + parsed.microsecond


def _decode_time(micros: int) -> datetime:
    return _EPOCH + timedelta(microseconds=micros)


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is not a count")
    return value
