"""TEST-ONLY listener using actual fitted models and retained multi-day paper wires.

Synthetic classification and policy selection exist only in this fixture. Owner credentials
are created separately by test setup using the actual private-file initializer outside
the checkout and workspace. Production CLI setup still requires an interactive TTY.
"""

import argparse
import json
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from entropytrade.api.recovery import restore, snapshot
from entropytrade.api.server import WorkbenchServer, workspace_path
from entropytrade.domain.time import SimulatedClock
from entropytrade.research.readiness import ResearchReadinessService
from tests.integration.research_paper_fixture import restored_clock
from tests.research_paper_forward_support import controlled_forward_environment
from tests.research_readiness_support import readiness_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description="TEST-ONLY readiness browser listener")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=43221)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--monitor-id")
    parser.add_argument("--owner-file", type=Path)
    parser.add_argument("--controlled-readiness", action="store_true")
    parser.add_argument("--cycles", type=int, choices=(1, 23), default=23)
    parser.add_argument("--recover", choices=("snapshot", "restore"))
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    workspace = workspace_path(repo, args.workspace)
    if not args.recover and not args.monitor_id:
        fixture, facts = readiness_fixture(workspace, cycles=args.cycles)
        rows = fixture.tracking.history()
        if len(rows) != 1 or args.metadata is None:
            parser.error("Initial fixture requires metadata and one actual paper deployment")
        args.monitor_id = rows[0]["id"]
        args.metadata.write_text(
            json.dumps(
                {
                    "monitor_id": args.monitor_id,
                    "job_id": fixture.job_id,
                    "experiment_id": fixture.experiment_id,
                    "data_kind": "synthetic",
                    "controlled_readiness": args.controlled_readiness,
                    "cycles": args.cycles,
                    "synthetic_evidence_eligible": facts.eligible,
                }
            )
        )
        clock = SimulatedClock(facts.evidence_as_of + timedelta(seconds=1))
    else:
        clock = restored_clock(workspace)
    with ExitStack() as context:
        context.enter_context(controlled_forward_environment(clock))
        context.enter_context(
            patch(
                "entropytrade.tracking.store.timestamp",
                side_effect=lambda: clock.now().isoformat(),
            )
        )
        if args.recover:
            if args.archive is None:
                parser.error("Recovery requires --archive")
            result = (snapshot if args.recover == "snapshot" else restore)(
                repo, archive=args.archive, workspace=workspace
            )
            sys.stdout.write(json.dumps(result) + "\n")
            return
        server = WorkbenchServer(repo, workspace, port=args.port, owner_file=args.owner_file)
        server.owner.clock = clock
        server.research.transport_label = "controlled_synthetic"
        server.readiness = ResearchReadinessService(
            workspace,
            server.tracking,
            server.research,
            clock=clock,
            expected_data_kind="synthetic" if args.controlled_readiness else "real",
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
