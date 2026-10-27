"""Recheck retained browser evidence without starting a server or mutating Git."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


bundle = Path(__file__).resolve().parent
browser = bundle / "browser-attempt-2"
receipt = json.loads((browser / "browser-receipt.json").read_text())
assert receipt["outcome"] == "passed"
assert [(w["number"], w["outcome"]) for w in receipt["workflows"]] == [
    (1, "passed"), (2, "passed"), (3, "passed"), (4, "passed")
]
assert not receipt["page_errors"]
assert not receipt["acceptance_gaps"]
assert not receipt["browser"]["computer_use"]
assert not receipt["browser"]["personal_chrome"]
assert len(receipt["screenshots"]) == 26
assert len(receipt["downloads"]) == 24
for screen in receipt["screenshots"]:
    assert digest(browser / screen["file"]) == screen["sha256"]

artifacts = 0
completed = [r for r in receipt["runs"] if r["status"] == "completed"]
for run in completed:
    root = browser / "runs" / run["label"]
    review = json.loads((root / "review.json").read_text())
    assert review["final_holdout_evaluated"] is False
    for artifact in review["artifacts"]:
        file = root / "workflow" / artifact["path"]
        assert file.stat().st_size == artifact["bytes"]
        assert "sha256:" + digest(file) == artifact["sha256"]
        artifacts += 1
    downloads = [d for d in receipt["downloads"] if d["job_id"] == run["job_id"]]
    assert len(downloads) == 4
    for download in downloads:
        file = browser / download["file"]
        assert digest(file) == download["sha256"]
        assert file.stat().st_size == download["bytes"]
        if file.suffix == ".json":
            assert json.loads(file.read_bytes()) == review
        else:
            assert file.read_bytes() == review["report"].encode()
    assert len({d["sha256"] for d in downloads if d["file"].endswith(".json")}) == 1
    assert len({d["sha256"] for d in downloads if d["file"].endswith(".txt")}) == 1
    assert run["restart_downloads_identical"]
assert len(completed) == 6
assert artifacts == 63

recorded = json.loads((browser / "runs/recorded-weather/review.json").read_text())
for proposal in recorded["proposals"]:
    comparisons = proposal["spec"]["entry_rules"]["all_of"]
    assert {"feature": "revision_f", "op": "ge", "threshold": "1.25"} in comparisons
    assert {"feature": "hours_to_close", "op": "lt", "threshold": "8"} in comparisons

synthetic = json.loads((browser / "runs/synthetic-weather/review.json").read_text())
assert synthetic["probability_count"] == 192
assert len(synthetic["probabilities"]) == 100
assert all(p["split"] == "validation" for p in synthetic["probabilities"])
negative = next(c for c in synthetic["candidates"] if c["candidate_id"] == "negative-control")
assert len(negative["scenarios"]) == 3
assert all(s["fill_count"] == 0 for s in negative["scenarios"])

for family in ("weather", "bitcoin", "bitcoin-network-denied"):
    root = browser / "runs" / ("public-" + family)
    review = json.loads((root / "review.json").read_text())
    capture = review["public_evidence"]["capture"]
    assert review["probability_count"] == 0
    assert review["coverage"]["scalar_label_events"] == 0
    assert all(c["forecast_metrics"] is None and c["scenarios"] == [] for c in review["candidates"])
    assert capture == json.loads((root / "public/capture.json").read_text())
    for response in capture["receipts"]:
        assert "sha256:" + digest(root / "public" / response["raw_ref"]) == response["hash"]
    if family == "bitcoin":
        assert len(review["public_evidence"]["contracts"]) == 210
        for contract in review["public_evidence"]["contracts"]:
            assert contract["rules_known"] is False
            assert contract["settlement_sources"] == []
            assert contract["settlement_basis"] == "unresolved"
            assert all(m["status"] == "unverified_mention" for m in contract["authority_mentions"])
    if family == "bitcoin-network-denied":
        assert review["acquisition"]["status"] == "incomplete"
        assert capture["receipts"] == []
        assert len(capture["failures"]) == 2
        assert capture["listed_contracts"] == capture["observations"] == 0

visual = json.loads((bundle / "visual-review/receipt.json").read_text())
assert visual["outcome"] == "passed"
for screen in visual["screenshots"]:
    assert digest(bundle / "visual-review" / screen["file"]) == screen["sha256"]

checks = json.loads((bundle / "checks.json").read_text())
assert checks["commit"] == receipt["commit"]
assert checks["tree"] == receipt["tree"]
assert checks["modified_exported_files"] == []
assert len(checks["commands"]) == 6
assert all(c["exit_code"] == 0 and not c["timeout"] for c in checks["commands"])
for command in checks["commands"]:
    assert digest(bundle / command["log"]) == command["sha256"]

with sqlite3.connect(f"file:{browser / 'state/jobs.sqlite'}?mode=ro", uri=True) as db:
    states = dict(db.execute("SELECT id,status FROM jobs"))
assert states == {r["job_id"]: r["status"] for r in receipt["runs"]}

summary = {
    "verified_at_utc": datetime.now(UTC).isoformat(),
    "commit": receipt["commit"], "tree": receipt["tree"],
    "outcome": "passed", "documented_browser_procedures_passed": 4,
    "completed_jobs": len(completed), "cancelled_jobs": 1, "interrupted_jobs": 1,
    "workflow_artifact_hashes_verified": artifacts,
    "full_page_screenshot_hashes_verified": len(receipt["screenshots"]),
    "supplemental_screenshot_hashes_verified": len(visual["screenshots"]),
    "browser_downloads_verified": len(receipt["downloads"]),
    "full_check_commands_passed": len(checks["commands"]),
    "preserved_failed_attempt": "browser-attempt-1",
    "v1_complete": False,
}
(bundle / "verification.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
