"""Credential-free offline verification of retained shadow decisions; never polls a source."""

import argparse
import json
from pathlib import Path
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import StrategySpec
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.experiments.engine import FeePolicy
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.evaluate import evaluate


def decision_inputs(
    spec: StrategySpec,
    data: ExperimentData,
    bundle: PredictionBundle,
    *,
    held: tuple[dict[str, Any], ...] = (),
    acquisition_complete: bool = True,
    fee: FeePolicy | None = None,
) -> dict[str, Any]:
    samples = tuple(
        s.revalidated(outcome=None, outcome_available_at=None)
        for s in data.samples
        if s.event_id not in data.protected_events
    )
    safe_data = data.revalidated(
        samples=samples, provenance={"purpose": "shadow replay; targets withheld"}
    )
    safe_bundle = bundle.revalidated(
        model_metadata={"original_metadata_hash": scientific_hash(bundle.model_metadata)},
        records=tuple(
            p
            for p in bundle.records
            if p.partition != "holdout" and any(p.usable(s) for s in samples)
        ),
    )
    return {
        "schema": "shadow-inputs-v1",
        "spec": spec.model_dump(mode="json"),
        "data": safe_data.model_dump(mode="json", exclude_computed_fields=True),
        "bundle": safe_bundle.model_dump(mode="json", exclude_computed_fields=True),
        "reservations": held,
        "acquisition_complete": acquisition_complete,
        "fee": fee.model_dump(mode="json", exclude_computed_fields=True) if fee else None,
    }


def reproduce(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    if inputs["schema"] != "shadow-inputs-v1":
        raise ValueError("unknown shadow input schema")
    return evaluate(
        StrategySpec.model_validate(inputs["spec"]),
        ExperimentData.model_validate(inputs["data"]),
        PredictionBundle.model_validate(inputs["bundle"]),
        reservations=tuple(inputs["reservations"]),
        acquisition_complete=inputs["acquisition_complete"],
        fee=FeePolicy.model_validate(inputs["fee"]) if inputs["fee"] else None,
    )


def verify(root: Path) -> dict[str, Any]:
    result = json.loads((root / "result.json").read_text())
    artifacts = result["artifacts"]
    if not any(a["path"] == "decision-inputs.json" for a in artifacts):
        raise ValueError("cycle has no committed replay inputs (failed or interrupted)")
    for artifact in artifacts:
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != artifact["sha256"]:
            raise ValueError("shadow artifact checksum/path mismatch")
    rows = reproduce(json.loads((root / "decision-inputs.json").read_text()))
    if json.loads(json.dumps(rows)) != result["decisions"]:
        raise ValueError("shadow decisions differ from retained result")
    return {
        "verified": True,
        "decision_count": len(rows),
        "submission_enabled": False,
        "limitation": "Reproduces decisions only; does not certify source truth or performance",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cycle", type=Path)
    args = parser.parse_args()
    # JSON output is deliberately a local verification command, never an execution control.
    print(json.dumps(verify(args.cycle), sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
