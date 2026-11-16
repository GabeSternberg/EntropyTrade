"""TEST-ONLY localhost server whose research acquisitions replay recorded public responses.

The replayed bytes are unmodified captures of the public sources for 2026-11-06..12
(``tests/fixtures/research``). The clock is fixed so the research window matches them, and
the quick depth needs five events because only seven days were recorded. The page labels
these jobs as a controlled replay. Production servers never use this module.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from entropytrade.api.server import WorkbenchServer
from entropytrade.domain.time import SimulatedClock
from entropytrade.research import model
from entropytrade.research.service import ResearchService
from tests.research_fixture_support import ReplayTransport

NOW = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="TEST-ONLY research replay server")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    model.MIN_EVENTS["quick"] = 5
    repo = Path(__file__).resolve().parents[3]
    server = WorkbenchServer(repo, args.workspace, port=args.port)
    server.research = ResearchService(
        server.jobs.root,
        repo,
        clock=SimulatedClock(NOW),
        transport=ReplayTransport(),
        transport_label="controlled_replay",
        sleep=lambda _: None,
        lease_fd=server.lock.fileno(),
        poll_seconds=0.1,
    )
    server.research.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
