"""Read-only cross-check of frozen software acceptance, independent of HTTP assertions.

Run from the repo with .venv/bin/python <this file>. Controlled responses establish
software behavior only. No requests, credentials, orders or Git writes occur here.
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from xml.etree import ElementTree

from entropytrade.families.bitcoin_history import history_data

ROOT = Path(__file__).resolve().parent
PARTITION = {"anchor": "2026-07-01", "fit_before": "2026-08-30", "holdout_start": "2026-09-29"}


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


source = load(ROOT / "source.json")
for relative, expected in source["files"].items():
    assert digest(ROOT.parents[2] / relative) == expected, relative


def verify_review(workspace, job_id, review):
    run = workspace / "runs" / job_id
    assert load(run / "review.json") == review
    with sqlite3.connect(f"file:{workspace / 'jobs.sqlite'}?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
        row = db.execute("SELECT status, result FROM jobs WHERE id=?", (job_id,)).fetchone()
        assert row[0] == "completed" and json.loads(row[1]) == review
    assert review["final_holdout_evaluated"] is False
    assert review["probabilities"] == [] and review["probability_count"] == 0
    for candidate in review["candidates"]:
        assert not candidate["tested"] and candidate["forecast_metrics"] is None
        assert candidate["scenarios"] == []
    for artifact in review["artifacts"]:
        path = (run / "workflow" / artifact["path"]).resolve()
        assert path.is_relative_to((run / "workflow").resolve())
        assert "sha256:" + digest(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["bytes"]
    if review["bitcoin_history"]["capture_count"] == 0:
        return
    assert all(c["status"] == "INSUFFICIENT_DATA" for c in review["candidates"])
    data = history_data(run / "history")
    assert data.provenance["partition"] == PARTITION
    assert len(data.samples) == 3 and data.protected_events == frozenset({"KXBTC-26SEP2917"})
    assert {s.decision_time.isoformat() for s in data.samples} == {
        "2026-07-01T15:00:00+00:00", "2026-08-30T15:00:00+00:00", "2026-09-29T15:00:00+00:00"}
    assert {s.outcome_available_at.isoformat() for s in data.samples} == {"2026-10-01T12:00:00+00:00"}
    reconciliation = data.provenance["reconciliation"]
    assert reconciliation["requested"] == reconciliation["deferred"] == 0
    assert reconciliation["retained_receipts"] == 3 and reconciliation["failures"] == []
    fixture = load(workspace / "controlled-fixture.json")
    prior_id = Path(fixture["previous"]).parent.name
    prior = workspace / "runs" / prior_id / "history/outcomes"
    assert reconciliation["receipts"] == load(prior / "receipts.json")["receipts"]
    for receipt in reconciliation["receipts"]:
        assert (run / "history/outcomes" / receipt["raw_ref"]).read_bytes() == (
            prior / receipt["raw_ref"]).read_bytes()
    # The late receipt must not be backdated into fitting, even with a finalized outcome.
    models = list((run / "workflow/models").rglob("results.json"))
    assert len(models) == 1
    model = load(models[0])
    assert model["metadata"]["fit_events"] == model["metadata"]["fit_date_blocks"] == 0
    assert model["metadata"]["split"] == {
        "fit": ["KXBTC-26JUL0117"], "calibration": [],
        "validation": ["KXBTC-26AUG3017"], "holdout": ["KXBTC-26SEP2917"]}
    assert model["records"] == []
    assert "parameters" not in model["metadata"]
    assert "received before fit cutoff" in json.dumps(model["refusals"])


listener = ROOT / "listener"
receipt = load(listener / "receipt.json")
assert "CONTROLLED SOFTWARE EVIDENCE" in receipt["evidence"]
assert receipt["status"] == "passed" and receipt["empirical_performance"] is False
for prefix, job_id in zip(("first", "second"), receipt["jobs"], strict=True):
    review = load(listener / f"{prefix}-review.json")
    verify_review(listener / "workspace", job_id, review)
    assert (listener / f"{prefix}-report.txt").read_text() == review["report"]

screenshots = downloads = 0
for prefix in ("empty", "controlled"):
    browser = ROOT / "browser"
    receipt = load(browser / f"{prefix}-history-browser-receipt.json")
    assert receipt["status"] == "passed" and receipt["page_errors"] == []
    if prefix == "controlled":
        assert receipt["evidence_kind"] == "CONTROLLED SOFTWARE EVIDENCE"
    for artifact in receipt["downloads"] + receipt["screenshots"]:
        assert digest(browser / artifact["file"]) == artifact["sha256"]
    files = receipt["downloads"]
    assert len(files) == len(receipt["screenshots"]) == 4
    assert files[0]["sha256"] == files[2]["sha256"]
    assert files[1]["sha256"] == files[3]["sha256"]
    job_id = files[0]["file"].split("entropytrade-", 1)[1].removesuffix(".json")
    review = load(browser / files[0]["file"])
    verify_review(browser / f"{prefix}-workspace", job_id, review)
    assert (browser / files[1]["file"]).read_text() == review["report"]
    screenshots += 4
    downloads += 4

pytest = ElementTree.parse(ROOT / "pytest.xml").getroot()
suite = pytest.find("testsuite")
assert int(suite.attrib["tests"]) == 752
assert all(int(suite.attrib[key]) == 0 for key in ("errors", "failures", "skipped"))
stats = load(ROOT / "browser/playwright-results.json")["stats"]
assert stats["expected"] == 2 and stats["unexpected"] == stats["skipped"] == 0
print(json.dumps({"status": "passed", "python_tests": 752, "browser_tests": 2,
                  "listener_jobs": 2, "screenshots": screenshots, "downloads": downloads,
                  "evidence_kind": "CONTROLLED SOFTWARE EVIDENCE",
                  "empirical_performance": False, "v1_complete": False}, indent=2))
