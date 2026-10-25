"""Structured strategy specifications (spec section 8).

A research agent emits a :class:`StrategySpec`, never an order and never executable Python.
``risk_overrides_allowed`` is fixed at ``"none"``: a spec cannot raise risk limits.
``spec_hash()`` is the immutable identity of a spec's content.
"""

from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import ActorKind, OutcomeSide, StrategyFamily, TimeInForce, Venue
from entropytrade.domain.ids import ContentHash, content_hash
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.numeric import ZERO, ExactDecimal, PositiveQuantity
from entropytrade.domain.time import UtcDatetime

MAX_KELLY_FRACTION = Decimal("0.5")
"""Full Kelly cannot be expressed. Sizing above this is rejected by the type itself."""


class SizingMethod(StrEnum):
    FIXED_CONTRACTS = "fixed_contracts"
    FIXED_DOLLARS = "fixed_dollars"
    FRACTIONAL_KELLY = "fractional_kelly"


class ModelKind(StrEnum):
    """Baselines from spec section 11. ``NONE`` means rules over features, no fitted model."""

    NONE = "none"
    LOGISTIC_REGRESSION = "logistic_regression"
    GLM = "glm"
    CALIBRATED_CLASSIFIER = "calibrated_classifier"
    GRADIENT_BOOSTED_TREES = "gradient_boosted_trees"
    DOMAIN_STATISTICAL = "domain_statistical"
    ENSEMBLE = "ensemble"


class CalibrationMethod(StrEnum):
    NONE = "none"
    ISOTONIC = "isotonic"
    PLATT = "platt"


class ComparisonOp(StrEnum):
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    EQ = "eq"


class MarketUniverse(DomainModel):
    """Ticker constraints that bound where a strategy may look. Never "all markets"."""

    venue: Venue = Venue.KALSHI
    description: str = Field(min_length=1)
    series_tickers: tuple[str, ...] = ()
    event_tickers: tuple[str, ...] = ()
    market_tickers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        groups = (self.series_tickers, self.event_tickers, self.market_tickers)
        if not any(groups):
            raise ValueError("a market universe needs at least one ticker constraint")
        for group in groups:
            if any(not ticker.strip() for ticker in group):
                raise ValueError("tickers must be non-empty")
            if len(set(group)) != len(group):
                raise ValueError("ticker constraints must be unique")
        return self


class FeatureRequirement(DomainModel):
    name: str = Field(min_length=1)
    version: str | None = None
    description: str = Field(min_length=1)


class Predicate(DomainModel):
    """One comparison. Rules are data, so they can be validated without executing code."""

    feature: str = Field(min_length=1)
    op: ComparisonOp
    threshold: ExactDecimal


class RuleSet(DomainModel):
    description: str = Field(min_length=1)
    all_of: tuple[Predicate, ...] = Field(min_length=1)


class PositionSizing(DomainModel):
    method: SizingMethod
    contracts: PositiveQuantity | None = None
    dollars: ExactDecimal | None = None
    kelly_fraction: ExactDecimal | None = None
    max_contracts: PositiveQuantity

    @model_validator(mode="after")
    def _matches_method(self) -> Self:
        if self.dollars is not None and self.dollars <= ZERO:
            raise ValueError("dollar sizing must be positive")
        if self.method is SizingMethod.FIXED_CONTRACTS and self.contracts is None:
            raise ValueError("fixed-contract sizing needs a contract count")
        if self.method is SizingMethod.FIXED_DOLLARS and self.dollars is None:
            raise ValueError("fixed-dollar sizing needs a dollar amount")
        if self.method is SizingMethod.FRACTIONAL_KELLY:
            fraction = self.kelly_fraction
            if fraction is None or not ZERO < fraction <= MAX_KELLY_FRACTION:
                raise ValueError(f"kelly_fraction must be in (0, {MAX_KELLY_FRACTION}]")
        if self.contracts is not None and self.contracts > self.max_contracts:
            raise ValueError("contracts cannot exceed max_contracts")
        return self


class ExecutionPreferences(DomainModel):
    time_in_force: TimeInForce = TimeInForce.GOOD_TILL_CANCELED
    post_only: bool = False
    max_spread: ExactDecimal | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.post_only and self.time_in_force is not TimeInForce.GOOD_TILL_CANCELED:
            raise ValueError("post-only execution must rest")
        if self.max_spread is not None and self.max_spread <= ZERO:
            raise ValueError("max_spread must be positive")
        return self


