"""A non-weather binary-market adapter fixture; no empirical market claims."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from entropytrade.agents.fixture import demo_specs
from entropytrade.agents.outputs import ResearchCandidate
from entropytrade.domain.enums import FillScenario, MarketResult
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.strategy import ComparisonOp, FeatureRequirement, Predicate, RuleSet
from entropytrade.experiments.data import (
    ContractSample,
    ExperimentData,
    PredictionBundle,
    ProbabilityRecord,
    RecordedPredictions,
)
from entropytrade.experiments.engine import ExperimentConfig
from entropytrade.experiments.synthetic import synthetic_fees
from entropytrade.features.registry import FeatureDefinition, scientific_hash

START = datetime(2025, 1, 1, 12, tzinfo=UTC)
RUN_ID = str(UUID(int=4000))


def nonweather() -> tuple[ExperimentData, RecordedPredictions, dict[str, Any], ExperimentConfig]:
    schema = {
        "features": [
            asdict(
                FeatureDefinition(
                    "mention_count",
                    "1",
                    "count",
                    ("fixture-transcript",),
                    "count available before cutoff",
                )
            )
        ]
    }
    feature_version = scientific_hash(schema)
    records = []
    samples = []
    for index in range(80):
        stamp = START + timedelta(days=index)
        event = f"MENTIONS-E{index}"
        ticker = event + "-YES"
        vector: dict[str, Decimal | None] = {"mention_count": Decimal(index % 3)}
        feature_hash = scientific_hash({k: str(v) for k, v in vector.items()})
        samples.append(
            ContractSample(
                event_id=event,
                ticker=ticker,
                family="MENTIONS",
                target_date=stamp.date(),
                decision_time=stamp,
                close_time=stamp + timedelta(hours=1),
                features_available_at=stamp - timedelta(seconds=1),
                features=vector,
                versions={"mention_count": "1"},
                feature_hash=feature_hash,
                sources=("fixture-transcript",),
                rules_known=True,
                eligible=True,
                outcome=MarketResult.NO if index % 4 == 0 else MarketResult.YES,
                outcome_available_at=stamp + timedelta(hours=2),
                fidelity="order_book",
                book=OrderBook(
                    market_ticker=ticker,
                    received_at=stamp,
                    bids=(OrderBookLevel(price=Decimal(".4"), quantity=Decimal(10)),),
                    asks=(OrderBookLevel(price=Decimal(".5"), quantity=Decimal(10)),),
                ),
            )
        )
        if index >= 50:
            records.append(
                ProbabilityRecord(
                    event_id=event,
                    ticker=ticker,
                    decision_time=stamp,
                    family="provided-frequency",
                    model_hash="sha256:" + "a" * 64,
                    feature_hash=feature_hash,
                    feature_version=feature_version,
                    fitted_before=START + timedelta(days=30),
                    calibrated_before=None,
                    calibration="none",
                    probability_yes=Decimal(".75"),
                    partition="validation" if index < 70 else "holdout",
                    prediction_id=f"prediction-{index}",
                )
            )
    data = ExperimentData(
        dataset_version=scientific_hash({"fixture": "non-weather-v1"}),
        feature_version=feature_version,
        data_kind="synthetic",
        samples=tuple(samples),
        protected_events=frozenset(s.event_id for s in samples[70:]),
        feature_definitions=schema,
        provenance={"source_kinds": ["fixture-transcript"]},
    )
    bundle = PredictionBundle(
        records=tuple(records),
        source_hash=scientific_hash({"fixture": "provided-frequency"}),
        model_metadata={
            "data_kind": "synthetic",
            "split": {"holdout": sorted(data.protected_events)},
        },
    )
    baseline = demo_specs()[0]
    spec = baseline.revalidated(
        strategy_id="mention-strategy",
        hypothesis="Known transcript prefixes may predict a binary mention outcome.",
        generation_run_id=UUID(RUN_ID),
        market_universe=baseline.market_universe.revalidated(
            series_tickers=("MENTIONS",), event_tickers=(), market_tickers=()
        ),
        features=(
            FeatureRequirement(
                name="mention_count", version="1", description="available transcript count"
            ),
        ),
        entry_rules=RuleSet(
            description="model-driven entry",
            all_of=(
                Predicate(
                    feature="model_yes_probability", op=ComparisonOp.GT, threshold=Decimal(".6")
                ),
            ),
        ),
        exit_rules=RuleSet(
            description="hold to settlement",
            all_of=(Predicate(feature="settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),),
        ),
        minimum_edge=Decimal(".03"),
        required_sources=("fixture-transcript",),
    )
    first = ResearchCandidate(
        candidate_id="mentions",
        hypothesis_id="h1",
        spec=spec,
        required_features=("mention_count",),
        required_sources=("fixture-transcript",),
        model_family="provided-frequency",
        evidence_ids=("fixture",),
    )
    second = first.revalidated(
        candidate_id="unsupported",
        hypothesis_id="h2",
        spec=spec.revalidated(hedging_rules="unimplemented pair hedge"),
    )
    research = {
        "run_id": RUN_ID,
        "status": "completed",
        "prompt": "Investigate mentions rather than weather",
        "coverage": {"feature_version": feature_version},
        "candidates": [first.model_dump(mode="json"), second.model_dump(mode="json")],
        "decisions": [
            {"candidate_id": c.candidate_id, "critic": {"accept_for_experiment": True}}
            for c in (first, second)
        ],
    }
    config = ExperimentConfig(
        fee_policy=synthetic_fees(),
        min_events=10,
        min_trades=1,
        bootstrap_samples=100,
        scenarios=(FillScenario.BASE,),
    )
    return data, RecordedPredictions(bundle), research, config
