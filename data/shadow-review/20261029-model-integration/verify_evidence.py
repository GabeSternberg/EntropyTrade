"""Read-only verification of retained real cycles and browser bytes. Run from repo root."""

import argparse
import hashlib
import json
from pathlib import Path

from entropytrade.data.sources import file_hash
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.replay import verify

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", type=Path, default=BASE)
parser.add_argument("--browser", default="browser-final")
args = parser.parse_args()
case = args.case.resolve()
browser = case / args.browser
source_inventory = case / "source-sha256.json"
if source_inventory.is_file():
    for name, digest in json.loads(source_inventory.read_text()).items():
        assert file_hash(REPO / name) == digest, name
receipt = json.loads((browser / "shadow-browser-receipt.json").read_text())
assert receipt["status"] == "passed"
assert receipt["page_errors"] == []
for item in receipt["downloads"] + receipt["screenshots"]:
    assert hashlib.sha256((browser / item["file"]).read_bytes()).hexdigest() == item["sha256"]
paused = (browser / "shadow-paused.json").read_bytes()
assert paused == (browser / "shadow-restarted.json").read_bytes()
monitor = json.loads((browser / "shadow-second-cycle.json").read_text())
assert monitor["submission_enabled"] is False
assert monitor["fills"] == [] and monitor["performance"] is None
summaries = []
for cycle in monitor["cycles"]:
    assert cycle["status"] == "completed"
    value = cycle["result"]
    assert scientific_hash(value) == cycle["digest"]
    root = case / "real-cycles" / monitor["id"] / cycle["id"]
    assert json.loads((root / "result.json").read_text()) == value
    assert verify(root)["verified"]
    assert not value["capture"]["failures"] and not value["execution"]["failures"]
    assert value["execution"]["book_count"] == 10
    assert len(value["execution"]["deferred_tickers"]) == 14
    assert len(value["execution"]["fee_evidence"]) == 1
    assert all(not f["certified"] for f in value["execution"]["fee_evidence"])
    for raw in value["capture"]["receipts"]:
        assert file_hash(root / "public" / raw["raw_ref"]) == raw["hash"]
    for raw in value["execution"]["receipts"]:
        assert file_hash(root / raw["raw_ref"]) == raw["sha256"]
    assert all(d["prediction"] is None and d["intent"] is None for d in value["decisions"])
    for name, digest in value["implementation"].items():
        assert file_hash(REPO / name) == digest, name
    summaries.append({"cycle": cycle["sequence"], "decisions": len(value["decisions"]),
                      "books": value["execution"]["book_count"],
                      "source_receipts": len(value["capture"]["receipts"]),
                      "execution_receipts": len(value["execution"]["receipts"])})
print(json.dumps({"verified": True, "real_cycles": summaries, "submission_enabled": False,
                  "limitation": "Authentic collection/lifecycle/replay, not empirical model acceptance"}, indent=2))
