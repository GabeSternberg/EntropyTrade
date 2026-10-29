"""Inventory all existing workbench Bitcoin captures; replay only verified real receipts.

Run from the repository root. Existing outputs are refused by the ordinary CLI.
The prior official reconciliation is immutable; this replay performs zero network reads.
"""

import json
import os
import subprocess
from pathlib import Path

from entropytrade.families.bitcoin_history import capture_samples

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
captures = {}
inventory = []
for path in sorted((REPO / "data/workbench-review").rglob("manifest.json")):
    manifest = json.loads(path.read_text())
    if manifest.get("family") != "bitcoin":
        continue
    samples = capture_samples(path.parent)
    captures.setdefault(manifest["dataset_version"], path.parent)
    inventory.append({
        "path": str(path.parent.relative_to(REPO)),
        "dataset_version": manifest["dataset_version"],
        "decision_time": manifest["decision_time"],
        "recognized_samples": len(samples),
        "events": sorted({s.event_id for s in samples}),
        "dates": sorted({s.target_date.isoformat() for s in samples}),
    })
(ROOT / "retained-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
command = [str(REPO / ".venv/bin/entropytrade"), "bitcoin-history"]
for path in captures.values():
    command.extend(["--capture", str(path)])
command.extend([
    "--previous", str(ROOT / "real-reconciliation/history"), "--no-fetch",
    "--output", str(ROOT / "real-all-captures"),
])
with (ROOT / "real-all-captures.log").open("w") as output:
    result = subprocess.run(
        command, cwd=REPO, timeout=90, check=False, stdout=output, stderr=subprocess.STDOUT,
        env={"PATH": os.defpath, "TZ": "UTC", "PYTHONNOUSERSITE": "1",
             "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
    )
raise SystemExit(result.returncode)
