"""Typed contracts for durable autonomous research.

Nothing here is an order, a trading approval or evidence of an edge. Hypotheses are
proposals; requirements and assessments are deterministic facts about available data.
"""

import re
from datetime import date, time
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import UtcDatetime
from entropytrade.features.registry import scientific_hash

NAME = r"^[a-z][a-z0-9_]{0,63}$"
SERIES = r"^[A-Z][A-Z0-9]{1,31}$"


class JobStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating_hypotheses"
    PLANNING = "planning_data"
    ACQUIRING = "acquiring_data"
    FEATURIZING = "registering_features"
    MODELING = "modeling"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AWAITING_OBSERVATIONS = "awaiting_observations"
    EVALUATED = "evaluated"
    RECOVERABLE_ERROR = "recoverable_error"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Statuses the worker advances by itself. Waiting statuses advance only on a trigger.
RUNNABLE = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.GENERATING,
        JobStatus.PLANNING,
        JobStatus.ACQUIRING,
        JobStatus.FEATURIZING,
        JobStatus.MODELING,
        JobStatus.RECOVERABLE_ERROR,
    }
)
TERMINAL = frozenset({JobStatus.FAILED, JobStatus.CANCELLED})
_ANY_ACTIVE = {JobStatus.RECOVERABLE_ERROR, JobStatus.FAILED, JobStatus.CANCELLED}
TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.GENERATING, *_ANY_ACTIVE}),
    JobStatus.GENERATING: frozenset({JobStatus.PLANNING, *_ANY_ACTIVE}),
    JobStatus.PLANNING: frozenset(
        {
            JobStatus.ACQUIRING,
            JobStatus.FEATURIZING,
            JobStatus.AWAITING_AUTHORIZATION,
            JobStatus.AWAITING_OBSERVATIONS,
            JobStatus.EVALUATED,
            *_ANY_ACTIVE,
        }
    ),
    JobStatus.ACQUIRING: frozenset({JobStatus.PLANNING, *_ANY_ACTIVE}),
    JobStatus.FEATURIZING: frozenset(
        {
            JobStatus.MODELING,
            JobStatus.PLANNING,
            JobStatus.AWAITING_AUTHORIZATION,
            JobStatus.AWAITING_OBSERVATIONS,
            JobStatus.EVALUATED,
            *_ANY_ACTIVE,
        }
    ),
    JobStatus.MODELING: frozenset(
        {
            JobStatus.PLANNING,
            JobStatus.AWAITING_AUTHORIZATION,
            JobStatus.AWAITING_OBSERVATIONS,
            JobStatus.EVALUATED,
            *_ANY_ACTIVE,
        }
    ),
    JobStatus.AWAITING_AUTHORIZATION: frozenset(
        {JobStatus.PLANNING, JobStatus.CANCELLED, JobStatus.FAILED}
    ),
    JobStatus.AWAITING_OBSERVATIONS: frozenset(
        {JobStatus.PLANNING, JobStatus.CANCELLED, JobStatus.FAILED}
    ),
    JobStatus.EVALUATED: frozenset({JobStatus.PLANNING, JobStatus.CANCELLED}),
    JobStatus.RECOVERABLE_ERROR: frozenset(
        {
            JobStatus.GENERATING,
            JobStatus.PLANNING,
            JobStatus.ACQUIRING,
            JobStatus.FEATURIZING,
            JobStatus.MODELING,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }
    ),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


def check_transition(current: JobStatus, target: JobStatus) -> None:
    if target not in TRANSITIONS[current]:
        raise ValueError(f"research job cannot move from {current.value} to {target.value}")


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    UNSUPPORTED = "permanently_unsupported"
    NEEDS_DATA = "needs_more_data"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AWAITING_OBSERVATIONS = "awaiting_new_observations"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BACKTEST_ELIGIBLE = "backtest_eligible"
    # Later lifecycle stages. Each requires deterministic evidence gates from a later
    # milestone (validation, paper results, explicit human approval). The research
    # service can never set them.
    HISTORICALLY_PROMISING = "historically_promising"
    PROSPECTIVE_PENDING = "prospective_validation_pending"
    PAPER_ELIGIBLE = "paper_trading_eligible"
    PAPER_ACTIVE = "paper_trading_active"
    LIVE_REQUESTED = "live_approval_requested"
    LIVE_ACTIVE = "live_active"
    SUSPENDED = "suspended"


RESEARCH_SETTABLE = frozenset(
    {
        HypothesisStatus.PROPOSED,
        HypothesisStatus.DUPLICATE,
        HypothesisStatus.REJECTED,
        HypothesisStatus.UNSUPPORTED,
        HypothesisStatus.NEEDS_DATA,
        HypothesisStatus.AWAITING_AUTHORIZATION,
        HypothesisStatus.AWAITING_OBSERVATIONS,
        HypothesisStatus.INSUFFICIENT_EVIDENCE,
        HypothesisStatus.BACKTEST_ELIGIBLE,
    }
)


