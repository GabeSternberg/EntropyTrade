"""TEST-ONLY research paper listener with actual fitting, collection and accounting.

Controlled source clocks, synthetic classification and HTTP transports exist only here
and in test helpers. Production has no flag or endpoint selecting these fixtures.
"""

import argparse
import json
import sqlite3
import sys
import threading
import traceback
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from entropytrade.api.recovery import restore, snapshot
from entropytrade.api.server import WorkbenchServer, workspace_path
from entropytrade.domain.time import SimulatedClock
from entropytrade.research.paper import ResearchPaperService
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
)
from tests.research_paper_support import paper_fixture


def restored_clock(workspace: Path) -> SimulatedClock:
    """Continue recorded test time; restarting never backdates existing observations."""
    values = [MODEL_NOW + timedelta(minutes=1)]
    database = workspace / "jobs.sqlite"
    if database.exists():
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            for query in (
                "SELECT max(created_at) FROM monitors",
                "SELECT max(at) FROM shadow_events",
                "SELECT max(finished_at) FROM shadow_cycles",
            ):
                row = db.execute(query).fetchone()
                if row and row[0]:
                    values.append(datetime.fromisoformat(row[0]))
    return SimulatedClock(max(values))


def main() -> None:
    parser = argparse.ArgumentParser(description="TEST-ONLY research paper listener")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=43215)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--job-id")
    parser.add_argument("--controlled-promotion", action="store_true")
    parser.add_argument("--recover", choices=("snapshot", "restore"))
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    workspace = workspace_path(repo, args.workspace)
    if not args.recover and not args.job_id:
        seeded = paper_fixture(workspace)
        if args.metadata is None:
            parser.error("--metadata is required for initial setup")
        args.metadata.write_text(
            json.dumps(
                {
                    "job_id": seeded.job_id,
                    "experiment_id": seeded.experiment_id,
                    "data_kind": "synthetic",
                    "controlled_promotion": args.controlled_promotion,
                }
            )
        )
    clock = restored_clock(workspace)
    with ExitStack() as context:
        if args.controlled_promotion:
            context.enter_context(controlled_forward_environment(clock))
            context.enter_context(
                patch(
                    "entropytrade.tracking.store.timestamp",
                    side_effect=lambda: clock.now().isoformat(),
                )
            )
        if args.recover:
            if args.archive is None:
                parser.error("--archive is required for recovery")
            result = (snapshot if args.recover == "snapshot" else restore)(
                repo, archive=args.archive, workspace=workspace
            )
            sys.stdout.write(json.dumps(result) + "\n")
            return
        server = WorkbenchServer(repo, workspace, port=args.port)
        server.research.transport_label = "controlled_synthetic"
        if args.controlled_promotion:
            server.paper = ResearchPaperService(
                server.jobs.root,
                server.tracking,
                clock=clock,
                expected_data_kind="synthetic",
            )
        stop = threading.Event()

        def incoming() -> None:
            """One actual incoming-data cycle per newly deployed controlled strategy."""
            attempted: set[str] = set()
            while not stop.wait(0.05):
                for row in server.tracking.history():
                    if (
                        row["source_kind"] != "autonomous_research"
                        or row["status"] != "active"
                        or row["id"] in attempted
                    ):
                        continue
                    monitor = server.tracking.get(row["id"])
                    if monitor is None or monitor["cycle_count"]:
                        continue
                    attempted.add(row["id"])
                    try:
                        commit_controlled_cycle(
                            SimpleNamespace(jobs=server.jobs, tracking=server.tracking),
                            max(clock.now(), MODEL_NOW.replace(hour=23, minute=0, second=5)),
                            clock=clock,
                        )
                    except (ValueError, OSError, KeyError, TypeError):
                        # No fabricated cycle/fill replaces failure; original partial bytes
                        # and the traceback remain available to the acceptance procedure.
                        traceback.print_exc()

        worker = threading.Thread(target=incoming, daemon=True)
        if args.controlled_promotion:
            worker.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            if worker.ident is not None:
                worker.join(timeout=10)
            server.server_close()


if __name__ == "__main__":
    main()
