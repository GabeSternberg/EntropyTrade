"""Research runs, backtest-run records and deployments (spec sections 9, 13 and 16).

These are records of what happened or was approved. They do not run anything: the backtest
engine is Phase 3, the agents are Phase 5, and live deployment is Phase 9.
"""

from enum import StrEnum
from itertools import pairwise
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import ExecutionFidelity, FillScenario
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.ids import ContentHash, new_id
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.numeric import NonNegativeMoney, PositiveQuantity
from entropytrade.domain.time import UtcDatetime


class ResearchRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Hypothesis(DomainModel):
    """A falsifiable statement, not a theme. "Weather forecasts are useful" does not qualify."""

    hypothesis_id: str = Field(min_length=1)
    statement: str = Field(min_length=20)
    created_at: UtcDatetime


class ResearchReport(DomainModel):
    report_id: UUID = Field(default_factory=new_id)
    run_id: UUID
    summary: str = Field(min_length=1)
    hypotheses: tuple[Hypothesis, ...] = ()
    uncertainties: tuple[str, ...] = ()
    suggested_sources: tuple[str, ...] = ()
    created_at: UtcDatetime


class AgentResearchRun(DomainModel):
    run_id: UUID = Field(default_factory=new_id)
    user_prompt: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: ResearchRunStatus
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None
    report: ResearchReport | None = None
    strategy_spec_hashes: tuple[ContentHash, ...] = ()

    @model_validator(mode="after")
    def _status(self) -> Self:
        if self.status is ResearchRunStatus.RUNNING:
            if self.finished_at is not None or self.report is not None:
                raise ValueError("a running research run has no report yet")
            return self
        if self.finished_at is None or self.finished_at < self.started_at:
            raise ValueError("a finished research run needs a finished_at at or after start")
        report_missing = self.report is None or self.report.run_id != self.run_id
        if self.status is ResearchRunStatus.COMPLETED and report_missing:
            raise ValueError("a completed run needs a report for this run")
        return self


class SampleSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class SplitWindow(DomainModel):
    split: SampleSplit
    start: UtcDatetime
    end: UtcDatetime

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("a split must end after it starts")
        return self


class BacktestRun(DomainModel):
    """Provenance of one backtest. Metrics and trades are produced by the Phase 3 engine."""

    run_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    strategy_spec_hash: ContentHash
    git_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{7,40}$")
    config_hash: ContentHash
    dataset_manifest_hash: ContentHash
    feature_version: str = Field(min_length=1)
    model_artifact_version: str | None = None
    fee_model: FeeModelRef
    execution_model_version: str = Field(min_length=1)
    fill_scenario: FillScenario
    execution_fidelity: ExecutionFidelity
    random_seed: int = Field(ge=0)
    start: UtcDatetime
    end: UtcDatetime
    splits: tuple[SplitWindow, ...] = Field(min_length=1)
    created_at: UtcDatetime

    @model_validator(mode="after")
    def _windows(self) -> Self:
        if self.end <= self.start:
            raise ValueError("backtest end must be after start")
        by_split: dict[SampleSplit, SplitWindow] = {}
        for window in self.splits:
            if window.split in by_split:
                raise ValueError(f"duplicate split {window.split}")
            if window.start < self.start or window.end > self.end:
                raise ValueError("a split must lie inside the backtest window")
            by_split[window.split] = window
        order = (SampleSplit.TRAIN, SampleSplit.VALIDATION, SampleSplit.HOLDOUT)
        present = [by_split[split] for split in order if split in by_split]
        for earlier, later in pairwise(present):
            if earlier.end > later.start:
                raise ValueError("train, validation and holdout must not overlap")
        if SampleSplit.HOLDOUT in by_split and SampleSplit.TRAIN not in by_split:
            raise ValueError("a holdout split requires a train split")
        return self


class DeploymentStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    HALTED = "halted"
    ENDED = "ended"


class CapitalEnvelope(DomainModel):
    """Hard money bound for one deployment. The risk engine enforces it."""

    max_dollars: NonNegativeMoney
    max_contracts: PositiveQuantity


class Deployment(DomainModel):
    deployment_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    strategy_spec_hash: ContentHash
    mode: TradingMode
    status: DeploymentStatus
    capital_envelope: CapitalEnvelope
    created_at: UtcDatetime
    approved_by: str | None = None
    activated_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _approval(self) -> Self:
        needs_approval = self.mode.uses_real_money and self.status in (
            DeploymentStatus.APPROVED,
            DeploymentStatus.ACTIVE,
        )
        if needs_approval and not self.approved_by:
            raise ValueError("an approved or active live deployment needs a human approver")
        if self.status is DeploymentStatus.ACTIVE and self.activated_at is None:
            raise ValueError("an active deployment needs activated_at")
        if self.activated_at is not None and self.activated_at < self.created_at:
            raise ValueError("activation cannot precede creation")
        return self
