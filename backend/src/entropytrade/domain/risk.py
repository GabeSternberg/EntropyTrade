"""Risk decisions and risk events (spec sections 22-24).

A :class:`RiskDecision` is fail-closed by construction: it must list the checks it ran, it can
only approve when every check passed, and a rejection must name at least one failed check.
"""

from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import RiskSeverity
from entropytrade.domain.ids import new_id
from entropytrade.domain.numeric import ZERO, ExactDecimal, Quantity
from entropytrade.domain.time import UtcDatetime


class RiskCheckResult(DomainModel):
    check_name: str = Field(min_length=1)
    passed: bool
    detail: str = ""
    observed: str | None = None
    limit: str | None = None


class RiskDecision(DomainModel):
    decision_id: UUID = Field(default_factory=new_id)
    intent_id: UUID
    approved: bool
    approved_quantity: Quantity
    checks: tuple[RiskCheckResult, ...] = Field(min_length=1)
    risk_config_version: str = Field(min_length=1)
    decided_at: UtcDatetime

    @model_validator(mode="after")
    def _check(self) -> Self:
        names = [c.check_name for c in self.checks]
        if len(names) != len(set(names)):
            raise ValueError("each risk check may appear only once per decision")
        all_passed = all(c.passed for c in self.checks)
        if self.approved and not all_passed:
            raise ValueError("cannot approve while a risk check failed")
        if not self.approved and all_passed:
            raise ValueError("a rejection must cite at least one failed check")
        if self.approved and self.approved_quantity <= ZERO:
            raise ValueError("an approval must allow a positive quantity")
        if not self.approved and self.approved_quantity != ZERO:
            raise ValueError("a rejection must allow zero quantity")
        return self

    @property
    def failed_checks(self) -> tuple[RiskCheckResult, ...]:
        return tuple(c for c in self.checks if not c.passed)


class RiskEventKind(StrEnum):
    LIMIT_BREACH = "limit_breach"
    KILL_SWITCH = "kill_switch"
    HALT = "halt"
    RESUME = "resume"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    STALE_DATA = "stale_data"
    SEQUENCE_GAP = "sequence_gap"
    RULES_CHANGED = "rules_changed"
    ORDER_STATE_UNKNOWN = "order_state_unknown"
    REPEATED_REJECTS = "repeated_rejects"
    DRIFT = "drift"


class RiskEvent(DomainModel):
    event_id: UUID = Field(default_factory=new_id)
    kind: RiskEventKind
    severity: RiskSeverity
    occurred_at: UtcDatetime
    message: str = Field(min_length=1)
    strategy_id: str | None = None
    deployment_id: UUID | None = None
    market_ticker: str | None = None
    intent_id: UUID | None = None
    client_order_id: UUID | None = None
    observed_value: ExactDecimal | None = None
    limit_value: ExactDecimal | None = None
