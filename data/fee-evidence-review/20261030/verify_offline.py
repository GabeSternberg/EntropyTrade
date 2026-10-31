"""Reproduce retained browser workspaces offline without source/model requests."""

import json
from pathlib import Path

from entropytrade.api.recovery import restore, snapshot
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.experiments.fee_replay import verify as experiment_verify
from entropytrade.tracking.replay import verify as shadow_verify

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
results = []
for kind in ("controlled", "authentic"):
    source = REPO / "data/cache" / ("fee-browser-final-20261030-" + kind)
    archive = EVIDENCE / (kind + "-offline.zip")
    target = REPO / "data/cache" / ("fee-offline-final-20261030-" + kind)
    snapshot(REPO, source, archive)
    restore(REPO, archive, target)
    assert FeeEvidenceStore(source).snapshot() == FeeEvidenceStore(target).snapshot()
    cycles = [shadow_verify(p.parent) for p in sorted((target / "shadow").glob("*/*/decision-inputs.json"))]
    experiments = [experiment_verify(p.parent) for p in sorted((target / "runs").glob("*/workflow/experiments/*/replay-inputs.json"))]
    assert cycles
    results.append({"kind": kind, "restored_cycles": cycles, "restored_experiments": experiments,
                    "fee_versions_identical": True, "submission_enabled": False})
(EVIDENCE / "offline-verification.json").write_text(json.dumps(results, indent=2))
