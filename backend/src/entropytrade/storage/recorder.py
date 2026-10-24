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
from uuid import uuid4

from entropytrade.domain.historical import ApiOrigin, HistoricalCutoff
from entropytrade.domain.ids import content_hash
from entropytrade.domain.market import Event, Market, Series
from entropytrade.domain.market_data import TradePrint
from entropytrade.domain.time import ensure_utc, utc_now
from entropytrade.exchange.frames import MarketFrame, TradeFrame


class Recorder:
    """One SQLite file. Safe to reopen; duplicates of stored identities are ignored."""

    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self._db = (
            sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
            if read_only
            else sqlite3.connect(path)
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        if not read_only:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            self._create()
            self._migrate()

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
        self.record_http(path=path, status=status, body=body, received_at=received_at)
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

    def save_market(
        self, market: Market, origin: ApiOrigin, *, raw_receipt_id: str | None = None
    ) -> None:
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
        self._db.execute(
            "INSERT OR IGNORE INTO market_observations "
            "(observation_id,market_ticker,observed_at,version_hash,payload,receipt_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                content_hash(market.model_dump(mode="json")),
                market.ticker,
                _iso(market.rules.captured_at),
                version,
                market.model_dump_json(),
                raw_receipt_id,
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
        with self._db:
            return self._insert_trade(trade, origin)

    def _insert_trade(self, trade: TradePrint, origin: ApiOrigin) -> bool:
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
        return cursor.rowcount == 1

    def save_frame(self, frame: MarketFrame, *, session_id: str = "legacy-api") -> bool:
        """Store a fact, retaining unsequenced frames and conflicting sequence payloads."""
        with self._db:
            return self._insert_frame(frame, session_id, None, utc_now())

    def _insert_frame(
        self, frame: MarketFrame, session_id: str, receipt_id: str | None, ingested: datetime
    ) -> bool:
        payload = frame.model_dump(mode="json")
        semantic = dict(payload)
        semantic.pop("received_at", None)
        identity = content_hash({"session": session_id, "payload": semantic})
        cursor = self._db.execute(
            """INSERT OR IGNORE INTO frames
            (record_id, session_id, channel, sid, seq, received_at, ingested_at,
             receipt_id, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                identity,
                session_id,
                frame.channel,
                frame.sid,
                frame.seq,
                _iso(frame.received_at),
                _iso(ingested),
                receipt_id,
                frame.model_dump_json(),
            ),
        )
        return cursor.rowcount == 1

    def bind_environment(self, environment: str) -> None:
        if environment not in {"production", "demo", "replay"}:
            raise ValueError("unknown recorder environment")
        existing = self._db.execute(
            "SELECT value FROM recorder_context WHERE key='environment'"
        ).fetchone()
        if existing is not None and existing[0] != environment:
            raise ValueError("recording environment mismatch; use a separate database")
        if existing is None and self.count("receipts") and environment != "replay":
            raise ValueError("existing unlabeled receipts cannot be certified; use a new database")
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO recorder_context VALUES ('environment', ?)", (environment,)
            )

    def start_session(self, at: datetime, *, mode: str = "live") -> str:
        session = str(uuid4())
        with self._db:
            self._db.execute(
                "INSERT INTO sessions(session_id, started_at, mode) VALUES (?, ?, ?)",
                (session, _iso(at), mode),
            )
        return session

    def end_session(self, session: str, at: datetime, reason: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE sessions SET ended_at=?, reason=? WHERE session_id=?",
                (_iso(at), reason, session),
            )

    def record_message(
        self,
        *,
        session: str,
        ordinal: int,
        raw: str,
        received_at: datetime,
        frame: MarketFrame | None,
        effects: tuple[str, ...] = (),
        error: str | None = None,
    ) -> str:
        """One FULL-synchronous transaction for raw receipt, normalized fact and integrity evidence.

        Replaying the same (session, ordinal) is idempotent. A distinct delivery always
        has its own receipt even when the normalized exchange fact is a duplicate.
        """
        receipt = content_hash({"session": session, "ordinal": ordinal})
        body_hash = content_hash({"raw": raw})
        ingested = utc_now()
        with self._db:
            old = self._db.execute(
                "SELECT body_hash FROM receipts WHERE receipt_id=?", (receipt,)
            ).fetchone()
            if old is not None and old["body_hash"] != body_hash:
                raise ValueError("receipt identity reused for different content")
            self._db.execute("INSERT OR IGNORE INTO bodies VALUES (?, ?)", (body_hash, raw))
            self._db.execute(
                """INSERT OR IGNORE INTO receipts
                (receipt_id, session_id, ordinal, body_hash, received_at, ingested_at, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (receipt, session, ordinal, body_hash, _iso(received_at), _iso(ingested), error),
            )
            if frame is not None:
                self._insert_frame(frame, session, receipt, ingested)
                if isinstance(frame, TradeFrame):
                    self._insert_trade(
                        TradePrint(
                            trade_id=frame.trade_id,
                            market_ticker=frame.market_ticker,
                            yes_price=frame.yes_price,
                            quantity=frame.quantity,
                            taker_side=frame.taker_side,
                            executed_at=frame.executed_at,
                            received_at=frame.received_at,
                            is_block_trade=frame.is_block_trade,
                        ),
                        ApiOrigin.LIVE,
                    )
            for index, effect in enumerate(effects):
                self._db.execute(
                    "INSERT OR IGNORE INTO effects VALUES (?, ?, ?)", (receipt, index, effect)
                )
        return receipt

    def save_health(self, payload: str, at: datetime) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO health(observed_at, payload) VALUES (?, ?)", (_iso(at), payload)
            )

    def health_summary(self) -> dict[str, object]:
        latest = self._db.execute(
            "SELECT payload, observed_at FROM health ORDER BY id DESC LIMIT 1"
        ).fetchone()
        open_sessions = self._db.execute(
            "SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL"
        ).fetchone()[0]
        age = (
            None
            if latest is None
            else (utc_now() - datetime.fromisoformat(latest[1])).total_seconds()
        )
        return {
            "health_age_seconds": age,
            "health_report_stale": age is None or age > 30,
            "latest": None if latest is None else json.loads(latest[0]),
            "unclosed_sessions": open_sessions,
            "receipts": self.count("receipts"),
            "frames": self.count("frames"),
            "integrity_effects": self.count("effects"),
        }

    def market_receipt(self, ticker: str, captured_at: datetime) -> str | None:
        row = self._db.execute(
            """SELECT h.receipt_id FROM http_receipts h JOIN bodies b USING(body_hash),
            json_each(CASE WHEN json_valid(b.body) THEN b.body ELSE '{}' END, '$.markets') m
            WHERE json_valid(b.body) AND json_extract(m.value, '$.ticker') = ?
            AND h.received_at <= ? ORDER BY h.rowid DESC LIMIT 1""",
            (ticker, _iso(captured_at)),
        ).fetchone()
        return None if row is None else str(row[0])

    def record_http(self, *, path: str, status: int, body: bytes, received_at: datetime) -> str:
        """Retain every REST receipt, including identical bodies at different retrievals."""
        receipt = str(uuid4())
        digest = content_hash({"body": body.decode("utf-8")})
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO bodies VALUES (?, ?)", (digest, body.decode("utf-8"))
            )
            self._db.execute(
                "INSERT INTO http_receipts VALUES (?, ?, ?, ?, ?, ?)",
                (receipt, path, status, digest, _iso(received_at), _iso(utc_now())),
            )
        return receipt

    def _migrate(self) -> None:
        """v1 -> v2: preserve all old rows; never claim missing legacy session provenance."""
        version = int(self._db.execute("PRAGMA user_version").fetchone()[0])
        if version > 2:
            raise ValueError("recorder schema is newer than this application")
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(frames)")}
        with self._db:
            if "record_id" not in columns:
                self._db.execute("ALTER TABLE frames RENAME TO legacy_frames_v1")
            statements = (
                "CREATE TABLE IF NOT EXISTS recorder_context (key TEXT PRIMARY KEY, value TEXT)",
                """CREATE TABLE IF NOT EXISTS frames (
                arrival_index INTEGER PRIMARY KEY, record_id TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL, channel TEXT NOT NULL, sid INTEGER NOT NULL,
                seq INTEGER, received_at TEXT NOT NULL, ingested_at TEXT,
                receipt_id TEXT, payload_json TEXT NOT NULL)""",
                "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, "
                "started_at TEXT NOT NULL, ended_at TEXT, reason TEXT, mode TEXT)",
                "CREATE TABLE IF NOT EXISTS bodies "
                "(body_hash TEXT PRIMARY KEY, body TEXT NOT NULL)",
                """CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                body_hash TEXT NOT NULL REFERENCES bodies, received_at TEXT NOT NULL,
                ingested_at TEXT NOT NULL, error TEXT, UNIQUE(session_id, ordinal))""",
                "CREATE TABLE IF NOT EXISTS effects (receipt_id TEXT REFERENCES receipts, "
                "effect_index INTEGER, payload TEXT NOT NULL, "
                "PRIMARY KEY(receipt_id,effect_index))",
                "CREATE TABLE IF NOT EXISTS health (id INTEGER PRIMARY KEY, "
                "observed_at TEXT NOT NULL, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS http_receipts (receipt_id TEXT PRIMARY KEY, "
                "path TEXT, status INTEGER, body_hash TEXT REFERENCES bodies, "
                "received_at TEXT, ingested_at TEXT)",
                "CREATE TABLE IF NOT EXISTS market_observations (observation_id TEXT PRIMARY KEY, "
                "market_ticker TEXT, observed_at TEXT, version_hash TEXT, payload TEXT)",
                "CREATE INDEX IF NOT EXISTS frame_time ON frames(received_at, arrival_index)",
            )
            for statement in statements:
                self._db.execute(statement)
            if "mode" not in {r[1] for r in self._db.execute("PRAGMA table_info(sessions)")}:
                self._db.execute("ALTER TABLE sessions ADD COLUMN mode TEXT")
            if "receipt_id" not in {
                r[1] for r in self._db.execute("PRAGMA table_info(market_observations)")
            }:
                self._db.execute("ALTER TABLE market_observations ADD COLUMN receipt_id TEXT")
            if "record_id" not in columns:
                for row in self._db.execute("SELECT * FROM legacy_frames_v1 ORDER BY received_at"):
                    self._db.execute(
                        """INSERT INTO frames(record_id,session_id,channel,sid,seq,received_at,
                        payload_json) VALUES (?, 'legacy-v1-unknown-session', ?, ?, ?, ?, ?)""",
                        (
                            content_hash(dict(row)),
                            row["channel"],
                            row["sid"],
                            row["seq"],
                            row["received_at"],
                            row["payload_json"],
                        ),
                    )
            self._db.execute("PRAGMA user_version=2")

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
        queries.update(
            {
                "receipts": "SELECT COUNT(*) AS n FROM receipts",
                "effects": "SELECT COUNT(*) AS n FROM effects",
                "sessions": "SELECT COUNT(*) AS n FROM sessions",
                "http_receipts": "SELECT COUNT(*) AS n FROM http_receipts",
                "market_observations": "SELECT COUNT(*) AS n FROM market_observations",
            }
        )
        sql = queries.get(table)
        if sql is None:
            raise ValueError(f"unknown table {table}")
        row = self._db.execute(sql).fetchone()
        return int(row["n"])

    def frame_payloads(self) -> tuple[str, ...]:
        rows = self._db.execute("SELECT payload_json FROM frames ORDER BY arrival_index").fetchall()
        return tuple(str(row["payload_json"]) for row in rows)


def _iso(value: datetime) -> str:
    return ensure_utc(value).isoformat()
