"""Append-only SQLite store for the market recorder.

Natural keys make a restart a no-op for rows that were already durable: the same trade,
the same rule text, and the same frame sequence are inserted with ``INSERT OR IGNORE``.
The file is opened in WAL mode so a crash mid-write does not tear a committed row.
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from entropytrade.domain.historical import ApiOrigin, HistoricalCutoff
from entropytrade.domain.ids import content_hash
from entropytrade.domain.market import Event, Market, Series
from entropytrade.domain.market_data import TradePrint
from entropytrade.exchange.frames import MarketFrame


class Recorder:
    """One SQLite file. Safe to reopen; duplicates of stored identities are ignored."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._create()

    def close(self) -> None:
        self._db.close()

    def _create(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS raw_payloads (
                body_hash TEXT PRIMARY KEY,
                origin TEXT NOT NULL,
                path TEXT NOT NULL,
                status INTEGER NOT NULL,
                received_at TEXT NOT NULL,
                body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rule_versions (
                market_ticker TEXT NOT NULL,
                rules_hash TEXT NOT NULL,
                origin TEXT NOT NULL,
                exchange_index INTEGER,
                captured_at TEXT NOT NULL,
                rules_json TEXT NOT NULL,
                PRIMARY KEY (market_ticker, rules_hash)
            );
            CREATE TABLE IF NOT EXISTS market_metadata (
                market_ticker TEXT NOT NULL,
                version_hash TEXT NOT NULL,
                origin TEXT NOT NULL,
                exchange_index INTEGER,
                observed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (market_ticker, version_hash)
            );
            CREATE TABLE IF NOT EXISTS series_fees (
                ticker TEXT NOT NULL,
                fee_type TEXT NOT NULL,
                fee_multiplier TEXT NOT NULL,
                maker_pays INTEGER NOT NULL,
                exchange_index INTEGER,
                observed_at TEXT NOT NULL,
                PRIMARY KEY (ticker, fee_type, fee_multiplier, maker_pays)
            );
            CREATE TABLE IF NOT EXISTS events (
                event_ticker TEXT NOT NULL,
                version_hash TEXT NOT NULL,
                exchange_index INTEGER,
                observed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (event_ticker, version_hash)
            );
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                market_ticker TEXT NOT NULL,
                origin TEXT NOT NULL,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS frames (
                channel TEXT NOT NULL,
                sid INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (channel, sid, seq)
            );
            CREATE TABLE IF NOT EXISTS cutoff (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload_json TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def save_raw(
        self,
        *,
        origin: ApiOrigin,
        path: str,
        status: int,
        body: bytes,
        received_at: datetime,
    ) -> bool:
        digest = hashlib.sha256(body).hexdigest()
        cursor = self._db.execute(
            """
            INSERT OR IGNORE INTO raw_payloads
                (body_hash, origin, path, status, received_at, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (digest, origin.value, path, status, _iso(received_at), body.decode("utf-8")),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def save_market(self, market: Market, origin: ApiOrigin) -> None:
        rules = market.rules.model_dump(mode="json")
        self._db.execute(
            """
            INSERT OR IGNORE INTO rule_versions
                (market_ticker, rules_hash, origin, exchange_index, captured_at, rules_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                market.ticker,
                market.rules.rules_hash,
                origin.value,
                market.exchange_index,
                _iso(market.rules.captured_at),
                json.dumps(rules, sort_keys=True),
            ),
        )
        payload = market.model_dump(mode="json")
        payload["rules"].pop("captured_at", None)
        version = content_hash(payload)
        self._db.execute(
            """
            INSERT OR IGNORE INTO market_metadata
                (market_ticker, version_hash, origin, exchange_index, observed_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                market.ticker,
                version,
                origin.value,
                market.exchange_index,
                _iso(market.rules.captured_at),
                json.dumps(payload, sort_keys=True),
            ),
        )
        self._db.commit()

    def save_series(self, series: Series, observed_at: datetime) -> None:
        maker_pays = "maker" in series.fee_type.value
        self._db.execute(
            """
            INSERT OR IGNORE INTO series_fees
                (ticker, fee_type, fee_multiplier, maker_pays, exchange_index, observed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                series.ticker,
                series.fee_type.value,
                str(series.fee_multiplier),
                int(maker_pays),
                series.exchange_index,
                _iso(observed_at),
            ),
        )
        self._db.commit()

    def save_event(self, event: Event, observed_at: datetime) -> None:
        payload = event.model_dump(mode="json")
        version = content_hash(payload)
        self._db.execute(
            """
            INSERT OR IGNORE INTO events
                (event_ticker, version_hash, exchange_index, observed_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.event_ticker,
                version,
                event.exchange_index,
                _iso(observed_at),
                json.dumps(payload, sort_keys=True),
            ),
        )
        self._db.commit()

    def save_trade(self, trade: TradePrint, origin: ApiOrigin) -> bool:
        payload = trade.model_dump(mode="json")
        cursor = self._db.execute(
            """
            INSERT OR IGNORE INTO trades
                (trade_id, market_ticker, origin, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                trade.trade_id,
                trade.market_ticker,
                origin.value,
                _iso(trade.received_at),
                json.dumps(payload, sort_keys=True),
            ),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def save_frame(self, frame: MarketFrame) -> bool:
        seq = frame.seq
        if seq is None:
            return False
        payload = frame.model_dump(mode="json")
        cursor = self._db.execute(
            """
            INSERT OR IGNORE INTO frames (channel, sid, seq, received_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                frame.channel,
                frame.sid,
                seq,
                _iso(frame.received_at),
                json.dumps(payload, sort_keys=True),
            ),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def save_cutoff(self, cutoff: HistoricalCutoff) -> None:
        payload = cutoff.model_dump(mode="json")
        self._db.execute(
            """
            INSERT INTO cutoff (id, payload_json, observed_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload_json = excluded.payload_json,
                observed_at = excluded.observed_at
            """,
            (json.dumps(payload, sort_keys=True), _iso(cutoff.observed_at)),
        )
        self._db.commit()

    def count(self, table: str) -> int:
        queries = {
            "raw_payloads": "SELECT COUNT(*) AS n FROM raw_payloads",
            "rule_versions": "SELECT COUNT(*) AS n FROM rule_versions",
            "market_metadata": "SELECT COUNT(*) AS n FROM market_metadata",
            "series_fees": "SELECT COUNT(*) AS n FROM series_fees",
            "events": "SELECT COUNT(*) AS n FROM events",
            "trades": "SELECT COUNT(*) AS n FROM trades",
            "frames": "SELECT COUNT(*) AS n FROM frames",
            "cutoff": "SELECT COUNT(*) AS n FROM cutoff",
        }
        sql = queries.get(table)
        if sql is None:
            raise ValueError(f"unknown table {table}")
        row = self._db.execute(sql).fetchone()
        return int(row["n"])

    def frame_payloads(self) -> tuple[str, ...]:
        rows = self._db.execute(
            "SELECT payload_json FROM frames ORDER BY received_at, channel, sid, seq"
        ).fetchall()
        return tuple(str(row["payload_json"]) for row in rows)


def _iso(value: datetime) -> str:
    return value.isoformat()
