"""Recheck retained workflow evidence without updating historical receipts or inputs."""

import json
from datetime import UTC, datetime
from pathlib import Path

from entropytrade.data.sources import file_hash
from entropytrade.families.public import forward_data

bundle = Path(__file__).resolve().parent
repo = bundle.parents[2]
retained = bundle.parent / "20261025T163400Z"
receipt = json.loads((retained / "receipt.json").read_text())
rows = []
for run in receipt["runs"]:
    folder = retained / run["label"]
    workspace = repo / run.get("workspace", "data/cache/workbench-browser-review-20261025T163400Z")
    original = workspace / "runs" / run["job_id"]
    review = json.loads((folder / "review.json").read_text())
    assert not review["final_holdout_evaluated"]
    assert all(p["split"] == "validation" for p in review["probabilities"])
    assert review == json.loads((original / "review.json").read_text())
    assert (folder / "report.txt").read_text() == review["report"]
    for artifact in review["artifacts"]:
        path = original / "workflow" / artifact["path"]
        assert file_hash(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["bytes"]
    if review["data_kind"] == "real":
        assert not review["probabilities"] and review["probability_count"] == 0
        assert all(c["forecast_metrics"] is None and not c["scenarios"] for c in review["candidates"])
    else:
        assert review["reasoning"] == "offline_mock"
        control = next(c for c in review["candidates"] if c["candidate_id"] == "negative-control")
        assert len(control["scenarios"]) == 3
        assert all(s["fill_count"] == 0 for s in control["scenarios"])
    row = {"label": run["label"], "job_id": run["job_id"],
           "started_at": run["started_at"], "finished_at": run["finished_at"],
           "protected_projection_verified": True, "browser_verified": False,
           "artifacts_verified": len(review["artifacts"]),
           "review_sha256": file_hash(folder / "review.json"),
           "report_sha256": file_hash(folder / "report.txt")}
    if (folder / "public").exists():
        manifest = json.loads((folder / "public/manifest.json").read_text())
        for name, expected in manifest["checksums"].items():
            assert file_hash(folder / "public" / name) == expected
        data = forward_data(folder / "public")
        assert data.dataset_version == review["lineage"]["dataset"]
        assert data.feature_version == review["lineage"]["feature_version"]
        capture = data.provenance["capture"]
        assert all(f["failed_at"] for f in capture["failures"])
        summary = review["acquisition"]
        assert summary["receipt_count"] == len(capture["receipts"])
        assert summary["listed_contracts"] == capture["listed_contracts"]
        assert summary["observations"] == capture["observations"]
        assert summary["failure_count"] == len(capture["failures"])
        assert summary["headline"] in review["report"]
        assert all(f in review["report"] for f in summary["failure_summaries"])
        assert summary["evaluation_limit"] in review["report"]
        if capture["family"] == "bitcoin":
            assert all(not c["rules_known"] and not c["settlement_sources"]
                       and c["settlement_basis"] == "unresolved" for c in data.provenance["contracts"])
        row["capture"] = {k: summary[k] for k in ("status", "receipt_count", "successful_response_count",
                                                "listed_contracts", "observations", "failure_count")}
    rows.append(row)

lifecycle = json.loads((retained / "http-lifecycle.json").read_text())
active = lifecycle["cancelled_while_active"]
assert active["before"]["status"] == "running"
assert active["before"]["events"][-1]["stage"] == "modeling"
assert active["after"]["status"] == "cancelled"
assert lifecycle["slot_reuse"]["status"] == "completed"
assert all(j["status"] == "interrupted" for j in lifecycle["after_restart"].values())
assert lifecycle["before_restart_exports"] == lifecycle["after_restart_exports"]
for export in lifecycle["after_restart_exports"]:
    folder = retained / export["label"]
    assert not export["browser_download"]
    assert file_hash(folder / "http-review.json") == "sha256:" + export["review_sha256"]
    assert json.loads((folder / "http-review.json").read_text()) == json.loads((folder / "review.json").read_text())
    assert file_hash(folder / "http-report.txt") == "sha256:" + export["report_sha256"]
    assert (folder / "http-report.txt").read_bytes() == (folder / "report.txt").read_bytes()

result = {"recorded_at": datetime.now(UTC).isoformat(), "runs": rows,
          "workflow_artifacts_verified": sum(r["artifacts_verified"] for r in rows),
          "lifecycle_receipt_sha256": file_hash(retained / "http-lifecycle.json"),
          "historical_http_lifecycle_verified": True, "browser_verified": False,
          "limitation": "Revalidation of retained HTTP/worker artifacts, not newly executed browser workflows."}
(bundle / "retained-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
print(f"Verified {len(rows)} retained runs, {result['workflow_artifacts_verified']} workflow artifacts and HTTP lifecycle evidence")
