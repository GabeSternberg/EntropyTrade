"""Read committed collector evidence without opening it for writes or migration."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from entropytrade.data.schema import MarketEvidence, MarketState
from entropytrade.data.sources import stamp
from entropytrade.domain.ids import content_hash
from entropytrade.domain.market import Market


def recorded_inputs(path: Path) -> tuple[list[MarketEvidence], list[MarketState], str]:
    """Committed receipt order, not exchange event order. Disconnections invalidate all books."""
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    states: list[MarketState] = []
    markets: list[MarketEvidence] = []
    books: dict[str, dict[str, object]] = {}
    evidence: list[str] = []
    try:
        db.execute("BEGIN")  # Stable read snapshot even while a collector writes WAL.
        context = db.execute(
            "SELECT value FROM recorder_context WHERE key='environment'"
        ).fetchone()
        if context is None or context[0] != "production":
            return (
                [],
                [],
                content_hash(
                    {"excluded_recording_environment": None if context is None else context[0]}
                ),
            )
        evidence.append("environment:production")
        for row in db.execute(
            "SELECT * FROM market_observations ORDER BY observed_at, observation_id"
        ):
            evidence.append(json.dumps(dict(row), sort_keys=True))
            payload = json.loads(row["payload"])
            rules_hash = payload["rules"].pop("rules_hash", None)
            market = Market.model_validate(payload)
            if rules_hash is not None and market.rules.rules_hash != rules_hash:
                raise ValueError("recorded market rules hash mismatch")
            raw_ref = f"recording:metadata:{row['observation_id']}"
            raw_hash = content_hash(payload)
            created = None
            if row["receipt_id"] is not None:
                receipt = db.execute(
                    "SELECT h.*, b.body FROM http_receipts h "
                    "JOIN bodies b USING(body_hash) WHERE receipt_id=?",
                    (row["receipt_id"],),
                ).fetchone()
                if receipt is None:
                    raise ValueError("market raw receipt is missing")
                evidence.append(json.dumps(dict(receipt), sort_keys=True))
                raw_ref = f"recording:http:{row['receipt_id']}"
                raw_hash = receipt["body_hash"]
                for item in json.loads(receipt["body"]).get("markets", []):
                    if item.get("ticker") == market.ticker:
                        created = stamp(item.get("created_time"))
            markets.append(
                MarketEvidence(
                    market=market,
                    created_at=created,
                    capture_basis="receipt" if row["receipt_id"] is not None else "unknown",
                    raw_ref=raw_ref,
                    raw_hash=raw_hash,
                )
            )
        for row in db.execute(
            """SELECT r.session_id, r.receipt_id, r.body_hash,
            r.received_at, r.ingested_at, r.error,
            e.payload FROM receipts r JOIN sessions s USING(session_id)
            LEFT JOIN effects e USING(receipt_id)
            WHERE s.mode = 'live'
            ORDER BY r.rowid, e.effect_index"""
        ):
            evidence.append(json.dumps(dict(row), sort_keys=True))
            at = stamp(row["received_at"])
            if at is None:
                raise ValueError("receipt lacks timestamp")
            kind = ""
            value: dict[str, object] = {}
            if row["payload"] is not None:
                payload = json.loads(row["payload"])
                kind, value = payload["kind"], payload["value"]
            if kind == "AppliedBook":
                book = value["book"]
                if not isinstance(book, dict):
                    raise ValueError("invalid normalized book")
                ticker = str(book["market_ticker"])
                books[ticker] = book
                states.append(
                    MarketState(
                        market_ticker=ticker,
                        event_time=at,
                        available_at=at,
                        received_at=at,
                        ingested_at=stamp(row["ingested_at"]),
                        fidelity="order_book",
                        payload=book,
                        raw_ref=f"receipt:{row['receipt_id']}",
                        raw_hash=row["body_hash"],
                    )
                )
            elif row["error"] is not None or kind in ("GapEffect", "StaleBook", "BookInvalidated"):
                if kind == "GapEffect" and value.get("kind") == "duplicate":
                    continue
                states.extend(
                    _invalid(ticker, at, f"receipt:{row['receipt_id']}") for ticker in books
                )
        for row in db.execute("SELECT * FROM sessions WHERE mode='live' ORDER BY started_at"):
            evidence.append(json.dumps(dict(row), sort_keys=True))
            # An unfinished/crashed session is not certified after its last receipt.
            end = stamp(row["ended_at"])
            if end is None:
                last = db.execute(
                    "SELECT MAX(received_at) FROM receipts WHERE session_id=?", (row["session_id"],)
                ).fetchone()[0]
                end = stamp(last)
                if end is not None:
                    end += timedelta(microseconds=1)
            if end is not None:
                states.extend(
                    _invalid(ticker, end, f"session:{row['session_id']}") for ticker in books
                )
    finally:
        db.close()
    return markets, states, content_hash({"committed_recording": evidence})


def _invalid(ticker: str, at: datetime, raw_ref: str) -> MarketState:
    return MarketState(
        market_ticker=ticker,
        event_time=at,
        available_at=at,
        received_at=at,
        fidelity="invalid",
        payload={},
        raw_ref=raw_ref,
        raw_hash=content_hash({"invalidated": raw_ref, "market": ticker}),
    )
