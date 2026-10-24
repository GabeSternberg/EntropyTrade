"""Recorder migration, receipts, revision identities, crash durability and source integrity."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from entropytrade.collector.service import ingest_message
from entropytrade.domain.historical import ApiOrigin
from entropytrade.exchange.feed import CollectorFeed
from entropytrade.exchange.frames import LifecycleFrame
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.storage.recorder import Recorder
from tests.exchange.test_feed_recorder import TICKER, WHEN, _delta, _snapshot
from tests.exchange.test_gateway_http import _market_body
from tests.support import utc


def wire(seq: int, *, delta: bool = False, ticker: str = TICKER) -> str:
    msg: dict[str, object] = {"market_ticker": ticker, "market_id": "id-1"}
    if delta:
        msg.update({"side": "yes", "price_dollars": "0.4200", "delta_fp": "-1.00"})
    else:
        msg.update({"yes_dollars_fp": [["0.4200", "10.00"]], "no_dollars_fp": [["0.5600", "8.00"]]})
    return json.dumps(
        {
            "type": "orderbook_delta" if delta else "orderbook_snapshot",
            "sid": 7,
            "seq": seq,
            "msg": msg,
        }
    )


def test_receipts_are_distinct_facts_are_idempotent_and_sessions_do_not_collide(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recording.sqlite"
    store = Recorder(path)
    feed = CollectorFeed()
    session = store.start_session(WHEN)
    feed.note_reconnect(WHEN)
    assert not ingest_message(store, feed, session=session, ordinal=1, raw=wire(1))
    assert not ingest_message(store, feed, session=session, ordinal=2, raw=wire(1))
    assert store.count("receipts") == 2
    assert store.count("frames") == 1
    with pytest.raises(ValueError, match="identity reused"):
        store.record_message(
            session=session, ordinal=1, raw="changed", received_at=WHEN, frame=None
        )
    store.end_session(session, WHEN, "stopped")
    store.close()
    reopened = Recorder(path)
    next_session = reopened.start_session(WHEN)
    assert next_session != session
    reopened.record_message(
        session=next_session, ordinal=1, raw=wire(1), received_at=WHEN, frame=_snapshot(1)
    )
    assert reopened.count("frames") == 2
    lifecycle = LifecycleFrame(sid=9, market_ticker=TICKER, event_type="settled", received_at=WHEN)
    assert reopened.save_frame(lifecycle, session_id=next_session)
    assert not reopened.save_frame(lifecycle, session_id=next_session)
    assert reopened.count("frames") == 3
    reopened.close()


def test_gap_and_conflicting_duplicate_are_persisted_before_resubscription(tmp_path: Path) -> None:
    store = Recorder(tmp_path / "gaps.sqlite")
    session = store.start_session(WHEN)
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    ingest_message(store, feed, session=session, ordinal=1, raw=wire(1))
    assert ingest_message(store, feed, session=session, ordinal=2, raw=wire(3, delta=True))
    assert feed.book(TICKER) is None
    payload = json.loads(wire(3, delta=True))
    payload["msg"]["delta_fp"] = "-2.00"
    assert ingest_message(store, feed, session=session, ordinal=3, raw=json.dumps(payload))
    assert store.count("frames") == 3  # Conflict preserved, never hidden by seq dedup.
    db = sqlite3.connect(store.path)
    effects = " ".join(row[0] for row in db.execute("SELECT payload FROM effects"))
    assert '"expected": 2' in effects
    assert '"kind": "reset"' in effects
    db.close()
    store.close()


def test_v1_migration_preserves_legacy_rows_and_labels_missing_provenance(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE frames(channel TEXT, sid INTEGER, seq INTEGER, received_at TEXT, "
        "payload_json TEXT, PRIMARY KEY(channel,sid,seq))"
    )
    db.execute(
        "INSERT INTO frames VALUES (?, ?, ?, ?, ?)",
        ("orderbook_snapshot", 7, 1, WHEN.isoformat(), _snapshot(1).model_dump_json()),
    )
    db.commit()
    db.close()
    store = Recorder(path)
    assert store.count("frames") == 1
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM legacy_frames_v1").fetchone()[0] == 1
    session, ingestion = db.execute("SELECT session_id, ingested_at FROM frames").fetchone()
    assert session == "legacy-v1-unknown-session"
    assert ingestion is None
    db.close()
    store.close()
    reopened = Recorder(path)
    assert reopened.count("frames") == 1
    reopened.close()


def test_rule_versions_and_repeated_rest_receipts_are_not_conflated(tmp_path: Path) -> None:
    store = Recorder(tmp_path / "metadata.sqlite")
    body = _market_body()
    first = market_from_body(body, captured_at=WHEN, series="KXHIGHPHIL")
    later = first.revalidated(rules=first.rules.revalidated(captured_at=utc(2026, 10, 2, 16)))
    revision = later.revalidated(rules=later.rules.revalidated(rules_secondary="Revised terms"))
    for market in (first, later, revision):
        store.save_market(market, ApiOrigin.LIVE)
        store.record_http(
            path="/markets",
            status=200,
            body=b'{"same": true}',
            received_at=market.rules.captured_at,
        )
    assert store.count("market_observations") == 3
    assert store.count("rule_versions") == 2
    assert store.count("http_receipts") == 3
    store.close()


def test_committed_message_survives_abrupt_process_exit(tmp_path: Path) -> None:
    path = tmp_path / "crash.sqlite"
    code = """
