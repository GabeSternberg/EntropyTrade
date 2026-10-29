"""Controlled wire receipts for acceptance; never empirical market/performance evidence.

Only setup is controlled. Submitted history jobs use the actual listener, discovery,
runner, subprocess worker, reconciliation and research/experiment engine unchanged.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from entropytrade.api.jobs import Jobs
from entropytrade.api.server import workspace_path
from entropytrade.domain.time import SimulatedClock
from entropytrade.families.bitcoin_history import build_history
from entropytrade.families.public import capture_public
from tests.unit.test_bitcoin_history import body
from tests.unit.test_public_families import weather

REPO = Path(__file__).resolve().parents[3]
LABEL = "CONTROLLED SOFTWARE EVIDENCE; no real ingestion or empirical performance"
DATES = (
    datetime(2026, 7, 1, 15, tzinfo=UTC),
    datetime(2026, 8, 30, 15, tzinfo=UTC),
    datetime(2026, 9, 29, 15, tzinfo=UTC),
)
RECEIVED = datetime(2026, 10, 1, 12, tzinfo=UTC)
PARTITION = {"anchor": "2026-07-01", "fit_before": "2026-08-30", "holdout_start": "2026-09-29"}


def market(at: datetime) -> dict[str, Any]:
    raw = body()
    month = {7: "Jul", 8: "Aug", 9: "Sep"}[at.month]
    event = f"KXBTC-26{month.upper()}{at.day:02d}17"
    close = at.replace(hour=21, minute=0)
    raw.update(
        ticker=f"{event}-T100000",
        event_ticker=event,
        title=LABEL,
        open_time=(close - timedelta(days=1)).isoformat(),
        close_time=close.isoformat(),
        latest_expiration_time=(close + timedelta(days=1)).isoformat(),
        rules_primary=(
            "If the simple average of the sixty seconds of CF Benchmarks' "
            "Bitcoin Real-Time Index (BRTI) before 5 PM EDT is above 100000 "
            f"at 5 PM EDT on {month} {at.day}, 2026, then the market resolves to Yes."
        ),
    )
    return raw


def add_capture(jobs: Jobs, at: datetime) -> Path:
    job_id = jobs.create({"idea": LABEL, "family": "bitcoin", "mode": "public"})
    path = jobs.root / "runs" / job_id / "public"
    asyncio.run(
        capture_public(
            path,
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(at),
            kalshi_transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"markets": [market(at)], "cursor": ""})
            ),
            source_transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"price": "100100", "time": at.isoformat()})
            ),
        )
    )
    assert jobs.update(job_id, "fixture", LABEL, status="completed", result={"evidence": LABEL})
    return path


def seed_workspace(workspace: Path) -> dict[str, Any]:
    jobs = Jobs(workspace)
    captures = [add_capture(jobs, at) for at in DATES]
    raw_by_ticker = {market(at)["ticker"]: market(at) for at in DATES}

    def finalized(request: httpx.Request) -> httpx.Response:
        raw = dict(raw_by_ticker[request.url.path.rsplit("/", 1)[-1]])
        raw.update(
            status="finalized",
            result="yes",
            settlement_value_dollars="1.0000",
            settlement_ts=(
                datetime.fromisoformat(raw["close_time"]) + timedelta(minutes=5)
            ).isoformat(),
        )
        return httpx.Response(200, json={"market": raw})

    job_id = jobs.create({"idea": LABEL, "family": "bitcoin", "mode": "history"})
    previous = workspace / "runs" / job_id / "history"
    data = asyncio.run(
        build_history(
            previous,
            captures,
            clock=SimulatedClock(RECEIVED),
            transport=httpx.MockTransport(finalized),
        )
    )
    assert data.provenance["partition"] == PARTITION
    assert data.provenance["reconciliation"]["requested"] == 3
    assert jobs.update(job_id, "fixture", LABEL, status="completed", result={"evidence": LABEL})
    # Discovery must ignore incomplete/failed Bitcoin jobs and the UI's 50-row limit.
    failed = jobs.create({"idea": LABEL, "family": "bitcoin", "mode": "public"})
    jobs.update(failed, "fixture", LABEL, status="failed")
    for _ in range(55):
        unrelated = jobs.create({"idea": LABEL, "family": "weather", "mode": "recorded"})
        jobs.update(unrelated, "fixture", LABEL, status="completed")
    assert not any(row["request"]["family"] == "bitcoin" for row in jobs.history())
    assert jobs.bitcoin_inputs() == (captures, [previous])
    metadata = {
        "evidence": LABEL,
        "partition": PARTITION,
        "received_at": RECEIVED.isoformat(),
        "captures": [str(p) for p in captures],
        "previous": str(previous),
        "protected_event": market(DATES[2])["event_ticker"],
    }
    (workspace / "controlled-fixture.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--add-repeat", action="store_true")
    args = parser.parse_args()
    root = workspace_path(REPO, args.workspace)
    if args.add_repeat:
        add_capture(Jobs(root), DATES[0] + timedelta(minutes=30))
    else:
        if root.exists():
            raise ValueError("Use a new controlled fixture workspace")
        seed_workspace(root)
