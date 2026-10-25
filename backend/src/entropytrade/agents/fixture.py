"""Synthetic Philadelphia day used by the research demo. Not a live archive."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic_ai.models.test import TestModel

from entropytrade.agents.deps import ResearchDeps
from entropytrade.agents.outputs import (
    CriticBatch,
    HypothesisDraft,
    QuantBatch,
    ResearchNote,
    SpecJudgement,
)
from entropytrade.domain.enums import (
    ActorKind,
    MarketResult,
    StrategyFamily,
    TimeInForce,
)
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.observations import FeatureObservation, Forecast
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.domain.strategy import (
    ComparisonOp,
    ExecutionPreferences,
    FeatureRequirement,
    MarketUniverse,
    PositionSizing,
    Predicate,
    RuleSet,
    SizingMethod,
    StrategySpec,
)
from entropytrade.weather.baseline import persistence_forecast

TICKER = "KXHIGHPHIL-26OCT02-T89"
STATION = "CLIPHL"
RUN_ID = UUID("00000000-0000-4000-8000-000000000005")
PROMPT = (
    "Research strategies for Philadelphia high-temperature prediction markets. "
    "Explore forecast revisions and identify other potential signals."
)
WHEN = datetime(2026, 10, 2, 16, tzinfo=UTC)
DECISION = datetime(2026, 10, 2, 15, tzinfo=UTC)
LABEL_AT = datetime(2026, 10, 3, 10, tzinfo=UTC)


def philadelphia_window() -> SplitWindow:
    return SplitWindow(
        split=SampleSplit.TRAIN,
        start=datetime(2026, 10, 2, 12, tzinfo=UTC),
        end=datetime(2026, 10, 3, 12, tzinfo=UTC),
    )


def philadelphia_forecast() -> Forecast:
    return persistence_forecast(
        previous_high_f=Decimal(90),
        previous_available_at=datetime(2026, 10, 2, 8, tzinfo=UTC),
        station=STATION,
        valid_on=DECISION.date(),
        run_time=datetime(2026, 10, 2, 8, tzinfo=UTC),
        available_at=datetime(2026, 10, 2, 8, tzinfo=UTC),
    )


def philadelphia_book() -> OrderBook:
    return OrderBook(
        market_ticker=TICKER,
        bids=(OrderBookLevel(price=Decimal("0.3000"), quantity=Decimal("5")),),
        asks=(OrderBookLevel(price=Decimal("0.4000"), quantity=Decimal("5")),),
        received_at=DECISION,
    )


def philadelphia_deps() -> ResearchDeps:
    return ResearchDeps(forecasts=(philadelphia_forecast(),), books=(philadelphia_book(),))


def philadelphia_records() -> tuple[FeatureObservation, ...]:
    forecast = philadelphia_forecast()
    return (
        FeatureObservation(
            source_id="fixture",
            event_time=forecast.run_time,
            available_at=forecast.available_at,
            ingested_at=forecast.ingested_at,
            feature_name="model_probability",
            feature_version="fixture",
            entity_id=TICKER,
            value=Decimal("0.70"),
        ),
        FeatureObservation(
            source_id="persistence",
            event_time=forecast.run_time,
            available_at=forecast.available_at,
            ingested_at=forecast.ingested_at,
            feature_name="forecast_high",
            feature_version="persistence",
            entity_id=TICKER,
            value=forecast.value,
        ),
        FeatureObservation(
            source_id="cli",
            event_time=LABEL_AT,
            available_at=LABEL_AT,
            ingested_at=LABEL_AT,
            feature_name="cli_high",
            feature_version="1",
            entity_id=TICKER,
            value=Decimal(91),
        ),
    )


def philadelphia_settlements() -> tuple[tuple[datetime, str, MarketResult], ...]:
    return ((LABEL_AT, TICKER, MarketResult.YES),)


def _spec(
    strategy_id: str,
    *,
    threshold: str,
    sizing: SizingMethod,
    exit_text: str,
    hypothesis: str,
) -> StrategySpec:
    contracts = Decimal("1.00") if sizing is SizingMethod.FIXED_CONTRACTS else None
    kelly = Decimal("0.25") if sizing is SizingMethod.FRACTIONAL_KELLY else None
    return StrategySpec(
        strategy_id=strategy_id,
        name=strategy_id,
        version=1,
        description="Buy YES when the fixture model probability clears a threshold.",
        hypothesis=hypothesis,
        strategy_family=StrategyFamily.INFORMATIONAL,
        market_universe=MarketUniverse(
            description="Philadelphia daily highs",
            series_tickers=("KXHIGHPHIL",),
        ),
        required_sources=("fixture",),
        features=(
            FeatureRequirement(
                name="model_probability",
                version="fixture",
                description="Scripted probability, not a fitted model.",
            ),
        ),
        entry_rules=RuleSet(
            description="Model probability above a threshold.",
            all_of=(
                Predicate(
                    feature="model_probability",
                    op=ComparisonOp.GT,
                    threshold=Decimal(threshold),
                ),
            ),
        ),
        exit_rules=RuleSet(
            description=exit_text,
            all_of=(
                Predicate(feature="hold_to_settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),
            ),
        ),
        minimum_edge=Decimal("0.03"),
        position_sizing=PositionSizing(
            method=sizing,
            contracts=contracts,
            kelly_fraction=kelly,
            max_contracts=Decimal("1.00"),
        ),
        execution=ExecutionPreferences(time_in_force=TimeInForce.FILL_OR_KILL),
        invalidation_conditions=("The fixture probability is replaced by a live model.",),
        assumptions=("The ask is the fill price and the position is held to settlement.",),
        generated_by=Actor(kind=ActorKind.AGENT, actor_id="quant"),
        generation_run_id=RUN_ID,
        created_at=WHEN,
    )


def demo_specs() -> tuple[StrategySpec, ...]:
    """Two tradable rules, one the critic rejects, and one the interpreter rejects."""
    hypothesis = "A model probability of 0.70 clears a 0.40 ask by more than the minimum edge."
    hold = "Hold to settlement."
    return (
        _spec(
            "phl-probability-055",
            threshold="0.55",
            sizing=SizingMethod.FIXED_CONTRACTS,
            exit_text=hold,
            hypothesis=hypothesis,
        ),
        _spec(
            "phl-probability-090",
            threshold="0.90",
            sizing=SizingMethod.FIXED_CONTRACTS,
            exit_text=hold,
            hypothesis=hypothesis,
        ),
        _spec(
            "phl-copy-rejected",
            threshold="0.55",
            sizing=SizingMethod.FIXED_CONTRACTS,
            exit_text=hold,
            hypothesis=hypothesis,
        ),
        _spec(
            "phl-kelly",
            threshold="0.55",
            sizing=SizingMethod.FRACTIONAL_KELLY,
            exit_text=hold,
            hypothesis=hypothesis,
        ),
    )


def scripted_research_note() -> ResearchNote:
    return ResearchNote(
        summary=(
            "The fixture has a model probability and a persistence high for CLIPHL. "
            "It has no forecast-revision series. The CLI label is not a research input."
        ),
        uncertainties=("One synthetic day is not a sample of Philadelphia weather.",),
        suggested_sources=("fixture",),
    )


def scripted_hypothesis() -> HypothesisDraft:
    return HypothesisDraft(
        statement=(
            "A model probability above 0.55 beats the 0.40 ask by more than 0.03 "
            "on this one Philadelphia fixture day."
        )
    )


def scripted_models() -> tuple[TestModel, TestModel, TestModel, TestModel]:
    specs = demo_specs()
    note = scripted_research_note()
    draft = scripted_hypothesis()
    batch = QuantBatch(specs=specs)
    critique = CriticBatch(
        judgements=(
            SpecJudgement(
                strategy_id="phl-probability-055",
                accept=True,
                reason="Predicates are testable.",
            ),
            SpecJudgement(
                strategy_id="phl-probability-090",
                accept=True,
                reason="A higher threshold is testable.",
            ),
            SpecJudgement(
                strategy_id="phl-copy-rejected",
                accept=False,
                reason="Duplicate of an accepted spec; do not spend a backtest on it.",
            ),
            SpecJudgement(
                strategy_id="phl-kelly",
                accept=True,
                reason="The critic allows it; fixed-contract support is a separate gate.",
            ),
        )
    )
    return (
        TestModel(custom_output_args=note.model_dump(mode="json")),
        TestModel(custom_output_args=draft.model_dump(mode="json")),
        TestModel(custom_output_args=batch.model_dump(mode="json")),
        TestModel(custom_output_args=critique.model_dump(mode="json")),
    )


def operational_models(prompt: str, evidence: object, run_id: str) -> tuple[TestModel, ...]:
    """Explicit mock answers over real coverage, never presented as provider research."""
    from typing import Any, cast

    from entropytrade.agents.outputs import (
        CandidateBatch,
        CandidateVerdict,
        EvidenceNote,
        HypothesisBatch,
        ResearchCandidate,
        ResearchCritique,
        ResearchHypothesis,
    )

    data = cast("Any", evidence)
    citations = tuple(c["evidence_id"] for c in data.calls[:3])
    requested = [m for m in data.markets if m["city"].casefold() in prompt.casefold()]
    family = (requested or data.markets)[0]["series"] if data.markets else "UNKNOWN"
    variables = ["revision_f", "model_disagreement_f", "station_bias_f"]
    if "disagreement" in prompt.lower() and "revision" not in prompt.lower():
        variables = ["model_disagreement_f", "station_bias_f", "revision_f"]
    mechanisms = {
        "revision_f": "Revisions may identify probability changes before market repricing.",
        "model_disagreement_f": "Disagreement may flag unreliable probabilities for filtering.",
        "station_bias_f": "Previously resolved station errors may improve forecast calibration.",
    }
    hypotheses = HypothesisBatch(
        hypotheses=tuple(
            ResearchHypothesis(
                hypothesis_id=f"h{i}",
                mechanism=mechanisms[name],
                market_family=family,
                window="15:00 UTC on target date before market close",
                variables=(name,),
                direction={
                    "revision_f": "upward revisions increase upper-threshold YES probability",
                    "model_disagreement_f": "high disagreement worsens raw probability calibration",
                    "station_bias_f": "positive prior forecast bias raises predicted daily highs",
                }[name],
                test=(
                    "Compare event-weighted validation Brier and log loss against "
                    "predeclared baselines."
                ),
                falsification=(
                    "Reject if there is no reliable out-of-sample improvement across "
                    "independent dates."
                ),
                necessary_evidence=(
                    "Certified vintages and actual source-matched settlement highs",
                ),
                evidence_ids=citations,
            )
            for i, name in enumerate(variables)
        )
    )
    candidates = []
    baseline = demo_specs()[0]
    for i, name in enumerate(variables):
        spec = None
        if i < 2 and data.markets:
            spec = baseline.revalidated(
                strategy_id=f"offline-candidate-{i}",
                name=f"{family} informational {name}",
                description=mechanisms[name],
                market_universe=MarketUniverse(
                    series_tickers=(family,), description="Actual permitted series"
                ),
                hypothesis=mechanisms[name],
                features=(
                    FeatureRequirement(name=name, version="1", description=mechanisms[name]),
                ),
                required_sources=("kalshi", "open-meteo"),
                exit_rules=RuleSet(
                    description="hold to settlement",
                    all_of=(
                        Predicate(feature="settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),
                    ),
                ),
                model_kind="domain_statistical",
                generation_run_id=UUID(run_id),
            )
            # Existing typed probability predicate is rebound to the R2 prediction interface.
            spec = spec.revalidated(
                entry_rules=RuleSet(
                    description="Informational YES entry when modeled probability meets threshold",
                    all_of=(
                        Predicate(
                            feature="model_yes_probability",
                            op=ComparisonOp.GT,
                            threshold=Decimal("0.55"),
                        ),
                        Predicate(
                            feature=name,
                            op=ComparisonOp.LE
                            if name == "model_disagreement_f"
                            else ComparisonOp.GT,
                            threshold=Decimal(5) if name == "model_disagreement_f" else Decimal(0),
                        ),
                    ),
                )
            )
        candidates.append(
            ResearchCandidate(
                candidate_id=f"c{i}",
                hypothesis_id=f"h{i}",
                spec=spec,
                missing_capability="experiment-only proposal; comparison orchestration requires R4"
                if i == 2
                else "",
                required_features=(name,),
                required_sources=("kalshi", "open-meteo"),
                model_family="ridge",
                evidence_ids=citations,
            )
        )
    note = EvidenceNote(
        market_understanding=(
            "Actual listed daily-high contracts exist, but eligible forecast "
            "history and scalar labels are missing."
        ),
        mechanisms=tuple(mechanisms[v] for v in variables),
        limitations=("No empirical forecast model or executable historical depth is available.",),
        evidence_ids=citations,
    )
    critique = ResearchCritique(
        verdicts=tuple(
            CandidateVerdict(
                candidate_id=c.candidate_id,
                accept_for_experiment=True,
                reason=(
                    "Plausible research proposal only; deterministic data and semantics "
                    "checks must gate any experiment."
                ),
                concerns=(
                    "Forecast clocks, scalar labels and independent-event counts are insufficient.",
                ),
            )
            for c in candidates
        )
    )
    return (
        TestModel(custom_output_args=note.model_dump(mode="json"), call_tools=["inspect_evidence"]),
        TestModel(custom_output_args=hypotheses.model_dump(mode="json"), call_tools=[]),
        TestModel(
            custom_output_args=CandidateBatch(candidates=tuple(candidates)).model_dump(mode="json"),
            call_tools=[],
        ),
        TestModel(custom_output_args=critique.model_dump(mode="json"), call_tools=[]),
    )
