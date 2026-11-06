"""Durable operational incidents. Operator clocks never become source availability clocks."""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from entropytrade.api.jobs import identifier
from entropytrade.domain.time import ensure_utc

SCHEMA = """
    CREATE TABLE IF NOT EXISTS shadow_alerts (
        id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL, kind TEXT NOT NULL,
        opened_at TEXT NOT NULL, acknowledged_at TEXT, resolved_at TEXT, evidence TEXT NOT NULL);
    CREATE UNIQUE INDEX IF NOT EXISTS one_open_shadow_alert
        ON shadow_alerts(monitor_id, kind) WHERE resolved_at IS NULL;
    CREATE TABLE IF NOT EXISTS shadow_alert_events (
        sequence INTEGER PRIMARY KEY, alert_id TEXT NOT NULL, at TEXT NOT NULL,
        action TEXT NOT NULL, evidence TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS shadow_alert_lifecycle ON shadow_alert_events(alert_id, sequence);
"""
KINDS = {"stale_collection", "repeated_failures", "unresolved_reconciliation"}


RECONCILIATION_GRACE_SECONDS = 3600
RECONCILIATION_RULE = (
    "grace after the exchange's expected expiration captured with the contract, "
    "or after close_time when none was published"
)


def settlement_expected(market: dict[str, Any]) -> tuple[datetime, str]:
    """When the exchange itself said settlement was expected, from the frozen contract record.

    Daily-high weather markets close at local midnight but settle after the next-morning
    official climate report (retained KXHIGHPHIL records: close 05:00Z, expected 19:00Z).
    Measuring the grace from close alone opened a false incident for every such contract.
    Only the expected (not latest) expiration is used, so a late settlement still alerts.
    """
    close = ensure_utc(datetime.fromisoformat(market["close_time"]))
    expected = market.get("expected_expiration_time")
    if expected:
        when = ensure_utc(datetime.fromisoformat(expected))
        if when > close:
            return when, "expected_expiration_time"
    return close, "close_time"


def healthy(cycle: sqlite3.Row) -> bool:
    return bool(
        cycle["status"] == "completed" and cycle["complete"] and cycle["failure_count"] == 0
    )


def refresh(db: sqlite3.Connection, now: str) -> None:
    """Called inside the store transaction, including when no collector is due.

    Acknowledgement does not resolve incidents. Pausing suppresses new freshness alarms,
    but cannot clear existing ones. Recovery requires a healthy committed collection;
    resuming/resetting the backoff counter is not recovery evidence.
    """
    moment = ensure_utc(datetime.fromisoformat(now))
    for monitor in db.execute("SELECT * FROM monitors").fetchall():
        mid = monitor["id"]
        cycles = db.execute(
            "SELECT id, status, finished_at, json_type(result, '$.capture') AS capture_type, "
            "json_extract(result, '$.capture.universe_complete') AS complete, "
            "coalesce(json_array_length(result, '$.capture.failures'), 0) + "
            "coalesce(json_array_length(result, '$.outcome_failures'), 0) + "
            "coalesce(json_array_length(result, '$.execution.failures'), 0) + "
            "coalesce(json_array_length(result, '$.paper_execution.failures'), 0) AS failure_count "
            "FROM shadow_cycles WHERE monitor_id=? ORDER BY sequence DESC",
            (mid,),
        ).fetchall()
        good = next((c for c in cycles if healthy(c)), None)
        last_good = good["finished_at"] if good else monitor["created_at"]
        # Allow three polling intervals plus the existing four-minute worker budget.
        stale_after = max(300, monitor["interval_seconds"] * 3 + 240)
        stale = moment >= datetime.fromisoformat(last_good) + timedelta(seconds=stale_after)
        terminal = [c for c in cycles if c["status"] in {"completed", "failed"}]
        failed = []
        for cycle in terminal:
            if healthy(cycle):
                break
            if cycle["status"] == "failed" or cycle["capture_type"] not in {None, "null"}:
                failed.append(cycle["id"])
        pending = []
        for contract in db.execute(
            "SELECT ticker, market, last_attempt FROM shadow_contracts "
            "WHERE monitor_id=? AND outcome IS NULL ORDER BY ticker",
            (mid,),
        ):
            market = json.loads(contract["market"])["market"]
            expected_at, basis = settlement_expected(market)
            if moment >= expected_at + timedelta(seconds=RECONCILIATION_GRACE_SECONDS):
                pending.append(
                    {
                        "ticker": contract["ticker"],
                        "close_time": market["close_time"],
                        "expected_settlement_at": expected_at.isoformat(),
                        "basis": basis,
                        "last_attempt": contract["last_attempt"],
                    }
                )
        conditions: dict[str, tuple[bool | None, dict[str, Any]]] = {
            "stale_collection": (
                stale if monitor["status"] == "active" or not stale else None,
                {
                    "last_healthy_collection_at": good["finished_at"] if good else None,
                    "baseline_at": last_good,
                    "threshold_seconds": stale_after,
                    "last_healthy_cycle_id": good["id"] if good else None,
                },
            ),
            "repeated_failures": (len(failed) >= 3, {"cycle_ids": failed, "threshold": 3}),
            "unresolved_reconciliation": (
                bool(pending),
                {
                    "contracts": pending,
                    "grace_seconds": RECONCILIATION_GRACE_SECONDS,
                    "rule": RECONCILIATION_RULE,
                },
            ),
        }
        for kind, (active, evidence) in conditions.items():
            if active is None:
                continue
            current = db.execute(
                "SELECT * FROM shadow_alerts WHERE monitor_id=? AND kind=? AND resolved_at IS NULL",
                (mid, kind),
            ).fetchone()
            encoded = json.dumps(evidence, sort_keys=True)
            action = None
            if active and current is None:
                aid = str(uuid4())
                db.execute(
                    "INSERT INTO shadow_alerts VALUES (?, ?, ?, ?, NULL, NULL, ?)",
                    (aid, mid, kind, now, encoded),
                )
                action = "opened"
            elif current is not None:
                aid = current["id"]
                if not active:
                    db.execute("UPDATE shadow_alerts SET resolved_at=? WHERE id=?", (now, aid))
                    action = "resolved"
                elif current["evidence"] != encoded:
                    db.execute("UPDATE shadow_alerts SET evidence=? WHERE id=?", (encoded, aid))
                    action = "evidence_updated"
            if action:
                db.execute(
                    "INSERT INTO shadow_alert_events(alert_id, at, action, evidence) "
                    "VALUES (?, ?, ?, ?)",
                    (aid, now, action, encoded),
                )


