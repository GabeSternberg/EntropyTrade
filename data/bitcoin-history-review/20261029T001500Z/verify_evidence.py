"""Cross-check real receipts, deterministic refusals and executed browser downloads.

Run from the repository root with locked dependencies. No acquisition or clock overrides.
The two experiment replays use identical immutable inputs and retain their artifacts.
"""

import json
from datetime import datetime
from pathlib import Path

from entropytrade.data.sources import file_hash
from entropytrade.experiments.engine import ExperimentConfig, run_experiments
from entropytrade.families.bitcoin_history import capture_samples, history_data
from entropytrade.families.bitcoin_models import BitcoinPredictions

ROOT = Path(__file__).resolve().parent
run = ROOT / "real-all-captures"
history = run / "history"
data = history_data(history)
partition = {"anchor": "2026-10-25", "fit_before": "2026-12-24", "holdout_start": "2027-01-23"}
assert data.provenance["partition"] == partition
assert len(data.samples) == 4 and len({s.target_date for s in data.samples}) == 3
assert not data.protected_events
assert data.provenance["capture_count"] == 8
manifest = json.loads((history / "manifest.json").read_text())
all_samples = [s for name in manifest["captures"] for s in capture_samples(history / name)]
for sample in data.samples:
    assert sample.decision_time == min(s.decision_time for s in all_samples if s.event_id == sample.event_id)
    assert sample.features_available_at <= sample.decision_time < sample.close_time
    assert not sample.rules_known and sample.book is None

summary = data.provenance["reconciliation"]
assert summary["requested"] == summary["deferred"] == 0 and not summary["failures"]
assert summary["retained_receipts"] == len(summary["receipts"]) == 4
fresh = json.loads((ROOT / "real-reconciliation/history/outcomes/receipts.json").read_text())
assert fresh["requested"] == 4 and not fresh["failures"]
assert all(r["status"] == 200 for r in fresh["receipts"])
reconciled = []
for receipt in summary["receipts"]:
    assert any(all(receipt[k] == r[k] for k in ("hash", "path", "status", "received_at")) for r in fresh["receipts"])
    path = history / "outcomes" / receipt["raw_ref"]
    assert file_hash(path) == receipt["hash"]
    body = json.loads(path.read_text())["market"]
    sample = next(s for s in data.samples if s.ticker == body["ticker"])
    received = datetime.fromisoformat(receipt["received_at"])
    settled = datetime.fromisoformat(body["settlement_ts"].replace("Z", "+00:00"))
    assert body["status"] == "finalized" and body["result"] == "no"
    assert body["settlement_value_dollars"] == "0.0000" and not body.get("is_provisional", False)
    assert sample.close_time <= settled <= received == sample.outcome_available_at
    assert sample.outcome.value == "no" and body["event_ticker"] == sample.event_id
    assert received > sample.decision_time
    assert sample.close_time == datetime.fromisoformat(body["close_time"].replace("Z", "+00:00"))
    reconciled.append({"ticker": sample.ticker, "decision_time": sample.decision_time.isoformat(),
        "close_time": sample.close_time.isoformat(), "settlement_ts": settled.isoformat(),
        "outcome_available_at": received.isoformat(), "result": "no", "receipt_hash": receipt["hash"]})

readiness = data.provenance["readiness"]
assert not readiness["minimum_evidence_met"]
assert readiness["fit"]["events"] == 4 and readiness["fit"]["dates"] == 3
assert readiness["fit"]["missing_events"] == 36 and readiness["fit"]["missing_dates"] == 17
assert readiness["fit_outcome_classes"] == ["no"]
assert readiness["validation"]["events"] == readiness["validation_labeled"]["events"] == 0
research = json.loads(next((run / "workflow/research").glob("*/run.json")).read_text())
existing = json.loads(next((run / "workflow/experiments").glob("*/results.json")).read_text())
ids = []
for index in (1, 2):
    output = ROOT / f"deterministic-replay-{index}"
    result = run_experiments(
        research=research, data=data, config=ExperimentConfig.model_validate(existing["config"]),
        provider=BitcoinPredictions(data, output / "models"), registry_path=output / "registry.sqlite",
        output=output / "experiments", tracking=output / "mlflow",
    )
    assert json.loads(json.dumps(result)) == existing
    assert not result["final_holdout_evaluated"]
    assert all(c["status"] == "INSUFFICIENT_DATA" and not c["scenarios"] and c["forecast_metrics"] is None for c in result["candidates"])
    ids.append(result["experiment_id"])

browser = ROOT / "browser"
receipt = json.loads((browser / "retained-history-browser-receipt.json").read_text())
assert receipt["status"] == "passed" and receipt["page_errors"] == []
for item in receipt["screenshots"] + receipt["downloads"]:
    assert file_hash(browser / item["file"]) == "sha256:" + item["sha256"]
assert len(receipt["screenshots"]) == len(receipt["downloads"]) == 4
assert [r["sha256"] for r in receipt["downloads"][:2]] == [r["sha256"] for r in receipt["downloads"][2:]]
review = json.loads((browser / receipt["downloads"][0]["file"]).read_text())
assert review["bitcoin_history"]["readiness"] == readiness
assert review["probabilities"] == [] and not review["final_holdout_evaluated"]
workspace = browser / "retained-workspace"
browser_data = history_data(workspace / "runs" / Path(receipt["downloads"][0]["file"]).stem.removeprefix("retained-before-entropytrade-") / "history")
assert browser_data.samples == data.samples
assert browser_data.provenance["partition"] == partition
verification = {"status": "passed", "official_finalized_contracts": reconciled,
    "readiness": readiness, "deterministic_experiment_ids": ids,
    "browser": "executed actual page interactions, downloads and server restart",
    "browser_screenshots": 4, "browser_downloads": 4,
    "empirical_model_evaluation": "blocked: insufficient fitting/validation history and one outcome class",
    "second_family_complete": False, "v1_complete": False}
(ROOT / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
print(json.dumps({"status": "passed", "events": 4, "dates": 3, "deterministic_experiment": ids[0], "complete": False}))
