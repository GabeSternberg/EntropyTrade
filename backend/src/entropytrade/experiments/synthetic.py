"""Controlled integration inputs: real R2 fitting over explicitly synthetic source evidence."""

import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import FeeType
from entropytrade.execution.fees import FeeSchedule
from entropytrade.experiments.engine import FeePolicy
from entropytrade.features.pipeline import build_features
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.probability import contract_probability, normal_cdf, strike_from_json
from entropytrade.ml.synthetic import synthetic_dataset


def _cdf(value: float, *, mean: float) -> float:
    return normal_cdf((value - mean) / 4.0)


def prepare_synthetic(root: Path, *, days: int = 240) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    version = scientific_hash(
        {"generator_hash": file_hash(Path(__file__)), "days": days, "seed": 17}
    )
    dataset = root / version.removeprefix("sha256:")
    if not dataset.exists():
        synthetic_dataset(dataset, days=days)
        rows = pq.read_table(dataset / "rows.parquet").to_pylist()
        observations = [
            json.loads(o["payload_json"])
            for o in pq.read_table(dataset / "observations.parquet").to_pylist()
        ]
        latest: dict[tuple[str, str], list[float]] = {}
        for record in observations:
            if record["role"] == "feature" and record["revision_id"].startswith("new"):
                latest.setdefault((record["entity_id"], record["valid_on"]), []).append(
                    float(record["value"])
                )
        for row in rows:
            values = latest[row["station"], row["target_date"]]
            # A predeclared noisy raw-forecast market benchmark; never uses the outcome.
            mean = sum(values) / len(values) + 1.5 * math.sin(
                datetime.fromisoformat(row["decision_time"]).toordinal()
            )
            probability = contract_probability(
                strike_from_json(row["strike_json"]),
                partial(_cdf, mean=mean),
            )
            bid = max(Decimal(".01"), Decimal(str(round(probability - 0.025, 2))))
            ask = min(Decimal(".99"), Decimal(str(round(probability + 0.025, 2))))
            stamp = row["decision_time"]
            book = {
                "market_ticker": row["market_ticker"],
                "received_at": stamp,
                "sequence": 1,
                "bids": [{"price": str(bid), "quantity": "20"}],
                "asks": [{"price": str(ask), "quantity": "20"}],
            }
            row["market_state_json"] = json.dumps(
                {
                    "market_ticker": row["market_ticker"],
                    "event_time": stamp,
                    "available_at": stamp,
                    "received_at": stamp,
                    "fidelity": "order_book",
                    "payload": book,
                    "raw_ref": "synthetic:declared-taker-book",
                    "raw_hash": scientific_hash(book),
                }
            )
            row["execution_fidelity"] = "order_book"
            row["city"] = row["city"].removeprefix("SYNTHETIC ")
            row["dataset_version"] = version
        pq.write_table(pa.Table.from_pylist(rows), dataset / "rows.parquet", compression="zstd")
        manifest = json.loads((dataset / "manifest.json").read_text())
        manifest.update(
            dataset_version=version,
            description="SYNTHETIC R4 fixture; books use forecasts, never outcomes",
        )
        (dataset / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
    manifest = build_features(
        dataset=dataset, archives=[], output=root / "features", data_kind="synthetic"
    )
    return root / "features" / str(manifest["feature_version"]).removeprefix("sha256:")


def synthetic_fees() -> FeePolicy:
    return FeePolicy(
        schedule=FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=Decimal(".07"),
        ),
        version="synthetic-illustrative-v1",
        available_at=datetime(2024, 1, 1, tzinfo=UTC),
        effective_from=datetime(2024, 1, 1, tzinfo=UTC),
        evidence="Synthetic configured schedule; not a historical Kalshi fee claim",
        evidence_hash=scientific_hash({"synthetic_coefficient": ".07"}),
        certified=False,
    )


def integration_models(prompt: str, evidence: Any, run_id: str) -> tuple[Any, ...]:
    """Explicit R3 TestModel integration with a predeclared negative control, never tuned."""
    from entropytrade.agents.fixture import operational_models
    from entropytrade.agents.outputs import (
        CandidateBatch,
        CandidateVerdict,
        HypothesisBatch,
        ResearchCandidate,
        ResearchCritique,
    )

    models = operational_models(prompt, evidence, run_id)
    hypotheses = HypothesisBatch.model_validate(models[1].custom_output_args)
    first = hypotheses.hypotheses[0]
    control = first.revalidated(
        hypothesis_id="negative-control",
        mechanism="An unattainable net edge is a control for execution rejection.",
        test="Run a declared unit-edge hurdle; verify no executable contract can clear it.",
        falsification="Reject any fill that cannot meet the declared net-edge hurdle.",
    )
    hypotheses = hypotheses.revalidated(hypotheses=(*hypotheses.hypotheses, control))
    candidates = CandidateBatch.model_validate(models[2].custom_output_args)
    candidates = candidates.revalidated(
        candidates=tuple(
            c.revalidated(
                required_sources=("synthetic-kalshi", "synthetic-gfs"),
                spec=c.spec.revalidated(required_sources=("synthetic-kalshi", "synthetic-gfs"))
                if c.spec is not None
                else None,
            )
            for c in candidates.candidates
        )
    )
    spec = candidates.candidates[0].spec
    if spec is None:
        raise ValueError("synthetic fixture lacks the declared executable spec")
    candidate = ResearchCandidate(
        candidate_id="negative-control",
        hypothesis_id="negative-control",
        spec=spec.revalidated(
            strategy_id="negative-control",
            minimum_edge=Decimal(1),
            hypothesis=control.mechanism,
            description=control.mechanism,
        ),
        required_features=candidates.candidates[0].required_features,
        required_sources=candidates.candidates[0].required_sources,
        model_family="ridge",
        evidence_ids=candidates.candidates[0].evidence_ids,
    )
    candidates = candidates.revalidated(candidates=(*candidates.candidates, candidate))
    critique = ResearchCritique.model_validate(models[3].custom_output_args)
    critique = critique.revalidated(
        verdicts=(
            *critique.verdicts,
            CandidateVerdict(
                candidate_id="negative-control",
                accept_for_experiment=True,
                reason="This is an explicit software negative control, not a profitability claim.",
                concerns=("The unit net-edge hurdle should produce no fills.",),
            ),
        )
    )
    models[1].custom_output_args = hypotheses.model_dump(mode="json")
    models[2].custom_output_args = candidates.model_dump(mode="json")
    models[3].custom_output_args = critique.model_dump(mode="json")
    return models