import os,sys
from pathlib import Path
from entropytrade.storage.recorder import Recorder
from entropytrade.domain.time import utc_now
s=Recorder(Path(sys.argv[1])); session=s.start_session(utc_now())
s.record_message(session=session,ordinal=1,raw='{}',received_at=utc_now(),frame=None)
os._exit(17)
"""
    result = subprocess.run([sys.executable, "-c", code, str(path)], check=False)  # noqa: S603 - fixed crash harness
    assert result.returncode == 17
    reopened = Recorder(path)
    assert reopened.health_summary()["unclosed_sessions"] == 1
    assert reopened.count("receipts") == 1
    db = sqlite3.connect(path)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.close()
    reopened.close()


def test_unrelated_market_messages_do_not_refresh_or_resurrect_a_book() -> None:
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    feed.apply(_snapshot(1))
    feed.apply(
        _snapshot(1).revalidated(sid=8, market_ticker="OTHER", received_at=utc(2026, 10, 2, 16))
    )
    book = feed.book(TICKER)
    assert book is not None
    assert book.received_at == WHEN
    assert feed.expire(utc(2026, 10, 2, 16), 60) == (TICKER,)
    assert feed.book(TICKER) is None
    feed.apply(_delta(2))
    assert feed.book(TICKER) is None
    feed.apply(_snapshot(3).revalidated(received_at=utc(2026, 10, 2, 16)))
    assert feed.book(TICKER) is not None


@given(repeats=st.integers(min_value=1, max_value=20))
def test_repeated_delta_does_not_change_displayed_size(repeats: int) -> None:
    feed = CollectorFeed()
    feed.note_reconnect(WHEN)
    feed.apply(_snapshot(1))
    for _ in range(repeats):
        feed.apply(_delta(2, delta="-1.00"))
    book = feed.book(TICKER)
    assert book is not None
    assert book.best_bid is not None
    assert str(book.best_bid.quantity) == "9.00"


def test_malformed_message_receipt_survives_decode_failure(tmp_path: Path) -> None:
    store = Recorder(tmp_path / "malformed.sqlite")
    session = store.start_session(WHEN)
    feed = CollectorFeed()
    with pytest.raises(ConnectionError, match="invalid stream message"):
        ingest_message(store, feed, session=session, ordinal=1, raw="malformed JSON")
    assert store.count("receipts") == 1
    assert store.count("frames") == 0
    db = sqlite3.connect(store.path)
    assert db.execute("SELECT error FROM receipts").fetchone()[0] == "decode_or_subscription_error"
    assert db.execute("SELECT body FROM bodies").fetchone()[0] == "malformed JSON"
    db.close()
    store.close()


def test_demo_and_replay_cannot_be_mixed_with_certified_production_data(tmp_path: Path) -> None:
    from entropytrade.data.recording import recorded_inputs

    store = Recorder(tmp_path / "demo.sqlite")
    store.bind_environment("demo")
    with pytest.raises(ValueError, match="environment mismatch"):
        store.bind_environment("production")
    store.close()
    metadata, states, _ = recorded_inputs(tmp_path / "demo.sqlite")
    assert metadata == []
    assert states == []
