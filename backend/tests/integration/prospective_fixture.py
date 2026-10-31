"""Explicitly SYNTHETIC scored reports and separate unchanged authentic insufficiency."""

import argparse
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import ProbabilityModelRef, StrategySpec
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.prospective import report
from entropytrade.tracking.replay import decision_inputs, reproduce
from entropytrade.tracking.store import TrackingStore
from tests.exchange.test_gateway_http import _market_body
from tests.integration.shadow_history_fixture import seed_authentic
from tests.unit.test_public_families import WHEN
from tests.unit.test_tracking import monitor, ready


def commit(
    store: TrackingStore,
    mid: str,
    inputs: dict[str, Any],
    contracts: list[dict[str, Any]],
    bodies: list[tuple[dict[str, Any], str]],
) -> str:
    # Explicit test-only monitor setup; the production API cannot import synthetic evidence.
    current = store.get(mid, export=True)
    assert current is not None
    if not current["cycles"]:
        spec = StrategySpec.model_validate(inputs["spec"])
        with store.jobs.connect() as db:
            db.execute(
                "UPDATE monitors SET spec=?, spec_hash=? WHERE id=?",
                (spec.model_dump_json(), spec.spec_hash(), mid),
            )
    store.control(mid, "pause")
    store.control(mid, "resume")
    claim = store.claim()
    assert claim
    root = store.jobs.root / "shadow" / mid / claim[1]
    root.mkdir(parents=True)
    (root / "outcomes").mkdir()
    receipts = []
    for i, (body, received) in enumerate(bodies):
        path = root / "outcomes" / f"{i:04d}.json"
        path.write_text(json.dumps({"market": body}, sort_keys=True))
        receipts.append(
            {
                "raw_ref": path.relative_to(root).as_posix(),
                "sha256": file_hash(path),
                "path": f"/trade-api/v2/markets/{body['ticker']}",
                "received_at": received,
                "status": 200,
            }
        )
    summary = {
        "outcomes": [],
        "outcome_attempts": [],
        "outcome_failures": [],
        "outcome_deferred": 0,
        "outcome_receipts": receipts,
    }
    (root / "outcomes/summary.json").write_text(json.dumps(summary, sort_keys=True))
    (root / "decision-inputs.json").write_text(json.dumps(inputs, sort_keys=True))
    result = {
        "detail": "CONTROLLED SYNTHETIC prospective report; no empirical evidence",
        "data_kind": "synthetic",
        "submission_enabled": False,
        "contracts": contracts,
        "decisions": reproduce(inputs),
        **summary,
    }
    result["artifacts"] = [
        {"path": p.relative_to(root).as_posix(), "sha256": file_hash(p), "bytes": p.stat().st_size}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    assert store.finish(mid, claim[1], result)
    store.control(mid, "pause")
    return claim[1]


def controlled_inputs() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    spec, data, bundle, _ = ready()
    base = data.samples[0]
    template = bundle.records[0]
    spec = spec.revalidated(
        market_universe=spec.market_universe.revalidated(series_tickers=("KXHIGHPHIL",)),
        model_ref=ProbabilityModelRef(family=template.family, version=template.model_hash),
    )
    samples, predictions, contracts, bodies = [], [], [], []
    for index in range(14):
        day_index = index if index < 10 else 0 if index == 10 else index - 1
        when = WHEN + timedelta(days=day_index)
        event = f"KXHIGHPHIL-{when:%y%b%d}".upper()
        ticker = event + ("-T90" if index == 10 else "-T89")
        body = {
            **_market_body(),
            "ticker": ticker,
            "event_ticker": event,
            "open_time": (when - timedelta(hours=1)).isoformat(),
            "close_time": (when + timedelta(hours=1)).isoformat(),
            "latest_expiration_time": (when + timedelta(hours=2)).isoformat(),
        }
        market = market_from_body(body, captured_at=when, series="KXHIGHPHIL")
        sample = base.revalidated(
            ticker=ticker,
            event_id=event,
            target_date=when.date(),
            family="KXHIGHPHIL",
            decision_time=when,
            close_time=market.close_time,
            features_available_at=when,
            book=None,
            outcome=None,
            outcome_available_at=None,
        )
        samples.append(sample)
        if index != 12:  # A missing forecast must remain visible even after settlement.
            predictions.append(
                template.revalidated(
                    ticker=ticker,
                    event_id=event,
                    decision_time=when,
                    fitted_before=WHEN - timedelta(days=1),
                    partition="forward",
                    probability_yes=Decimal("0.75"),
                    prediction_id=scientific_hash([ticker, when.isoformat()]),
                )
            )
        contracts.append(
            {
                "ticker": ticker,
                "market": market.model_dump(mode="json", exclude_computed_fields=True),
            }
        )
        bodies.append(body)
    data = data.revalidated(
        samples=tuple(samples), protected_events=frozenset({samples[-1].event_id})
    )
    bundle = bundle.revalidated(
        records=tuple(predictions), model_metadata={"data_kind": "synthetic"}
    )
    return decision_inputs(spec, data, bundle), contracts, bodies


def seed(workspace: Path, *, authentic: bool = False) -> dict[str, Any]:
    if authentic:
        receipt = seed_authentic(workspace)
        mid = receipt["monitor_id"]
        store = TrackingStore(Jobs(workspace))
        value = store.get(mid, export=True)
        assert value is not None
        original = value["cycles"][-1]
        inputs = json.loads(
            (workspace / original["artifact_root"] / "decision-inputs.json").read_text()
        )
        spec = StrategySpec.model_validate(inputs["spec"])
        # Restore the original frozen identity as well as the unmodified receipt files.
        # The generic retained-cycle fixture otherwise uses a different setup proposal.
        with store.jobs.connect() as db:
            db.execute(
                "UPDATE monitors SET spec=?, spec_hash=?, model_binding=? WHERE id=?",
                (
                    spec.model_dump_json(),
                    spec.spec_hash(),
                    json.dumps(original["result"].get("model_binding")),
                    mid,
                ),
            )
    else:
        if workspace.exists():
            raise ValueError("fresh synthetic workspace required")
        store = TrackingStore(Jobs(workspace))
        mid = monitor(store)
        inputs, contracts, bodies = controlled_inputs()
        commit(store, mid, inputs, contracts, [])
        labels = []
        for index, body in enumerate(bodies):
            if index == 11:  # A valid forecast awaits its official result.
                continue
            close = datetime.fromisoformat(body["close_time"])
            final = {
                **body,
                "status": "finalized",
                "result": "yes",
                "settlement_value_dollars": "1.0000",
                "settlement_ts": (close + timedelta(minutes=1)).isoformat(),
            }
            labels.append((final, (close + timedelta(hours=1)).isoformat()))
        commit(store, mid, inputs, contracts, labels)
        corrected = dict(labels[0][0], result="no", settlement_value_dollars="0.0000")
        commit(
            store, mid, inputs, contracts, [(corrected, (WHEN + timedelta(days=15)).isoformat())]
        )
        store = TrackingStore(Jobs(workspace))
        store.recover()
    value = report(Jobs(workspace), mid)
    return {
        "monitor_id": mid,
        "report": value,
        "evidence": "Unchanged authentic retained receipts; insufficient forecasts"
        if authentic
        else "CONTROLLED SYNTHETIC software evidence; never empirical performance",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--authentic", action="store_true")
    args = parser.parse_args()
    args.receipt.write_text(json.dumps(seed(args.workspace, authentic=args.authentic), indent=2))
