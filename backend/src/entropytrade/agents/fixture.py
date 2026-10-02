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