def acknowledge(db: sqlite3.Connection, monitor_id: str, alert_id: str, now: str) -> None:
    row = db.execute(
        "SELECT * FROM shadow_alerts WHERE id=? AND monitor_id=?",
        (identifier(alert_id), identifier(monitor_id)),
    ).fetchone()
    if row is None:
        raise ValueError("alert not found for this monitor")
    if row["acknowledged_at"] is not None:
        return
    if row["resolved_at"] is not None:
        raise ValueError("resolved alert cannot be acknowledged")
    db.execute("UPDATE shadow_alerts SET acknowledged_at=? WHERE id=?", (now, alert_id))
    db.execute(
        "INSERT INTO shadow_alert_events(alert_id, at, action, evidence) VALUES (?, ?, ?, ?)",
        (alert_id, now, "acknowledged", row["evidence"]),
    )


def history(db: sqlite3.Connection, monitor_id: str | None = None) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM shadow_alerts WHERE (? IS NULL OR monitor_id=?) ORDER BY opened_at DESC, id",
        (monitor_id, monitor_id),
    ).fetchall()
    return [
        {
            **dict(row),
            "evidence": json.loads(row["evidence"]),
            "events": [
                {**dict(event), "evidence": json.loads(event["evidence"])}
                for event in db.execute(
                    "SELECT sequence, at, action, evidence FROM shadow_alert_events "
                    "WHERE alert_id=? ORDER BY sequence",
                    (row["id"],),
                )
            ],
        }
        for row in rows
    ]


def validate(db: sqlite3.Connection, monitors: set[str]) -> None:
    """Verify the durable lifecycle on offline restore without evaluating today's clock."""
    ids = set()
    open_keys = set()
    for alert in history(db):
        ids.add(identifier(alert["id"]))
        if alert["monitor_id"] not in monitors or alert["kind"] not in KINDS:
            raise ValueError("invalid restored alert reference/kind")
        if alert["resolved_at"] is None:
            key = (alert["monitor_id"], alert["kind"])
            if key in open_keys:
                raise ValueError("duplicate restored open alert")
            open_keys.add(key)
        acknowledged_at = resolved_at = evidence = None
        previous = None
        for index, event in enumerate(alert["events"]):
            at = ensure_utc(datetime.fromisoformat(event["at"]))
            if (previous is not None and at < previous) or resolved_at is not None:
                raise ValueError("invalid restored alert chronology")
            previous = at
            action = event["action"]
            if index == 0:
                if action != "opened" or event["at"] != alert["opened_at"]:
                    raise ValueError("missing restored alert opening")
                evidence = event["evidence"]
            elif action == "acknowledged" and acknowledged_at is None:
                if event["evidence"] != evidence:
                    raise ValueError("invalid restored acknowledgement evidence")
                acknowledged_at = event["at"]
            elif action == "resolved":
                resolved_at = event["at"]
            elif action == "evidence_updated":
                evidence = event["evidence"]
            else:
                raise ValueError("invalid restored alert transition")
        if not alert["events"] or (
            acknowledged_at != alert["acknowledged_at"]
            or resolved_at != alert["resolved_at"]
            or evidence != alert["evidence"]
        ):
            raise ValueError("restored alert disagrees with its lifecycle")
    if any(r[0] not in ids for r in db.execute("SELECT alert_id FROM shadow_alert_events")):
        raise ValueError("orphaned restored alert event")
