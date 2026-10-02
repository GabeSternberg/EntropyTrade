"""Restart-safe snapshot of a ledger. Reloading does not replay fills."""

import json
import sqlite3
from pathlib import Path

from entropytrade.portfolio.ledger import Ledger


class LedgerStore:
    """One SQLite row. The payload is the whole ledger, replaced on each save."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL
            )
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def save(self, ledger: Ledger) -> None:
        payload = json.dumps(ledger.dump(), sort_keys=True)
        self._db.execute(
            """
            INSERT INTO ledger (id, payload) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
            """,
            (payload,),
        )
        self._db.commit()

    def load(self) -> Ledger | None:
        row = self._db.execute("SELECT payload FROM ledger WHERE id = 1").fetchone()
        if row is None:
            return None
        loaded = json.loads(row[0])
        if not isinstance(loaded, dict):
            return None
        return Ledger.load(loaded)