class DataKind(StrEnum):
    """Family-neutral evidence vocabulary used by requirements, sources and datasets."""

    MARKET_CONTRACTS = "market_contracts"
    MARKET_RULES = "market_rules"
    DECISION_QUOTES = "decision_quotes"
    ORDER_BOOK_DEPTH = "order_book_depth"
    TRADE_PRINTS = "trade_prints"
    FEE_SCHEDULE = "fee_schedule"
    FORECAST_VINTAGES = "forecast_vintages"
    FORECAST_REVISIONS = "forecast_revisions"
    SETTLEMENT_LABELS = "settlement_labels"
    REFERENCE_OBSERVATIONS = "reference_observations"
    INTRADAY_OBSERVATIONS = "intraday_observations"
    COVARIATE_SERIES = "covariate_series"


class ProviderChoice(DomainModel):
    """Public provider selection. Keys and base URLs never enter this object."""

    provider: Literal["local_templates", "gemini", "openai", "anthropic", "openai_compatible"]
    model_name: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def check_model(self) -> Self:
        if self.provider == "local_templates":
            if self.model_name:
                raise ValueError("local templates do not use a model name")
        elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", self.model_name):
            raise ValueError("select a valid model name for the provider")
        return self


class ResearchBudget(DomainModel):
    """Hard per-job limits enforced by deterministic code."""

    ai_usd: Decimal = Field(default=Decimal("0.50"), ge=0, le=Decimal("5.00"))
    max_http_requests: int = Field(default=240, ge=0, le=2000)
    max_bytes: int = Field(default=96_000_000, ge=0, le=512_000_000)
    max_runtime_seconds: int = Field(default=1800, ge=60, le=86_400)
    max_retries: int = Field(default=3, ge=0, le=6)


class ResearchRequest(DomainModel):
    objective: str = Field(min_length=10, max_length=2000)
    family: str = Field(pattern=NAME)
    universe: tuple[str, ...] = Field(default=(), max_length=8)
    provider: ProviderChoice = ProviderChoice(provider="local_templates")
    budget: ResearchBudget = ResearchBudget()
    acquisition: Literal["none", "approved_sources", "ask"] = "approved_sources"
    lookback_days: int = Field(default=240, ge=7, le=365)
    validation_depth: Literal["quick", "standard", "thorough"] = "standard"
    paper_preference: Literal["never", "recommend", "paper_when_authorized"] = "recommend"

    @field_validator("universe")
    @classmethod
    def check_universe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(SERIES, item) is None for item in value):
            raise ValueError("universe entries must be series tickers")
        if len(set(value)) != len(value):
            raise ValueError("universe entries must be unique")
        return value

    def fingerprint(self) -> str:
        return scientific_hash(self.model_dump(mode="json"))


MIN_EVENTS = {"quick": 20, "standard": 60, "thorough": 120}


class FeatureNeed(DomainModel):
    """A feature or label a hypothesis uses, with the evidence it needs."""

    name: str = Field(pattern=NAME)
    role: Literal["feature", "label"] = "feature"
    data_kinds: tuple[DataKind, ...] = Field(default=(), max_length=6)
    note: str = Field(default="", max_length=400)


class RuleSketch(DomainModel):
    """A typed entry condition. ``threshold`` None means "to be fitted", never a guess."""

    feature: str = Field(pattern=NAME)
    op: Literal[">", ">=", "<", "<=", "=="]
    threshold: Decimal | None = None
    side: Literal["yes", "no", "either"] = "either"


class DecisionPoint(DomainModel):
    """A decision time in the contract's local timezone, relative to its target date."""

    day_offset: int = Field(ge=-3, le=0)
    local_time: time


class Provenance(DomainModel):
    generator: Literal["local_templates", "provider"]
    provider: str = ""
    model_name: str = ""
    template_id: str = ""
    prompt_hash: str = ""
    created_at: UtcDatetime