class Citation(DomainModel):
    source: str = Field(min_length=1)
    url: str | None = None
    claim: str = Field(min_length=1)
    observed_at: UtcDatetime | None = None


class EntryWindow(DomainModel):
    """UTC instants and event target dates, both inclusive start / exclusive end."""

    start: UtcDatetime | None = None
    end: UtcDatetime | None = None
    target_start: date | None = None
    target_end: date | None = None

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("entry window end must follow start")
        if (
            self.target_start is not None
            and self.target_end is not None
            and self.target_end <= self.target_start
        ):
            raise ValueError("target date end must follow start")
        return self


class ProbabilityModelRef(DomainModel):
    family: str = Field(min_length=1)
    version: ContentHash


class StrategySpec(DomainModel):
    """A testable strategy. Downstream code consumes this model, not free-form prose."""

    strategy_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    strategy_family: StrategyFamily
    market_universe: MarketUniverse
    side: OutcomeSide = OutcomeSide.YES
    entry_window: EntryWindow = EntryWindow()
    probability_feature: str | None = None
    model_ref: ProbabilityModelRef | None = None
    max_entry_price: ExactDecimal | None = None
    min_displayed_quantity: PositiveQuantity | None = None
    uncertainty_allowance: ExactDecimal = ZERO
    slippage_allowance: ExactDecimal = ZERO
    exit_mode: Literal["hold_to_settlement", "predicate"] = "hold_to_settlement"
    required_sources: tuple[str, ...] = Field(min_length=1)
    features: tuple[FeatureRequirement, ...] = ()
    model_kind: ModelKind = ModelKind.NONE
    calibration: CalibrationMethod = CalibrationMethod.NONE
    entry_rules: RuleSet
    exit_rules: RuleSet
    minimum_edge: ExactDecimal
    position_sizing: PositionSizing
    maximum_holding_period_seconds: int | None = Field(default=None, gt=0)
    hedging_rules: str = ""
    execution: ExecutionPreferences = ExecutionPreferences()
    risk_overrides_allowed: Literal["none"] = "none"
    invalidation_conditions: tuple[str, ...] = Field(min_length=1)
    assumptions: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()
    generated_by: Actor
    generation_run_id: UUID | None = None
    created_at: UtcDatetime

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.max_entry_price is not None and not ZERO < self.max_entry_price <= 1:
            raise ValueError("maximum entry price must be in (0,1]")
        if self.uncertainty_allowance < ZERO or self.slippage_allowance < ZERO:
            raise ValueError("cost allowances must be nonnegative")
        if self.minimum_edge <= ZERO:
            raise ValueError("minimum_edge must be positive: a zero edge is not a trade")
        if self.generated_by.kind is ActorKind.AGENT and self.generation_run_id is None:
            raise ValueError("an agent-authored spec must name its research run")
        if self.calibration is not CalibrationMethod.NONE and self.model_kind is ModelKind.NONE:
            raise ValueError("calibration requires a model")
        if any(not item.strip() for item in self.invalidation_conditions + self.assumptions):
            raise ValueError("assumptions and invalidation conditions must be non-empty")
        return self

    @property
    def maximum_holding_period(self) -> timedelta | None:
        seconds = self.maximum_holding_period_seconds
        if seconds is None:
            return None
        return timedelta(seconds=seconds)

    def spec_hash(self) -> ContentHash:
        """Stable identity of this spec. Equal content hashes equal, regardless of field order."""
        return content_hash(self.model_dump(mode="python"))


class StrategyVersion(DomainModel):
    """One immutable version in a strategy's lineage. Old versions are never overwritten."""

    strategy_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    spec_hash: ContentHash
    parent_spec_hash: ContentHash | None = None
    created_at: UtcDatetime

    @model_validator(mode="after")
    def _lineage(self) -> Self:
        if self.version == 1 and self.parent_spec_hash is not None:
            raise ValueError("version 1 has no parent")
        if self.version > 1 and self.parent_spec_hash is None:
            raise ValueError("versions after 1 must name their parent spec")
        if self.parent_spec_hash == self.spec_hash:
            raise ValueError("a version cannot be its own parent")
        return self

    @classmethod
    def from_spec(
        cls,
        spec: StrategySpec,
        *,
        parent_spec_hash: ContentHash | None = None,
    ) -> "StrategyVersion":
        return cls(
            strategy_id=spec.strategy_id,
            version=spec.version,
            spec_hash=spec.spec_hash(),
            parent_spec_hash=parent_spec_hash,
            created_at=spec.created_at,
        )
