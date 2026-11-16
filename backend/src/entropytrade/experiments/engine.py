"""Family-neutral, protected deterministic experiments using the existing replay and registry."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Self

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field, model_validator

from entropytrade.backtest.replay import run_replay
from entropytrade.data.sources import file_hash
from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import FillScenario
from entropytrade.domain.numeric import ZERO, ExactDecimal
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.domain.strategy import ProbabilityModelRef, StrategySpec
from entropytrade.domain.time import utc_now
from entropytrade.execution.fee_evidence import FeeVersion, select_fee
from entropytrade.execution.fee_policy import FeePolicy as FeePolicy
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.experiments.data import (
    ContractSample,
    ExperimentData,
    PredictionBundle,
    PredictionProvider,
    ProbabilityRecord,
)
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import metrics
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.strategies.interpret import UnsupportedSpecError, compile_strategy
from entropytrade.strategy_registry.store import Registry


class ExperimentConfig(DomainModel):
    fee_policy: FeePolicy | None = None
    fee_versions: tuple[FeeVersion, ...] | None = None
    execution_policy: Literal["recorded_receipts", "legacy_snapshot_sensitivity"] = Field(
        default="recorded_receipts",
        exclude_if=lambda value: value == "legacy_snapshot_sensitivity",
    )
    latency_seconds: int = Field(default=1, ge=0, le=3600)
    max_book_age_seconds: int = Field(default=60, ge=0, le=3600)
    starting_cash: ExactDecimal = Field(default=Decimal("1000"), gt=0)
    per_trade: ExactDecimal = Field(default=Decimal("25"), gt=0)
    per_event: ExactDecimal = Field(default=Decimal("100"), gt=0)
    total_deployed: ExactDecimal = Field(default=Decimal("500"), gt=0)
    min_events: int = Field(default=20, ge=10)
    min_trades: int = Field(default=10, ge=1)
    bootstrap_samples: int = Field(default=500, ge=100, le=2000)
    seed: int = 17
    scenarios: tuple[FillScenario, ...] = (
        FillScenario.OPTIMISTIC,
        FillScenario.BASE,
        FillScenario.CONSERVATIVE,
    )

    def revalidated(self, **changes: object) -> Self:
        # Wire serialization omits the legacy value for historical compatibility;
        # validated copies must still preserve an explicitly selected legacy policy.
        return super().revalidated(**{"execution_policy": self.execution_policy, **changes})

    @model_validator(mode="after")
    def unique_scenarios(self) -> "ExperimentConfig":
        if self.fee_versions is not None and self.fee_policy is not None:
            raise ValueError("choose frozen fee evidence or a legacy explicit policy")
        if FillScenario.BASE not in self.scenarios or len(set(self.scenarios)) != len(
            self.scenarios
        ):
            raise ValueError("scenarios must be unique and include base")
        return self


def _covers(spec: StrategySpec, sample: ContractSample) -> bool:
    universe = spec.market_universe
    return (
        sample.ticker in universe.market_tickers
        or sample.event_id in universe.event_tickers
        or sample.family in universe.series_tickers
    )


def _interval(values: list[float], config: ExperimentConfig) -> dict[str, Any] | None:
    if len(values) < config.min_events:
        return None
    rng = np.random.default_rng(config.seed)
    array = np.asarray(values)
    estimates = [
        float(np.mean(rng.choice(array, size=len(array), replace=True)))
        for _ in range(config.bootstrap_samples)
    ]
    return {
        "lower": float(np.quantile(estimates, 0.025)),
        "upper": float(np.quantile(estimates, 0.975)),
        "blocks": len(values),
        "method": "fixed-seed date-block bootstrap mean",
        "nominal_coverage": 0.95,
    }


def _records(
    data: ExperimentData, samples: list[ContractSample], predictions: list[ProbabilityRecord]
) -> list[FeatureObservation]:
    observations = []
    ingested = utc_now()
    for sample in samples:
        for name, value in sample.features.items():
            observations.append(
                FeatureObservation(
                    source_id="pit-feature-matrix",
                    event_time=sample.decision_time,
                    available_at=sample.features_available_at,
                    ingested_at=max(ingested, sample.decision_time),
                    feature_name=name,
                    feature_version=sample.versions[name],
                    entity_id=sample.ticker,
                    value=value,
                    input_manifest_hash=data.feature_version,
                )
            )
    observations.extend(
        FeatureObservation(
            source_id=record.family,
            event_time=record.decision_time,
            available_at=record.decision_time,
            ingested_at=max(ingested, record.decision_time),
            feature_name="model_yes_probability",
            feature_version="r2-prediction-v1",
            entity_id=record.ticker,
            value=record.probability_yes,
            input_manifest_hash=record.model_hash,
        )
        for record in predictions
    )
    return observations


def _uses_recorded_execution(
    samples: list[ContractSample], data_kind: str, config: ExperimentConfig
) -> bool:
    return any(sample.execution_books for sample in samples) or (
        config.execution_policy == "recorded_receipts"
        and (
            data_kind == "real"
            or any(
                sample.book is not None and sample.book.received_at != sample.decision_time
                for sample in samples
            )
        )
    )


def _scenario(
    spec: StrategySpec,
    data: ExperimentData,
    samples: list[ContractSample],
    predictions: list[ProbabilityRecord],
    config: ExperimentConfig,
    scenario: FillScenario,
    end: datetime,
) -> dict[str, Any]:
    policy = config.fee_policy
    bindings: list[dict[str, Any]] = []
    families = {s.ticker: s.family for s in samples}

    def schedule_at(ticker: str, when: datetime) -> FeeSchedule:
        chosen, audit = select_fee(
            config.fee_versions or (), series=families[ticker], when=when, data_kind=data.data_kind
        )
        if chosen is None:
            raise ValueError("execution fee evidence refused: " + str(audit["reason"]))
        bindings.append(audit)
        return chosen.schedule.revalidated(
            quadratic_coefficient=chosen.schedule.quadratic_coefficient
            * (Decimal("1.5") if scenario is FillScenario.CONSERVATIVE else Decimal(1))
        )

    if config.fee_versions is not None:
        policy, _ = select_fee(
            config.fee_versions,
            series=samples[0].family,
            when=samples[0].decision_time,
            data_kind=data.data_kind,
        )
    if policy is None:
        raise ValueError("execution needs a fee policy")
    schedule = policy.schedule
    if scenario is FillScenario.CONSERVATIVE:
        schedule = schedule.revalidated(
            quadratic_coefficient=schedule.quadratic_coefficient * Decimal("1.5")
        )
    start = min(s.decision_time for s in samples)
    ledger = Ledger(config.starting_cash, as_of=start)
    explicit_execution = _uses_recorded_execution(samples, data.data_kind, config)
    books = tuple(
        book
        for sample in samples
        for book in ((sample.book,) if sample.book is not None else ()) + sample.execution_books
    )
    result = run_replay(
        books=books,
        decision_points=tuple(
            (sample.decision_time, sample.book) for sample in samples if sample.book is not None
        )
        if explicit_execution
        else None,
        records=_records(data, samples, predictions),
        strategy=compile_strategy(spec),
        ledger=ledger,
        broker=PaperBroker(ledger, schedule),
        fee_schedule_at=schedule_at if config.fee_versions is not None else None,
        engine=RiskEngine(
            RiskLimits(
                bankroll=config.starting_cash,
                per_trade=config.per_trade,
                per_event=config.per_event,
                total_deployed=config.total_deployed,
                max_loss=config.starting_cash,
                max_drawdown=config.starting_cash,
                max_book_age_seconds=config.max_book_age_seconds,
                min_liquidity=Decimal(".01"),
                max_spread=spec.execution.max_spread or Decimal("0.9999"),
                min_net_edge=spec.minimum_edge,
                config_version="r4-v1",
            )
        ),
        latency=timedelta(seconds=config.latency_seconds),
        window=SplitWindow(split=SampleSplit.VALIDATION, start=start, end=end),
        settlements=tuple(
            (s.outcome_available_at, s.ticker, s.outcome)
            for s in samples
            if s.outcome_available_at is not None and s.outcome is not None
        ),
        event_ids={s.ticker: s.event_id for s in samples},
        close_times={s.ticker: s.close_time for s in samples},
        target_dates={s.ticker: s.target_date for s in samples},
        max_book_age=timedelta(seconds=config.max_book_age_seconds),
        scenario=scenario,
    )
    fills = ledger.fills()
    peak, drawdown = config.starting_cash, ZERO
    for _, equity in result.equity_curve:
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    complete = not ledger.positions
    missing_execution_receipts = sum(
        row["status"] == "execution_evidence_missing" for row in result.audit
    )
    execution_evidence_complete = missing_execution_receipts == 0
    by_date: dict[str, float] = defaultdict(float)
    dates = {s.event_id: s.target_date.isoformat() for s in samples}
    # Include zero-trade dates. These are correlated event blocks, not tick returns.
    for day in dates.values():
        by_date[day] += 0
    for event, value in result.event_pnl.items():
        by_date[dates[event]] += float(value)
    return {
        "scenario": scenario.value,
        "execution_fidelity": "sized_snapshot_taker_simulation",
        **(
            {
                "execution_clock_mode": "recorded_post_decision_receipts",
                "execution_evidence_complete": execution_evidence_complete,
                "missing_execution_receipts": missing_execution_receipts,
            }
            if explicit_execution
            else {}
        ),
        "fee_policy": policy.model_dump(mode="json"),
        "fee_bindings": bindings,
        "fee_schedule_used": schedule.model_dump(mode="json"),
        "fill_count": len(fills),
        "filled_orders": len({f.client_order_id for f in fills}),
        "events_traded": len(
            {
                next(s.event_id for s in samples if s.ticker == f.contract.market_ticker)
                for f in fills
            }
        ),
        "net_pnl": str(ledger.equity() - config.starting_cash)
        if complete and execution_evidence_complete
        else None,
        "realized_pnl": str(ledger.realized_pnl),
        "fees_paid": str(ledger.fees_paid),
        "drawdown_at_cost": str(drawdown) if complete and execution_evidence_complete else None,
        "mark_basis": "cost-basis equity between settlements, not market marks",
        "unsettled_positions": len(ledger.positions),
        "mean_date_pnl_interval": _interval(list(by_date.values()), config)
        if complete and execution_evidence_complete
        else None,
        "ledger": ledger.dump(),
        "audit": result.audit,
        "equity_curve": [{"time": t.isoformat(), "equity": str(e)} for t, e in result.equity_curve],
    }


def evaluate_candidate(
    candidate: dict[str, Any],
    research: dict[str, Any],
    data: ExperimentData,
    provider: PredictionProvider,
    config: ExperimentConfig,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "candidate_id": candidate["candidate_id"],
        "status": "INSUFFICIENT_DATA",
        "reasons": [],
        "forecast_metrics": None,
        "scenarios": [],
        "rank": None,
        "data_kind": data.data_kind,
        "tested": False,
    }
    if candidate["spec"] is None or candidate["missing_capability"]:
        result.update(
            status="UNSUPPORTED",
            reasons=[
                candidate["missing_capability"]
                if candidate["spec"] is not None
                else "no executable StrategySpec was supplied"
            ],
        )
        return result
    try:
        spec = StrategySpec.model_validate(candidate["spec"])
        compile_strategy(spec)
    except (ValueError, UnsupportedSpecError) as exc:
        result.update(status="UNSUPPORTED", reasons=[str(exc)])
        return result
    result["original_spec_hash"] = spec.spec_hash()
    decision = next(
        (d for d in research["decisions"] if d["candidate_id"] == candidate["candidate_id"]), None
    )
    if decision and decision.get("status") == "REJECTED":
        result.update(
            status="INVALID", reasons=["deterministic research validation rejected this candidate"]
        )
        return result
    verdict = next(
        (
            d["critic"]
            for d in research["decisions"]
            if d["candidate_id"] == candidate["candidate_id"]
        ),
        None,
    )
    if verdict is None or not verdict["accept_for_experiment"]:
        result.update(
            status="REJECTED", reasons=["critic rejected or did not judge this candidate"]
        )
        return result
    definitions = {f["name"]: f["version"] for f in data.feature_definitions["features"]}
    names = (
        set(candidate["required_features"])
        | {p.feature for p in spec.entry_rules.all_of}
        | {f.name for f in spec.features}
    )
    if spec.exit_mode == "predicate":
        names.update(p.feature for p in spec.exit_rules.all_of)
    if names - set(definitions) - {"model_yes_probability", "yes_bid", "yes_ask"}:
        result.update(status="INVALID", reasons=["unknown feature reference"])
        return result
    if any(
        f.version is not None and f.version != definitions.get(f.name, "r2-prediction-v1")
        for f in spec.features
    ):
        result.update(status="INVALID", reasons=["feature version mismatch"])
        return result
    universe = spec.market_universe
    if (
        not set(universe.market_tickers) <= {s.ticker for s in data.samples}
        or not set(universe.event_tickers) <= {s.event_id for s in data.samples}
        or not set(universe.series_tickers) <= {s.family for s in data.samples}
    ):
        result.update(
            status="INVALID", reasons=["market universe contains unlisted contracts/events/series"]
        )
        return result
    scoped = [
        s for s in data.samples if s.event_id not in data.protected_events and _covers(spec, s)
    ]
    if config.fee_versions is not None:
        result["fee_evidence"] = [
            select_fee(
                config.fee_versions, series=s.family, when=s.decision_time, data_kind=data.data_kind
            )[1]
            for s in scoped
        ]
    result["coverage"] = {
        "events": len({s.event_id for s in scoped}),
        "eligible_events": len({s.event_id for s in scoped if s.eligible}),
        "books": sum(s.book is not None for s in scoped),
    }
    if set(candidate["required_sources"]) != set(spec.required_sources):
        result.update(status="INVALID", reasons=["candidate/spec source requirements disagree"])
        return result
    if not any(set(spec.required_sources) <= set(s.sources) for s in scoped):
        result["reasons"] = ["required source provenance is unavailable at decision time"]
        return result
    missing_features = [
        name
        for name in names & set(definitions)
        if not any(s.features.get(name) is not None for s in scoped)
    ]
    if missing_features:
        result["coverage"] = {
            "events": len({s.event_id for s in scoped}),
            "eligible_events": len({s.event_id for s in scoped if s.eligible}),
            "books": sum(s.book is not None for s in scoped),
        }
        result["reasons"] = [
            "no usable point-in-time feature coverage: " + ", ".join(sorted(missing_features)),
            "no trading inference is possible from missing inputs",
        ]
        return result
    try:
        bundle = provider.prepare(spec, candidate["model_family"])
    except ValueError as exc:
        result.update(status="INVALID", reasons=[str(exc)])
        return result
    if bundle.model_metadata.get("data_kind") != data.data_kind:
        result.update(status="INVALID", reasons=["synthetic/real model and dataset mismatch"])
        return result
    result["model_lineage"] = {
        "source_hash": bundle.source_hash,
        "metadata": bundle.model_metadata,
        "refusals": bundle.refusals,
    }
    protected = set(data.protected_events) | set(
        (bundle.model_metadata.get("split") or {}).get("holdout", [])
    )
    eligible = [s for s in data.samples if s.event_id not in protected and _covers(spec, s)]
    samples_by_key = {(s.ticker, s.decision_time): s for s in eligible}
    predictions = [
        p
        for p in bundle.records
        if p.family == candidate["model_family"]
        and p.partition == "validation"
        and p.event_id not in protected
        and (p.ticker, p.decision_time) in samples_by_key
    ]
    if not predictions:
        result["reasons"] = [
            bundle.refusals.get(
                candidate["model_family"],
                "no permitted validation predictions; "
                "insufficient point-in-time data/model history",
            ),
            "execution P&L is unavailable without certified rules, sized books and fee evidence",
        ]
        result["coverage"] = {
            "events": len({s.event_id for s in eligible}),
            "eligible_events": len({s.event_id for s in eligible if s.eligible}),
            "books": sum(s.book is not None for s in eligible),
        }
        return result
    samples = [samples_by_key[p.ticker, p.decision_time] for p in predictions]
    if any(
        not p.usable(s) or p.feature_version != data.feature_version
        for p, s in zip(predictions, samples, strict=True)
    ):
        result.update(
            status="INVALID",
            reasons=["future-trained/calibrated model or mismatched point-in-time feature vector"],
        )
        return result
    model_hashes = {p.model_hash for p in predictions}
    if len(model_hashes) != 1 or (
        spec.model_ref
        and (
            spec.model_ref.version not in model_hashes
            or spec.model_ref.family != candidate["model_family"]
        )
    ):
        result.update(
            status="INVALID",
            reasons=["model version mismatch or multiple model versions in one partition"],
        )
        return result
    requested = spec.calibration.value
    actual = {p.calibration for p in predictions}
    if (requested == "none" and not actual <= {"none", "uncalibrated baseline"}) or (
        requested != "none" and actual != {requested}
    ):
        result.update(
            status="INVALID", reasons=["calibration method differs from requested StrategySpec"]
        )
        return result
    spec = spec.revalidated(
        model_ref=ProbabilityModelRef(
            family=candidate["model_family"], version=next(iter(model_hashes))
        )
    )
    result["executed_spec"] = spec.model_dump(mode="json")
    result["executed_spec_hash"] = spec.spec_hash()
    result["prediction_ids"] = [p.prediction_id for p in predictions]
    scored = [
        {
            "event_id": s.event_id,
            "market_ticker": s.ticker,
            "target_date": s.target_date.isoformat(),
            "outcome": s.outcome.value,
            "probability_yes": float(p.probability_yes),
        }
        for p, s in zip(predictions, samples, strict=True)
        if s.outcome is not None
    ]
    result["forecast_metrics"] = metrics(scored, min_events=config.min_events)
    result["walk_forward"] = bundle.model_metadata.get("walk_forward", [])
    baseline = {
        (p.ticker, p.decision_time): p
        for p in bundle.records
        if p.family == bundle.model_metadata.get("baseline_family", "climatology")
        and p.partition == "validation"
    }
    comparisons: list[dict[str, Any]] = []
    improvements: dict[str, list[float]] = defaultdict(list)
    for p, s in zip(predictions, samples, strict=True):
        if s.outcome is None:
            continue
        reference = None
        if (
            s.book
            and s.book.midpoint is not None
            and s.decision_time - s.book.received_at
            <= timedelta(seconds=config.max_book_age_seconds)
        ):
            reference = float(s.book.midpoint)
        elif (s.ticker, s.decision_time) in baseline and baseline[s.ticker, s.decision_time].usable(
            s
        ):
            reference = float(baseline[s.ticker, s.decision_time].probability_yes)
        if reference is not None:
            y = float(s.outcome.value == "yes")
            comparisons.append(
                {
                    "event_id": s.event_id,
                    "market_ticker": s.ticker,
                    "target_date": s.target_date.isoformat(),
                    "outcome": s.outcome.value,
                    "probability_yes": reference,
                }
            )
            improvements[s.target_date.isoformat()].append(
                (reference - y) ** 2 - (float(p.probability_yes) - y) ** 2
            )
    result["benchmark"] = metrics(comparisons, min_events=config.min_events)
    result["benchmark"]["basis"] = (
        "available quoted midpoint else registered training-only baseline; not executable fills"
    )
    result["brier_improvement_interval"] = _interval(
        [float(np.mean(v)) for v in improvements.values()], config
    )
    if len({s.event_id for s in samples}) < config.min_events or any(
        not s.eligible
        or not s.rules_known
        or s.outcome is None
        or not set(spec.required_sources) <= set(s.sources)
        for s in samples
    ):
        result["reasons"].append(
            "insufficient independent validation events, labels or known rules"
        )
    if any(s.book is None or s.fidelity != "order_book" for s in samples):
        result["reasons"].append(
            "historical execution lacks sized books; candles/prints are not fills"
        )
    if any(
        s.book is not None
        and (
            s.decision_time - s.book.received_at > timedelta(seconds=config.max_book_age_seconds)
            or (s.book.exchange_ts is not None and s.book.exchange_ts > s.decision_time)
        )
        for s in samples
    ):
        result["reasons"].append(
            "historical execution depth is stale or has a future exchange clock"
        )
    policy = config.fee_policy
    start = min(s.decision_time for s in samples)
    protected_starts = [s.decision_time for s in data.samples if s.event_id in protected]
    end = (
        min(protected_starts)
        if protected_starts
        else max(s.close_time for s in samples) + timedelta(days=2)
    )
    if config.fee_versions is not None:
        # Replay decides on the retained book clock and executes after configured latency.
        # Verify every required clock before producing any scenario; mixed versions are legal.
        explicit_execution = _uses_recorded_execution(samples, data.data_kind, config)
        checks = [
            select_fee(config.fee_versions, series=s.family, when=when, data_kind=data.data_kind)[1]
            for s in samples
            for when in (
                {s.decision_time, s.decision_time + timedelta(seconds=config.latency_seconds)}
                if explicit_execution
                else {
                    s.decision_time,
                    s.book.received_at if s.book else s.decision_time,
                    (s.book.received_at if s.book else s.decision_time)
                    + timedelta(seconds=config.latency_seconds),
                }
            )
        ]
        result["execution_fee_evidence"] = sorted(
            checks, key=lambda a: (a["series"], a["decision_time"])
        )
        if any(a["status"] != "applicable" for a in checks):
            result["reasons"].append(
                "point-in-time fee evidence refused: "
                + ", ".join(sorted({a["reason"] for a in checks if a["reason"]}))
            )
    elif policy is None or (
        data.data_kind == "real" and (not policy.certified or not policy.evidence_hash)
    ):
        result["reasons"].append("verified historical fee schedule unavailable")
    elif (
        policy.available_at > start
        or policy.effective_from > start
        or (policy.effective_to and end > policy.effective_to)
    ):
        result["reasons"].append("fee schedule is outside its information/effective-time range")
    if result["reasons"]:
        return result
    result["scenarios"] = [
        _scenario(spec, data, samples, predictions, config, scenario, end)
        for scenario in config.scenarios
    ]
    result["tested"] = True
    result["status"] = "BACKTESTED"
    if any(s.get("execution_evidence_complete") is False for s in result["scenarios"]):
        result.update(
            status="INSUFFICIENT_DATA",
            reasons=[
                "missing actual post-decision execution receipts; "
                "partial simulated accounting cannot establish execution profitability"
            ],
        )
    elif any(s["unsettled_positions"] for s in result["scenarios"]):
        result.update(
            status="INSUFFICIENT_DATA",
            reasons=["positions unresolved within the permitted evaluation window"],
        )
    elif all(s["fill_count"] < config.min_trades for s in result["scenarios"]):
        result.update(status="REJECTED", reasons=["too few modeled fills for trading evidence"])
    elif data.data_kind == "real":
        ci = result["brier_improvement_interval"]
        robust = (
            ci is not None
            and ci["lower"] > 0
            and all(
                s["mean_date_pnl_interval"] is not None and s["mean_date_pnl_interval"]["lower"] > 0
                for s in result["scenarios"]
            )
        )
        result.update(
            status="PROMISING_FOR_FURTHER_VALIDATION" if robust else "REJECTED",
            reasons=[]
            if robust
            else [
                "validation evidence is statistically weak or sensitive to execution assumptions"
            ],
        )
    return result


class _PreparedProvider:
    def __init__(self, provider: PredictionProvider) -> None:
        self.provider = provider
        self.cache: dict[str, Any] = {}

    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        key = str((family, spec.spec_hash()))
        if key not in self.cache:
            try:
                self.cache[key] = self.provider.prepare(spec, family)
            except ValueError as exc:
                self.cache[key] = str(exc)
        value = self.cache[key]
        if isinstance(value, str):
            raise ValueError(value)
        if not isinstance(value, PredictionBundle):
            raise TypeError("invalid registered provider bundle")
        return value


def run_experiments(
    *,
    research: dict[str, Any],
    data: ExperimentData,
    provider: PredictionProvider,
    config: ExperimentConfig,
    registry_path: Path,
    output: Path,
    tracking: Path,
) -> dict[str, Any]:
    if research["status"] != "completed":
        raise ValueError("failed research cannot enter experiments")
    from entropytrade.agents.outputs import CandidateBatch

    CandidateBatch.model_validate({"candidates": research["candidates"]})
    if research["coverage"]["feature_version"] != data.feature_version:
        raise ValueError("research/experiment feature version mismatch")
    cached_provider = _PreparedProvider(provider)
    resolved: dict[str, Any] = {}
    for candidate in research["candidates"]:
        if candidate["spec"] is None or candidate["missing_capability"]:
            continue
        if any(
            d["candidate_id"] == candidate["candidate_id"] and d.get("status") == "REJECTED"
            for d in research["decisions"]
        ):
            continue
        try:
            spec = StrategySpec.model_validate(candidate["spec"])
            compile_strategy(spec)
            bundle = cached_provider.prepare(spec, candidate["model_family"])
            resolved[candidate["candidate_id"]] = bundle.source_hash
        except ValueError as exc:
            resolved[candidate["candidate_id"]] = {"refusal": str(exc)}
    code = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    package = Path(__file__).parent.parent
    for name in (
        "backtest/replay.py",
        "strategies/interpret.py",
        "execution/paper.py",
        "execution/fees.py",
        "execution/fee_policy.py",
        "execution/fee_evidence.py",
        "risk/engine.py",
        "domain/strategy.py",
    ):
        code[name] = file_hash(package / name)
    normalized = data.model_dump(mode="json")
    normalized["protected_events"] = sorted(data.protected_events)
    identity = {
        "research_run": research["run_id"],
        "research_hash": scientific_hash(research),
        "dataset": data.dataset_version,
        "feature_version": data.feature_version,
        "config": config.model_dump(mode="json"),
        "resolved_models": resolved,
        "normalized_data_hash": scientific_hash(normalized),
        "code": code,
    }
    experiment_id = scientific_hash(identity)
    destination = output / experiment_id.removeprefix("sha256:")
    if destination.exists():
        for name, digest in json.loads((destination / "checksums.json").read_text()).items():
            if file_hash(destination / name) != digest:
                raise ValueError("experiment artifact checksum mismatch")
        cached: dict[str, Any] = json.loads((destination / "results.json").read_text())
        return cached
    results = [
        evaluate_candidate(c, research, data, cached_provider, config)
        for c in research["candidates"]
    ]
    comparable = [r for r in results if r["forecast_metrics"] and "brier" in r["forecast_metrics"]]
    prior_score = None
    rank = 0
    for row in sorted(comparable, key=lambda r: r["forecast_metrics"]["brier"]):
        score = row["forecast_metrics"]["brier"]
        if prior_score != score:
            rank += 1
        prior_score = score
        row["rank"] = rank
        row["ranking_basis"] = "validation Brier; ties share a rank; trading status is separate"
    result = {
        "experiment_id": experiment_id,
        **identity,
        "data_kind": data.data_kind,
        "candidates": results,
        "requested_trial_count": len(results) * len(config.scenarios),
        "final_holdout_evaluated": False,
        "warnings": [
            "Each candidate/scenario counts as a trial. Intervals are descriptive after selection.",
            "Snapshot fills model taker execution, not queues or observed fills.",
            "Synthetic results verify software only; ranking is not deployment authorization.",
        ],
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = Registry(registry_path)
    try:
        registry.record_experiment(
            experiment_id,
            json.dumps(result, sort_keys=True),
            len(results) * len(config.scenarios),
            data.data_kind,
        )
        # The registry counts cumulative trials; this artifact records its immutable batch.
    finally:
        registry.close()
    destination.mkdir(parents=True)
    (destination / "results.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    trades = [
        {"candidate_id": r["candidate_id"], "scenario": s["scenario"], **f}
        for r in results
        for s in r["scenarios"]
        for f in s["ledger"]["fills"]
    ]
    pq.write_table(
        pa.Table.from_pylist(
            [{"payload_json": json.dumps(t, sort_keys=True)} for t in trades],
            schema=pa.schema([("payload_json", pa.string())]),
        ),
        destination / "trades.parquet",
    )
    lines = [
        "# Research-to-experiment report",
        "",
        f"Data: {data.data_kind}. Research run: {research['run_id']}",
        "Final holdout: not evaluated. No trading authorization.",
        "",
    ]
    for row in results:
        lines += [
            f"{row['candidate_id']}: {row['status']}",
            "; ".join(row["reasons"]) or "Completed deterministic validation experiment.",
        ]
        if row["forecast_metrics"]:
            lines.append("Forecast metrics: " + json.dumps(row["forecast_metrics"], sort_keys=True))
        for scenario in row["scenarios"]:
            lines.append(
                f"{scenario['scenario']}: fills={scenario['fill_count']}, "
                f"net P&L={scenario['net_pnl']}, fees={scenario['fees_paid']}; modeled fills."
            )
    lines += ["", *result["warnings"]]
    (destination / "report.md").write_text("\n".join(lines) + "\n")
    if config.fee_versions is not None:
        # Protected labels/features never enter the portable replay projection.
        protected = set(data.protected_events)
        for value in cached_provider.cache.values():
            if isinstance(value, PredictionBundle):
                protected.update((value.model_metadata.get("split") or {}).get("holdout", []))
        replay_data = data.revalidated(
            samples=tuple(
                s.revalidated(
                    features={},
                    versions={},
                    outcome=None,
                    outcome_available_at=None,
                    book=None,
                    execution_books=(),
                )
                if s.event_id in protected
                else s
                for s in data.samples
            )
        )
        bundles = {
            key: value.revalidated(
                records=tuple(
                    p
                    for p in value.records
                    if p.event_id not in protected and p.partition != "holdout"
                )
            ).model_dump(mode="json")
            if isinstance(value, PredictionBundle)
            else value
            for key, value in cached_provider.cache.items()
        }
        (destination / "replay-inputs.json").write_text(
            json.dumps(
                {
                    "schema": "experiment-replay-v1",
                    "research": research,
                    "data": {
                        **replay_data.model_dump(mode="json"),
                        "protected_events": sorted(data.protected_events),
                    },
                    "config": config.model_dump(mode="json"),
                    "predictions": bundles,
                },
                sort_keys=True,
                indent=2,
            )
        )
    (destination / "checksums.json").write_text(
        json.dumps({p.name: file_hash(p) for p in destination.iterdir()}, sort_keys=True)
    )
    _track(result, destination, tracking)
    return result


def _track(result: dict[str, Any], path: Path, tracking: Path) -> None:
    import mlflow

    tracking.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking.resolve().as_uri())
    mlflow.set_experiment("entropytrade-strategy-experiments")
    with mlflow.start_run(run_name=result["experiment_id"]):
        mlflow.log_params(
            {
                "experiment_id": result["experiment_id"],
                "research_run": result["research_run"],
                "data_kind": result["data_kind"],
            }
        )
        for row in result["candidates"]:
            if row["forecast_metrics"] and "brier" in row["forecast_metrics"]:
                mlflow.log_metric(row["candidate_id"] + ".brier", row["forecast_metrics"]["brier"])
        mlflow.log_artifacts(str(path))
