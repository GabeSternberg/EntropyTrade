"""Strategy specs, point-in-time selection and run records."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from entropytrade.domain.enums import (
    ActorKind,
    ExecutionFidelity,
    FeeType,
    FillScenario,
    StrategyFamily,
    TimeInForce,
)
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.lifecycle import Actor, LifecycleState
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.observations import FeatureObservation, Forecast, select_as_of
from entropytrade.domain.runs import (
    AgentResearchRun,
    BacktestRun,
    CapitalEnvelope,
    Deployment,
    DeploymentStatus,
    ResearchReport,
    ResearchRunStatus,
    SampleSplit,
    SplitWindow,
)
from entropytrade.domain.strategy import (
    MAX_KELLY_FRACTION,
    CalibrationMethod,
    ComparisonOp,
    ExecutionPreferences,
    FeatureRequirement,
    MarketUniverse,
    ModelKind,
    PositionSizing,
    Predicate,
    RuleSet,
    SizingMethod,
    StrategySpec,
    StrategyVersion,
)
from tests.support import utc


def _rules(feature: str = "net_edge") -> RuleSet:
    return RuleSet(
        description=feature,
        all_of=(Predicate(feature=feature, op=ComparisonOp.GT, threshold=Decimal("0.02")),),
    )


def _spec(**changes: object) -> StrategySpec:
    base: dict[str, object] = {
        "strategy_id": "phl-revision",
        "name": "Philadelphia forecast revisions",
        "version": 1,
        "description": "Trade daily-high brackets after a large forecast revision.",
        "hypothesis": (
            "Upward revisions greater than 2F in the last 12 hours are followed by "
            "underpriced upper brackets."
        ),
        "strategy_family": StrategyFamily.INFORMATIONAL,
        "market_universe": MarketUniverse(
            description="Philadelphia daily highs",
            series_tickers=("KXHIGHPHIL",),
        ),
        "required_sources": ("kalshi", "open-meteo"),
        "features": (
            FeatureRequirement(name="forecast_revision_f", version="v1", description="Last 12h"),
        ),
        "model_kind": ModelKind.DOMAIN_STATISTICAL,
        "entry_rules": _rules(),
        "exit_rules": _rules("hours_to_close"),
        "minimum_edge": Decimal("0.03"),
        "position_sizing": PositionSizing(
            method=SizingMethod.FRACTIONAL_KELLY,
            kelly_fraction=Decimal("0.25"),
            max_contracts=Decimal("10"),
        ),
        "maximum_holding_period_seconds": 36 * 3600,
        "invalidation_conditions": ("Settlement source text changes.",),
        "assumptions": ("Brackets in one event are mutually exclusive.",),
        "generated_by": Actor(kind=ActorKind.HUMAN, actor_id="gabe"),
        "created_at": utc(2026, 10, 2),
    }
    base.update(changes)
    return StrategySpec.model_validate(base)


def _observation(hour: int, value: str, *, revision: str | None = None) -> FeatureObservation:
    moment = utc(2026, 10, 1, hour)
    return FeatureObservation(
        source_id="open-meteo",
        revision_id=revision,
        event_time=moment,
        published_at=moment,
        available_at=moment,
        ingested_at=moment + timedelta(seconds=5),
        feature_name="forecast_high_f",
        feature_version="v1",
        entity_id="CLIPHL",
        value=Decimal(value),
    )


def test_spec_hash_is_stable_and_versions_need_lineage() -> None:
    spec = _spec()
    assert spec.spec_hash() == _spec().spec_hash()
    assert spec.spec_hash() != _spec(hypothesis="A different mechanism.").spec_hash()
    assert spec.maximum_holding_period == timedelta(hours=36)
    version = StrategyVersion.from_spec(spec)
    assert version.version == 1
    with pytest.raises(ValueError, match="parent"):
        StrategyVersion.from_spec(_spec(version=2))
    child = StrategyVersion.from_spec(_spec(version=2), parent_spec_hash=version.spec_hash)
    assert child.parent_spec_hash == version.spec_hash


def test_spec_cannot_raise_risk_or_use_full_kelly() -> None:
    with pytest.raises(ValueError, match="none"):
        _spec(risk_overrides_allowed="raise_limits")
    with pytest.raises(ValueError, match="kelly"):
        _spec(
            position_sizing=PositionSizing(
                method=SizingMethod.FRACTIONAL_KELLY,
                kelly_fraction=MAX_KELLY_FRACTION + Decimal("0.1"),
                max_contracts=Decimal(1),
            )
        )
    with pytest.raises(ValueError, match="positive"):
        _spec(minimum_edge=Decimal(0))
    with pytest.raises(ValueError, match="research run"):
        _spec(generated_by=Actor(kind=ActorKind.AGENT, actor_id="quant"))
    with pytest.raises(ValueError, match="ticker"):
        MarketUniverse(description="everything")
    with pytest.raises(ValueError, match="calibration"):
        _spec(model_kind=ModelKind.NONE, calibration=CalibrationMethod.PLATT)


def test_execution_preferences_reject_crossing_post_only() -> None:
    with pytest.raises(ValueError, match="post-only"):
        ExecutionPreferences(post_only=True, time_in_force=TimeInForce.FILL_OR_KILL)


def test_select_as_of_hides_the_future_and_keeps_the_latest_known_revision() -> None:
    early = _observation(8, "70")
    revised = _observation(9, "74", revision="r2")
    future = _observation(18, "80")
    decision = utc(2026, 10, 1, 12)
    chosen = select_as_of([future, early, revised], decision, key=lambda row: row.entity_id)
    assert chosen["CLIPHL"] is revised
    # A record that arrives after the decision cannot change what the decision saw.
    assert select_as_of([early, revised], decision, key=lambda row: row.entity_id) == chosen
    with pytest.raises(ValueError, match="naive"):
        select_as_of([early], datetime(2026, 10, 1, 12, 0), key=lambda row: row.entity_id)  # noqa: DTZ001


def test_a_revision_after_the_decision_is_not_visible() -> None:
    early = _observation(8, "70")
    revised = early.revalidated(
        value=Decimal("74"),
        revision_id="r2",
        revised_at=utc(2026, 10, 1, 9),
    )
    leaked = early.revalidated(
        value=Decimal("80"),
        revision_id="r3",
        revised_at=utc(2026, 10, 1, 18),
    )
    decision = utc(2026, 10, 1, 12)
    chosen = select_as_of([leaked, early, revised], decision, key=lambda row: row.entity_id)
    assert chosen["CLIPHL"] is revised
    assert select_as_of([early, revised], decision, key=lambda row: row.entity_id) == chosen
    assert select_as_of([leaked], decision, key=lambda row: row.entity_id) == {}


def test_forecast_cannot_be_available_before_it_was_run() -> None:
    moment = utc(2026, 10, 1, 12)
    with pytest.raises(ValueError, match="run time"):
        Forecast(
            source_id="open-meteo",
            event_time=moment,
            available_at=moment,
            ingested_at=moment,
            provider="open-meteo",
            model="gfs",
            run_time=moment + timedelta(hours=1),
            location_id="CLIPHL",
            variable="temperature_2m_max",
            valid_from=utc(2026, 10, 2),
            valid_to=utc(2026, 10, 3),
            value=Decimal(75),
            unit="F",
        )


def test_point_in_time_stamps_stay_ordered() -> None:
    moment = utc(2026, 10, 1, 12)
    with pytest.raises(ValueError, match="available_at"):
        _observation(8, "70").revalidated(published_at=moment + timedelta(days=1))


def test_backtest_holdout_cannot_overlap_training() -> None:
    start, mid, end = utc(2026, 1, 1), utc(2026, 4, 1), utc(2026, 7, 1)
    fee = FeeModelRef(
        version="kalshi-quadratic-2026-08",
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        effective_from=utc(2026, 1, 1),
    )
    spec = _spec()
    common = {
        "strategy_id": spec.strategy_id,
        "strategy_version": spec.version,
        "strategy_spec_hash": spec.spec_hash(),
        "git_sha": "abcdef1",
        "config_hash": spec.spec_hash(),
        "dataset_manifest_hash": spec.spec_hash(),
        "feature_version": "features-v1",
        "fee_model": fee,
        "execution_model_version": "exec-v0",
        "fill_scenario": FillScenario.CONSERVATIVE,
        "execution_fidelity": ExecutionFidelity.CANDLES_ONLY,
        "random_seed": 7,
        "start": start,
        "end": end,
        "created_at": utc(2026, 8, 1),
    }

    def run_with(splits: tuple[SplitWindow, ...]) -> BacktestRun:
        return BacktestRun.model_validate({**common, "splits": splits})

    run_with(
        (
            SplitWindow(split=SampleSplit.TRAIN, start=start, end=mid),
            SplitWindow(split=SampleSplit.HOLDOUT, start=mid, end=end),
        )
    )
    with pytest.raises(ValueError, match="overlap"):
        run_with(
            (
                SplitWindow(split=SampleSplit.TRAIN, start=start, end=end),
                SplitWindow(split=SampleSplit.HOLDOUT, start=mid, end=end),
            )
        )
    with pytest.raises(ValueError, match="train"):
        run_with((SplitWindow(split=SampleSplit.HOLDOUT, start=mid, end=end),))


def test_research_run_and_live_deployment_need_their_records() -> None:
    started = utc(2026, 10, 2, 12)
    running = AgentResearchRun(
        user_prompt="Research Philadelphia high-temperature markets.",
        model="anthropic:claude",
        status=ResearchRunStatus.RUNNING,
        started_at=started,
    )
    with pytest.raises(ValueError, match="report"):
        running.revalidated(status=ResearchRunStatus.COMPLETED, finished_at=utc(2026, 10, 2, 13))
    report = ResearchReport(
        run_id=running.run_id,
        summary="Two mechanisms worth testing.",
        created_at=utc(2026, 10, 2, 13),
    )
    AgentResearchRun(
        run_id=running.run_id,
        user_prompt=running.user_prompt,
        model=running.model,
        status=ResearchRunStatus.COMPLETED,
        started_at=started,
        finished_at=utc(2026, 10, 2, 13),
        report=report,
        strategy_spec_hashes=(_spec().spec_hash(),),
    )
    envelope = CapitalEnvelope(max_dollars=Decimal("25"), max_contracts=Decimal(5))
    spec = _spec()
    with pytest.raises(ValueError, match="approver"):
        Deployment(
            strategy_id=spec.strategy_id,
            strategy_version=1,
            strategy_spec_hash=spec.spec_hash(),
            mode=TradingMode.LIVE,
            status=DeploymentStatus.ACTIVE,
            capital_envelope=envelope,
            created_at=started,
            activated_at=utc(2026, 10, 2, 14),
        )
    paper = Deployment(
        strategy_id=spec.strategy_id,
        strategy_version=1,
        strategy_spec_hash=spec.spec_hash(),
        mode=TradingMode.PAPER,
        status=DeploymentStatus.PROPOSED,
        capital_envelope=envelope,
        created_at=started,
    )
    assert paper.approved_by is None
    assert LifecycleState.DRAFT.value == "draft"
