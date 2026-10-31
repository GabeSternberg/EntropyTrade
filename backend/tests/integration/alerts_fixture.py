"""Offline controlled operator lifecycle for real-browser acceptance; never market evidence."""

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from entropytrade.api.jobs import Jobs, timestamp
from entropytrade.api.workspace import workspace_lease, workspace_path
from entropytrade.domain.time import SimulatedClock, utc_now
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_public_families import WHEN
from tests.unit.test_tracking import monitor
from tests.unit.test_tracking_alerts import complete, fail

REPO = Path(__file__).resolve().parents[3]


def operate(workspace: Path, action: str) -> dict[str, Any]:
    workspace = workspace_path(REPO, workspace)
    if action == "seed" and workspace.exists():
        raise ValueError("fresh acceptance workspace required")
    with workspace_lease(workspace):
        store = TrackingStore(Jobs(workspace))
        if action == "seed":
            clock = SimulatedClock(WHEN)
            with patch("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat()):
                mid = monitor(store)
                # A controlled close is used only to exercise operator escalation.
                complete(
                    store,
                    mid,
                    clock,
                    contracts=[
                        {
                            "ticker": "CONTROLLED",
                            "market": {"close_time": WHEN.isoformat()},
                        }
                    ],
                )
                for _ in range(3):
                    fail(store, mid, clock)
                clock.advance(timedelta(hours=2))
                store.alerts()
                # Acknowledge through the website, never by fixture setup.
                store.control(mid, "pause")
        else:
            mid = store.history()[0]["id"]
            if action == "recover":
                # Health signals and outcome here are explicitly controlled, with current
                # operator clocks. They do not assert actual acquisition or certification.
                clock = SimulatedClock(utc_now())
                store.control(mid, "resume")
                complete(
                    store,
                    mid,
                    clock,
                    outcomes=[
                        {
                            "ticker": "CONTROLLED",
                            "result": "no",
                            "available_at": timestamp(),
                            "basis": "CONTROLLED test reconciliation; no authentic outcome",
                        }
                    ],
                )
                store.control(mid, "pause")
            elif action == "recur":
                # Explicit retries avoid waiting through backoff; this cannot erase the
                # incident's evidence streak, and no future operator clock is invented.
                for _ in range(3):
                    store.control(mid, "pause")
                    store.control(mid, "resume")
                    fail(store, mid, SimulatedClock(utc_now()))
                store.control(mid, "pause")
            else:
                raise ValueError("unknown fixture action")
        value = store.get(mid, export=True)
        assert value
        return {
            "monitor_id": mid,
            "alerts": value["alerts"],
            "submission_enabled": False,
            "limitation": "CONTROLLED operator lifecycle only; no actual acquisition, "
            "authentic outcome, empirical performance or trading activation",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "recover", "recur"])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    args.receipt.write_text(json.dumps(operate(args.workspace, args.action), indent=2))
