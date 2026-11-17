"""TEST-ONLY unified frontend listener with one computed C/D paper lineage.

The >50 history rows are explicitly metadata-only pagination/count probes. They do
not contain fitted models, acquired data, balances, fills or scientific approval.
The one actual synthetic model, replay and incoming paper cycle use the accepted
C/D fixture and real accounting code. Production exposes no fixture selector.
"""

import argparse
import json
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from entropytrade.api.server import WorkbenchServer, workspace_path
from entropytrade.domain.time import SimulatedClock
from entropytrade.research.readiness import ResearchReadinessService
from entropytrade.research.service import ResearchService
from entropytrade.research.store import ResearchStore
from tests.research_paper_forward_support import controlled_forward_environment
from tests.research_readiness_support import readiness_fixture


def metadata_history(workspace: Path, job_id: str) -> dict[str, Any]:
    """Insert count probes only, preserving the actual fitted job and its bytes."""
    store = ResearchStore(workspace / "research")
    with store.connect() as db:
        template = dict(db.execute("SELECT * FROM research_jobs WHERE id=?", (job_id,)).fetchone())
        columns = (
            "id",
            "request",
            "fingerprint",
            "family",
            "universe",
            "status",
            "detail",
            "created_at",
            "updated_at",
            "next_run_at",
            "attempts",
            "checkpoint",
            "usage",
            "error",
        )
        for index in range(56):
            probe = dict(template)
            identifier = str(uuid5(NAMESPACE_URL, f"lifecycle-metadata-job:{index}"))
            request = json.loads(probe["request"])
            request["objective"] = (
                f"CONTROLLED metadata-only count probe {index:02d}; no research ran"
            )
            probe.update(
                id=identifier,
                request=json.dumps(request),
                fingerprint=f"CONTROLLED-metadata-count-probe-{index:02d}",
                status="cancelled" if index % 2 else "failed",
                detail="CONTROLLED metadata-only history row; no scientific computation",
                created_at=(
                    datetime.fromisoformat(template["created_at"]) - timedelta(seconds=index + 1)
                ).isoformat(),
                updated_at=(
                    datetime.fromisoformat(template["updated_at"]) - timedelta(seconds=index + 1)
                ).isoformat(),
            )
            db.execute(
                "INSERT INTO research_jobs "
                "(id,request,fingerprint,family,universe,status,detail,created_at,updated_at,"
                "next_run_at,attempts,checkpoint,usage,error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                tuple(probe[column] for column in columns),
            )
            result = {
                "status": "insufficient_evidence",
                "data_kind": "real" if index % 2 else "synthetic",
                "fixture_metadata_only": True,
                "eligibility": {
                    "eligible": False,
                    "reasons": ["CONTROLLED metadata-only count probe; no evidence or fit"],
                },
                "validation": {"status": "not_run"},
                "backtest": {"status": "blocked", "submission_enabled": False},
            }
            db.execute(
                "INSERT INTO research_experiments "
                "(job_id,id,hypothesis_id,status,config,result,error,attempts,"
                "created_at,updated_at) "
                "VALUES (?,?,?,'completed','{}',?,NULL,0,?,?)",
                (
                    identifier,
                    "sha256:" + f"{index + 1:064x}",
                    "CONTROLLED-metadata-only",
                    json.dumps(result),
                    probe["created_at"],
                    probe["updated_at"],
                ),
            )
    # These retained statuses test the separate legacy and course summaries. None
    # is queued, so no worker/network run can be mistaken for a completed result.
    from entropytrade.api.jobs import Jobs

    jobs = Jobs(workspace)
    identifiers: dict[str, str] = {}
    for mode, count in (("recorded", 54), ("cis1990", 3)):
        for index in range(count):
            identifier = str(uuid5(NAMESPACE_URL, f"lifecycle-{mode}:{index}"))
            detail = (
                f"CONTROLLED metadata-only {mode} history {index:02d}; cancelled before execution"
            )
            request = {"idea": detail, "family": "weather", "mode": mode}
            if mode == "cis1990":
                request = {
                    "idea": "Philadelphia weather research",
                    "family": "weather",
                    "mode": mode,
                }
            with jobs.connect() as db:
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,'cancelled',?,?,?,NULL)",
                    (
                        identifier,
                        json.dumps(request),
                        template["created_at"],
                        template["updated_at"],
                        detail,
                    ),
                )
                db.execute(
                    "INSERT INTO events(job_id,at,stage,detail) VALUES (?,?,'cancelled',?)",
                    (identifier, template["created_at"], detail),
                )
            identifiers["course_job_id" if mode == "cis1990" else "legacy_job_id"] = identifier
    return {
        **identifiers,
        "metadata_only_rows": {
            "research_jobs": 56,
            "experiments": 56,
            "legacy_jobs": 54,
            "course_jobs": 3,
        },
        "expected_totals": {
            "research_jobs": 57,
            "experiments": 57,
            "legacy_jobs": 54,
            "course_jobs": 3,
            "monitors": 1,
            "paper_accounts": 1,
        },
        "metadata_warning": (
            "Count probes are stored metadata only; real/synthetic labels do not establish "
            "evidence authenticity or performance."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--scenario", choices=("empty", "unavailable", "mixed"), required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    workspace = workspace_path(repo, args.workspace)
    metadata: dict[str, Any] = {"scenario": args.scenario, "data_kind": "synthetic"}
    clock = None
    if args.scenario == "mixed":
        fixture, facts = readiness_fixture(workspace, cycles=1)
        monitor_id = fixture.tracking.history()[0]["id"]
        metadata.update(metadata_history(workspace, fixture.job_id))
        metadata.update(
            job_id=fixture.job_id,
            experiment_id=fixture.experiment_id,
            monitor_id=monitor_id,
            computed_paper_cycles=1,
        )
        # Advancing controlled time without another cycle creates a genuine stale
        # collection incident through the actual production incident evaluator.
        clock = SimulatedClock(facts.evidence_as_of + timedelta(days=1, minutes=10))
    with ExitStack() as context:
        if clock is not None:
            context.enter_context(controlled_forward_environment(clock))
            context.enter_context(
                patch(
                    "entropytrade.tracking.store.timestamp",
                    side_effect=lambda: clock.now().isoformat(),
                )
            )
        server = WorkbenchServer(repo, workspace, port=args.port)
        if args.scenario == "unavailable":
            # Deliberate optional-store read failure. No worker starts or tries to
            # repair this file; the read-only summary must say unavailable, not 0.
            research = workspace / "research"
            research.mkdir(exist_ok=True)
            (research / "research.sqlite").write_bytes(
                b"CONTROLLED unreadable optional SQLite store\n"
            )
        if clock is not None:
            server.research = ResearchService(
                workspace,
                repo,
                clock=clock,
                lease_fd=server.lock.fileno(),
                poll_seconds=0.1,
                transport_label="controlled_synthetic",
            )
            server.readiness = ResearchReadinessService(
                workspace, server.tracking, server.research, clock=clock, expected_data_kind="real"
            )
            incidents = server.tracking.alerts()
            stale = [
                row
                for row in incidents
                if row["monitor_id"] == metadata["monitor_id"] and row["kind"] == "stale_collection"
            ]
            if not stale:
                raise AssertionError(
                    "Actual controlled stale-collection evaluator produced no incident"
                )
            metadata["alert_id"] = stale[0]["id"]
            server.research.start()
        args.metadata.write_text(json.dumps(metadata, indent=2) + "\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
