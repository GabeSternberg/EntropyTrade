"""Import verified real receipts into a NEW acceptance workspace without changing clocks.

This is receipt replay setup, not acquisition through the browser. No HTTP stubs, new
responses, clock overrides or replacement workers are used. The page subsequently runs
the ordinary discovery/reconciliation/model/experiment workflow.
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.api.server import workspace_path
from entropytrade.families.bitcoin_history import history_data

REPO = Path(__file__).resolve().parents[3]
LABEL = "Imported retained real receipts; replay setup, no new source acquisition"


def seed_retained(workspace: Path, snapshot: Path) -> dict[str, Any]:
    source = snapshot.resolve()
    if not source.is_relative_to(REPO / "data"):
        raise ValueError("select a retained snapshot within repository data")
    data = history_data(source)
    manifest = json.loads((source / "manifest.json").read_text())
    if workspace.exists():
        raise ValueError("use a new retained-receipt workspace")
    jobs = Jobs(workspace)
    for relative in manifest["captures"]:
        job_id = jobs.create({"idea": LABEL, "family": "bitcoin", "mode": "public"})
        shutil.copytree(source / relative, workspace / "runs" / job_id / "public")
        jobs.update(job_id, "imported", LABEL, status="completed", result={"evidence": LABEL})
    job_id = jobs.create({"idea": LABEL, "family": "bitcoin", "mode": "history"})
    destination = workspace / "runs" / job_id / "history"
    shutil.copytree(source, destination)
    assert history_data(destination) == data
    jobs.update(job_id, "imported", LABEL, status="completed", result={"evidence": LABEL})
    metadata = {
        "evidence": LABEL,
        "source_snapshot": str(source.relative_to(REPO)),
        "dataset_version": data.dataset_version,
        "partition": data.provenance["partition"],
        "capture_count": data.provenance["capture_count"],
        "retained_events": data.provenance["retained_events"],
        "retained_dates": data.provenance["retained_dates"],
        "protected_events": len(data.protected_events),
        "readiness": data.provenance["readiness"],
        "receipts": data.provenance["reconciliation"]["receipts"],
        "samples": [s.model_dump(mode="json") for s in data.samples],
    }
    (workspace / "retained-inputs.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    seed_retained(workspace_path(REPO, args.workspace), args.snapshot)
