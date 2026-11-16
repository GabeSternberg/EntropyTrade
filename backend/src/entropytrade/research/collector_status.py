"""Sanitized coverage status for the canonical collector, exported without raw evidence.

Run this on the collector host against a *restored copy* of a verified snapshot, never the
live chain directory. It writes counts of covered dates per evidence kind, entity and source,
plus a content hash. It contains no prices, forecasts, labels, credentials or file bytes, so
it can be copied to a research workspace (``research/collector-status/``) to show how
prospective evidence is accruing. It never satisfies a requirement by itself: raw evidence
must be imported through a verified snapshot first.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from entropytrade.features.registry import scientific_hash
from entropytrade.research.inventory import COLLECTOR_STATUS_SCHEMA, inventory

ORIGINS = {"shadow_monitor", "weather_snapshot", "label_batch"}


def status(workspace: Path, repo: Path, *, now: datetime | None = None) -> dict[str, Any]:
    records, problems = inventory(workspace, repo)
    slices = [
        {
            "kind": r.kind.value,
            "variable": r.variable,
            "family": r.family,
            "source_id": r.source_id,
            "clock": r.clock,
            "fidelity": r.fidelity,
            "coverage": {e: list(d) for e, d in r.coverage.items()},
        }
        for r in records
        if r.origin in ORIGINS and r.data_kind == "authentic"
    ]
    body = {"slices": slices, "problems": problems}
    return {
        "schema": COLLECTOR_STATUS_SCHEMA,
        "generated_at": (now or datetime.now(UTC)).isoformat(),
        "chain_head": scientific_hash(body),
        "source": "canonical_local_chain",
        **body,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export sanitized canonical-collector coverage")
    parser.add_argument("--workspace", type=Path, required=True, help="restored snapshot copy")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    workspace = args.workspace.resolve()
    if workspace.name == "chain" or (workspace / ".chain").exists():
        raise SystemExit("point --workspace at a restored copy, never the live chain")
    if args.output.exists():
        raise SystemExit("refusing to overwrite an existing status file")
    args.output.write_text(json.dumps(status(workspace, repo), indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