class HypothesisSpec(DomainModel):
    hypothesis_id: str = Field(pattern=r"^h-[0-9a-f]{12}$")
    version: int = Field(default=1, ge=1)
    signature: str
    title: str = Field(min_length=5, max_length=160)
    objective: str = Field(min_length=10, max_length=2000)
    family: str = Field(pattern=NAME)
    universe: tuple[str, ...] = Field(min_length=1, max_length=8)
    rationale: str = Field(min_length=20, max_length=2000)
    features: tuple[FeatureNeed, ...] = Field(min_length=1, max_length=10)
    label: FeatureNeed
    decision_schedule: tuple[DecisionPoint, ...] = Field(min_length=1, max_length=4)
    timestamp_semantics: str = Field(min_length=10, max_length=1000)
    candidate_models: tuple[str, ...] = Field(min_length=1, max_length=6)
    rules: tuple[RuleSketch, ...] = Field(default=(), max_length=6)
    validation_plan: str = Field(min_length=10, max_length=1500)
    leakage_risks: tuple[str, ...] = Field(min_length=1, max_length=8)
    invalidation: tuple[str, ...] = Field(min_length=1, max_length=8)
    provenance: Provenance
    claims_edge: Literal[False] = False

    @model_validator(mode="after")
    def check_label(self) -> Self:
        if self.label.role != "label":
            raise ValueError("the hypothesis label must have the label role")
        if any(f.role != "feature" for f in self.features):
            raise ValueError("labels may not be used as decision-time features")
        names = [f.name for f in self.features]
        if len(set(names)) != len(names) or self.label.name in names:
            raise ValueError("feature names must be unique and distinct from the label")
        if any(r.feature not in names for r in self.rules):
            raise ValueError("rules may reference only the hypothesis features")
        return self


def hypothesis_signature(family: str, mechanism: str, features: tuple[str, ...]) -> str:
    """Numbers are normalized so threshold-only variants count as the same search."""
    words = " ".join(re.sub(r"\d+(?:\.\d+)?", "#", mechanism.casefold()).split())
    return scientific_hash({"family": family, "mechanism": words, "features": sorted(features)})


class DataRequirement(DomainModel):
    """One machine-readable evidence need for one entity."""

    requirement_id: str
    kind: DataKind
    family: str = Field(pattern=NAME)
    entity: str = Field(min_length=1, max_length=64)
    series: str = Field(pattern=SERIES)
    variable: str = Field(pattern=NAME)
    start: date
    end: date
    clock: Literal["issuance", "receipt", "any"]
    fidelity: Literal["any", "quote", "order_book"] = "any"
    min_events: int = Field(ge=1, le=10_000)
    min_vintages: int = Field(default=1, ge=1, le=4)
    min_sources: int = Field(default=1, ge=1, le=4)
    blocking: Literal["predictive", "execution"]
    purpose: str = Field(min_length=10, max_length=600)
    features: tuple[str, ...] = ()
    hypotheses: tuple[str, ...] = ()
    # Hypotheses whose predictive test needs this evidence; for the rest it is execution-only.
    predictive_for: tuple[str, ...] = ()

    def blocking_for(self, hypothesis_id: str) -> Literal["predictive", "execution"]:
        return "predictive" if hypothesis_id in self.predictive_for else "execution"

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.end < self.start:
            raise ValueError("requirement window must be ordered")
        return self

    @property
    def coverage_key(self) -> str:
        """Equivalent needs share a key across jobs, so collection is never duplicated."""
        return scientific_hash(
            {
                "kind": self.kind.value,
                "family": self.family,
                "entity": self.entity,
                "variable": self.variable,
                "clock": self.clock,
                "fidelity": self.fidelity,
                "min_sources": self.min_sources,
            }
        )


def requirement_id(
    *, kind: DataKind, family: str, entity: str, variable: str, clock: str, fidelity: str
) -> str:
    return (
        "r-"
        + scientific_hash(
            {
                "kind": kind.value,
                "family": family,
                "entity": entity,
                "variable": variable,
                "clock": clock,
                "fidelity": fidelity,
            }
        ).removeprefix("sha256:")[:16]
    )


class AssessmentStatus(StrEnum):
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    MISSING = "missing"
    ACQUIRING = "acquiring"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    AWAITING_OBSERVATIONS = "awaiting_observations"
    UNOBTAINABLE = "unobtainable"


class Assessment(DomainModel):
    requirement_id: str
    status: AssessmentStatus
    events_available: int = Field(ge=0)
    events_required: int = Field(ge=1)
    datasets: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    assessed_at: UtcDatetime


class DatasetRecord(DomainModel):
    """One inventoried evidence slice: one dataset, kind, variable and source.

    ``coverage`` maps an entity to the ISO target dates covered; ``*`` marks evidence with
    no date dimension, such as a fee schedule. A forecast dataset lists a date under
    ``forecast_revisions`` only when two distinct issuance clocks exist for it.
    """

    record_id: str
    dataset_id: str
    origin: Literal[
        "research_acquisition",
        "weather_snapshot",
        "label_batch",
        "shadow_monitor",
        "configured_evidence",
        "fee_evidence",
        "collector_status",
    ]
    data_kind: Literal["authentic", "synthetic", "controlled"]
    kind: DataKind
    variable: str
    family: str
    source_id: str = ""
    clock: Literal["issuance", "receipt", "unknown"]
    fidelity: Literal["any", "candle", "quote", "order_book"] = "any"
    coverage: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    created_at: UtcDatetime | None = None
    content_hash: str = ""
    path: str = ""
    verified: bool = False
    detail: str = Field(default="", max_length=600)
