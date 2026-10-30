"""Authentic retained weather import for acceptance. Copies original bytes/clocks only."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.api.workspace import workspace_path
from entropytrade.data.sources import file_hash
from entropytrade.families.public import forward_data

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "data/shadow-review/20261029-model-integration/completion/real-cycles"
LABEL = "Authentic retained weather receipt replay; no new acquisition or empirical performance"


def seed_retained(workspace: Path) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("acceptance needs a new workspace")
    captures = sorted(SOURCE.glob("*/*/public"))
    if len(captures) != 2:
        raise ValueError("expected two authentic retained weather cycles")
    jobs = Jobs(workspace)
    evidence = []
    for capture in captures:
        data = forward_data(capture)
        assert data.provenance["capture"]["family"] == "weather"
        job_id = jobs.create({"idea": LABEL, "family": "weather", "mode": "public"})
        destination = workspace / "runs" / job_id / "public"
        shutil.copytree(capture, destination)
        assert forward_data(destination) == data
        jobs.update(job_id, "receipt_import", LABEL, status="completed", result={"evidence": LABEL})
        evidence.append(
            {
                "job_id": job_id,
                "source": str(capture.relative_to(REPO)),
                "manifest_sha256": file_hash(capture / "manifest.json"),
                "dataset_version": data.dataset_version,
                "decision_time": data.provenance["decision_time"],
            }
        )
    return {"evidence": LABEL, "captures": evidence}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    metadata = seed_retained(workspace_path(REPO, args.workspace))
    destination = args.evidence.resolve()
    if not destination.is_relative_to(REPO / "data") or destination.exists():
        raise ValueError("use a new evidence file in repository data")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
