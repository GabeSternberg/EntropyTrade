"""Browser setup: separate CONTROLLED intentions and exact authentic receipt replay."""

import argparse
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.tracking.evaluate import evaluate
from entropytrade.tracking.replay import decision_inputs, reproduce, verify
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations
from tests.fee_support import authentic_refusal, controlled_fee
from tests.integration.shadow_history_fixture import seed_authentic
from tests.unit.test_tracking import ready


def finish(
    store: TrackingStore,
    monitor: str,
    inputs: dict[str, Any],
    result: dict[str, Any],
    original: Path | None = None,
) -> None:
    store.control(monitor, "pause")
    store.control(monitor, "resume")
    claim = store.claim()
    assert claim is not None
    root = store.jobs.root / "shadow" / monitor / claim[1]
    if original:
        shutil.copytree(original, root)
        (root / "original-result.json").write_bytes((root / "result.json").read_bytes())
    else:
        root.mkdir(parents=True)
    (root / "decision-inputs.json").write_text(json.dumps(inputs, sort_keys=True, indent=2))
    result["artifacts"] = [
        {"path": p.relative_to(root).as_posix(), "sha256": file_hash(p), "bytes": p.stat().st_size}
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "result.json"
    ]
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    assert store.finish(monitor, claim[1], result)
    assert verify(root)["verified"]
    store.control(monitor, "pause")


def seed(workspace: Path, *, authentic: bool) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("requires fresh workspace")
    if authentic:
        receipt = seed_authentic(workspace)
        store = TrackingStore(Jobs(workspace))
        versions = (authentic_refusal(),)
        monitor = receipt["monitor_id"]
        previous = store.get(monitor, export=True)
        assert previous is not None
        latest = previous["cycles"][0]
        original = workspace / "shadow" / monitor / latest["id"]
        inputs = json.loads((original / "decision-inputs.json").read_text())
        inputs["fee_versions"] = [v.model_dump(mode="json") for v in versions]
        inputs["series_fees"] = latest["result"]["execution"]["fee_evidence"]
        decisions = reproduce(inputs)
        assert decisions
        assert all(d["status"] == "blocked" and d["intent"] is None for d in decisions)
        result = {
            **latest["result"],
            "decisions": decisions,
            "fee_versions": [v.summary() for v in versions],
            "detail": "Authentic original receipt replay with new fee selection; "
            "no new acquisition",
        }
        finish(store, monitor, inputs, result, original)
    else:
        store = TrackingStore(Jobs(workspace))
        versions = (controlled_fee(),)
        spec, data, bundle, _ = ready()
        spec = spec.revalidated(
            position_sizing=spec.position_sizing.revalidated(
                contracts=Decimal("40"), max_contracts=Decimal("1000")
            )
        )
        sample = data.samples[0]
        assert sample.book is not None
        data = data.revalidated(
            samples=(
                sample.revalidated(
                    book=sample.book.revalidated(
                        asks=(sample.book.asks[0].revalidated(quantity=Decimal("1000")),)
                    )
                ),
            )
        )
        job = store.jobs.create(
            {
                "idea": "CONTROLLED fee-intention software fixture",
                "family": "weather",
                "mode": "recorded",
            }
        )
        store.jobs.update(
            job,
            "completed",
            "CONTROLLED",
            status="completed",
            result={
                "data_kind": "real",
                "proposals": [{"candidate_id": "c0", "spec": spec.model_dump(mode="json")}],
            },
        )
        monitor = store.create({"job_id": job, "candidate_id": "c0", "interval_seconds": 60})
        for index in range(5):
            if index:
                store = TrackingStore(Jobs(workspace))
            previous = store.get(monitor, export=True)
            assert previous is not None
            held = reservations(previous)
            inputs = decision_inputs(spec, data, bundle, held=held, fee_versions=versions)
            decisions = evaluate(spec, data, bundle, reservations=held, fee_versions=versions)
            assert decisions[0]["status"] == ("shadow_eligible" if index < 4 else "risk_rejected")
            finish(
                store,
                monitor,
                inputs,
                {
                    "detail": "CONTROLLED fee-inclusive reservations; no empirical evidence",
                    "submission_enabled": False,
                    "decisions": decisions,
                    "contracts": [],
                    "quotes": [],
                    "outcomes": [],
                    "fee_versions": [v.summary() for v in versions],
                },
            )
    for version in versions:
        FeeEvidenceStore(workspace).put(version)
    return {
        "monitor_id": monitor,
        "evidence": "Authentic original receipts; no new collection"
        if authentic
        else "CONTROLLED synthetic eligible intentions; never empirical",
        "fee_versions": [v.version for v in versions],
        "submission_enabled": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--authentic", action="store_true")
    args = parser.parse_args()
    args.receipt.write_text(json.dumps(seed(args.workspace, authentic=args.authentic), indent=2))
