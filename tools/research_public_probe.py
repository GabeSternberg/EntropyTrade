"""Bounded, anonymous, read-only acquisition through the ordinary research workflow.

No provider call, collector configuration, credentials or order client. A blocked source
is recorded as a failure, never replaced with fixtures. Run in a new cloud workspace.
"""

import argparse
import json
from pathlib import Path

from entropytrade.api.jobs import Jobs
from entropytrade.research.paper import ResearchPaperService
from entropytrade.research.service import ResearchService
from entropytrade.tracking.store import TrackingStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise ValueError("probe output must be new")
    root.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    workspace = root / "workspace"
    jobs = Jobs(workspace)
    tracking = TrackingStore(jobs)
    service = ResearchService(workspace, repo)
    job_id = service.submit(
        {
            "objective": "Study NWS forecast bias in Philadelphia daily-high contract outcomes",
            "family": "weather",
            "universe": ["KXHIGHPHIL"],
            "lookback_days": 30,
            "provider": {"provider": "local_templates"},
            "validation_depth": "quick",
            "acquisition": "approved_sources",
            "budget": {
                "ai_usd": "0",
                "max_http_requests": 64,
                "max_bytes": 16000000,
                "max_runtime_seconds": 300,
                "max_retries": 0,
            },
        }
    )["id"]
    service.run_until_idle()
    report = service.report(job_id)
    assert report is not None
    (root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    detail = service.detail(job_id)
    assert detail is not None
    before = {
        p.relative_to(workspace): p.read_bytes()
        for p in (workspace / "research").rglob("*")
        if p.is_file() and p.suffix != ".sqlite"
    }
    restarted = ResearchService(workspace, repo)
    restarted.recover()
    assert restarted.store.experiments(job_id) == service.store.experiments(job_id)
    assert all((workspace / path).read_bytes() == body for path, body in before.items())
    summary = {
        "schema": "entropytrade-public-lifecycle-probe-v1",
        "data_kind": "authentic public HTTP only; successful acquisition is counted below",
        "provider": "local_templates; no AI provider or credentials used",
        "job_id": job_id,
        "status": detail["status"],
        "detail": detail["detail"],
        "usage": detail["usage"],
        "features": len(detail["features"]),
        "acquisitions": [
            {key: row[key] for key in ("source_id", "status", "detail", "dataset_id")}
            for row in detail["acquisitions"]
        ],
        "paper": ResearchPaperService(workspace, tracking).proposals(job_id),
        "restart_artifact_bytes_equal": True,
        "windows_accessed": False,
        "submission_enabled": False,
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
