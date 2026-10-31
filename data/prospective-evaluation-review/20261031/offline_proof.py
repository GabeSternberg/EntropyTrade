"""Durable offline proof. No sockets, credentials, source acquisition or browser claims."""
import json
from pathlib import Path
from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import snapshot, restore
from entropytrade.data.sources import file_hash
from entropytrade.tracking.prospective import report, csv_report
from entropytrade.tracking.store import TrackingStore
from tests.integration.prospective_fixture import seed

repo = Path.cwd()
evidence = repo / "data/prospective-evaluation-review/20261031/offline"
evidence.mkdir()
results = []
for authentic in (False, True):
    label = "authentic" if authentic else "synthetic"
    root = repo / "data/cache" / ("prospective-proof-20261031-" + label)
    receipt = seed(root, authentic=authentic)
    mid = receipt["monitor_id"]
    value = receipt["report"]
    originals = {p.relative_to(root).as_posix(): file_hash(p)
                 for p in (root / "shadow").rglob("*") if p.is_file()}
    (evidence / (label + "-report.json")).write_text(json.dumps(value, sort_keys=True, indent=2))
    (evidence / (label + "-observations.csv")).write_text(csv_report(value))
    TrackingStore(Jobs(root)).recover()
    assert report(Jobs(root), mid) == value
    archive = repo / "data/cache" / ("prospective-proof-20261031-" + label + ".zip")
    snapshot(repo, root, archive)
    restored = root.with_name(root.name + "-restored")
    restore(repo, archive, restored)
    restored_report = report(Jobs(restored), mid)
    assert restored_report == value
    assert csv_report(restored_report) == csv_report(value)
    checks = {p: {"expected": h, "actual": file_hash(restored / p)} for p, h in originals.items()}
    assert all(r["expected"] == r["actual"] for r in checks.values())
    (evidence / (label + "-source-hashes.json")).write_text(json.dumps(checks, indent=2))
    results.append({"kind": label, "report_hash": value["report_hash"], "counts": value["counts"],
                    "workspace": str(root.relative_to(repo)), "archive": str(archive.relative_to(repo)),
                    "archive_sha256": file_hash(archive), "restored_workspace": str(restored.relative_to(repo)),
                    "cycle_files_unchanged": len(checks), "restart_identical": True,
                    "offline_report_identical": True, "offline_csv_identical": True,
                    "browser_executed": False})
(evidence / "receipt.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
