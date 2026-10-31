"""Seed actual-browser accounting acceptance. Controlled success stays synthetic."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.tracking.accounting import account_hash, reproduce, verify_export
from entropytrade.tracking.replay import reproduce as shadow_reproduce
from entropytrade.tracking.replay import verify
from entropytrade.tracking.store import TrackingStore
from tests.fee_support import authentic_refusal
from tests.integration.shadow_history_fixture import seed_authentic
from tests.paper_support import paper_inputs
from tests.unit.test_shadow_accounting import outcome
from tests.unit.test_tracking import monitor


def commit(store: TrackingStore, mid: str, inputs: dict[str, Any]) -> None:
    store.control(mid, "pause")
    store.control(mid, "resume")
    claim = store.claim()
    assert claim
    root = store.jobs.root / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    inputs = json.loads(json.dumps(inputs))
    result = {
        "detail": "Paper accounting replay; original observations remain separate",
        "submission_enabled": False,
        "paper_inputs": inputs,
        "paper": reproduce(inputs),
        "decisions": shadow_reproduce(inputs["decision_inputs"]),
    }
    (root / "decision-inputs.json").write_text(json.dumps(inputs["decision_inputs"], indent=2))
    (root / "paper-inputs.json").write_text(json.dumps(inputs, indent=2))
    result["artifacts"] = [
        {"path": p.name, "sha256": file_hash(p), "bytes": p.stat().st_size}
        for p in sorted(root.iterdir())
    ]
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    assert store.finish(mid, claim[1], result)
    assert verify(root)["verified"]
    store.control(mid, "pause")


def seed(workspace: Path, *, authentic: bool) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("fresh workspace required")
    if authentic:
        receipt = seed_authentic(workspace)
        store = TrackingStore(Jobs(workspace))
        mid = receipt["monitor_id"]
        previous = store.get(mid, export=True)
        assert previous
        original = previous["cycles"][0]
        source = workspace / "shadow" / mid / original["id"] / "decision-inputs.json"
        inputs = paper_inputs()
        inputs["decision_inputs"] = json.loads(source.read_text())
        inputs["decision_inputs"]["fee_versions"] = [authentic_refusal().model_dump(mode="json")]
        samples = inputs["decision_inputs"]["data"]["samples"]
        inputs["as_of"] = max(s["decision_time"] for s in samples)
        inputs["event_ids"] = {s["ticker"]: s["event_id"] for s in samples}
        inputs["close_times"] = {s["ticker"]: s["close_time"] for s in samples}
        inputs["execution_books"] = {}
        commit(store, mid, inputs)
    else:
        store = TrackingStore(Jobs(workspace))
        mid = monitor(store)
        state = None
        for index, seconds in enumerate((0, 60, 120, 7200, 8000)):
            inputs = paper_inputs(state, seconds=seconds)
            next(iter(inputs["execution_books"].values()))["asks"][0]["quantity"] = "3.00"
            if index == 1:
                version = FeeVersion.model_validate(inputs["decision_inputs"]["fee_versions"][0])
                assert version.policy
                when = datetime.fromisoformat(inputs["as_of"]) - timedelta(seconds=1)
                early = version.revalidated(policy=version.policy.revalidated(effective_to=when))
                late = version.revalidated(
                    policy=version.policy.revalidated(
                        effective_from=when,
                        schedule=version.policy.schedule.revalidated(quadratic_coefficient=".14"),
                    )
                )
                inputs["decision_inputs"]["fee_versions"] = [
                    v.model_dump(mode="json") for v in (early, late)
                ]
            if index >= 3:
                inputs["outcomes"] = [outcome(inputs)]
                inputs["as_of"] = max(inputs["as_of"], inputs["outcomes"][0]["available_at"])
            commit(store, mid, inputs)
            store = TrackingStore(Jobs(workspace))
            store.recover()
            current = store.get(mid, export=True)
            assert current
            state = current["paper_account"]
    value = store.get(mid, export=True)
    assert value
    verified = verify_export(value)
    return {
        "monitor_id": mid,
        "evidence": "Original authentic receipt replay; no new acquisition"
        if authentic
        else "CONTROLLED SYNTHETIC paper fills, fees and settlement; never empirical",
        "summary": value["paper_summary"],
        "verified": verified,
        "state_hash": account_hash(value["paper_account"]),
        "submission_enabled": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--authentic", action="store_true")
    args = parser.parse_args()
    args.receipt.write_text(json.dumps(seed(args.workspace, authentic=args.authentic), indent=2))
