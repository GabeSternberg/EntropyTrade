"""CONTROLLED synthetic replay proof; no authentic source, return or family claim."""

import json
import shutil
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.experiments.engine import run_experiments
from entropytrade.experiments.fee_replay import verify
from tests.fee_support import controlled_fee
from tests.r4_support import nonweather

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
scratch = REPO / "data/cache/fee-controlled-experiment-20261030"
assert not scratch.exists()
data, provider, research, config = nonweather()
version = controlled_fee()
assert version.policy is not None
boundary = data.samples[50].decision_time + timedelta(microseconds=500000)
earlier = version.revalidated(policy=version.policy.revalidated(effective_to=boundary))
later = version.revalidated(policy=version.policy.revalidated(
    effective_from=boundary,
    schedule=version.policy.schedule.revalidated(quadratic_coefficient=Decimal(".14")),
))
config = config.revalidated(fee_policy=None, fee_versions=(earlier, later))
result = run_experiments(research=research, data=data, provider=provider, config=config,
                         registry_path=scratch / "registry.sqlite", output=scratch / "experiments",
                         tracking=scratch / "mlflow")
artifact = scratch / "experiments" / result["experiment_id"][7:]
target = EVIDENCE / "CONTROLLED-experiment"
shutil.copytree(artifact, target)
verification = verify(target)
(EVIDENCE / "controlled-experiment-verification.json").write_text(json.dumps({
    "evidence": "CONTROLLED synthetic probability/market/fee fixtures; software repeatability only",
    "verification": verification, "experiment_id": result["experiment_id"],
    "scenarios": [{"scenario": s["scenario"], "simulated_fills": s["fill_count"],
                   "simulated_fees": s["fees_paid"],
                   "fee_versions": sorted({a["version"] for a in s["fee_bindings"]})}
                  for s in result["candidates"][0]["scenarios"]],
    "submission_enabled": False,
}, indent=2))
