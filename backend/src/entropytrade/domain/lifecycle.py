"""Strategy promotion lifecycle (spec section 16).

Transitions are an explicit allow-list. Moving *up* into a real-capital tier (``LIVE_SMALL``,
``LIVE``) always needs a recorded human approval; moving down (``DEGRADED``, ``PAUSED``,
``RETIRED``) never does, so deterministic risk reductions can never be blocked waiting for a
person. Agents can propose transitions but cannot supply a :class:`HumanApproval`.
"""

from enum import StrEnum
from typing import Final, Self
from uuid import UUID

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import ActorKind
from entropytrade.domain.ids import new_id
from entropytrade.domain.time import UtcDatetime


class LifecycleState(StrEnum):
    DRAFT = "draft"
    RESEARCH = "research"
    BACKTESTED = "backtested"
    VALIDATED = "validated"
    PAPER = "paper"
    SHADOW_LIVE = "shadow_live"
    LIVE_SMALL = "live_small"
    LIVE = "live"
    DEGRADED = "degraded"
    PAUSED = "paused"
    RETIRED = "retired"


S = LifecycleState

ALLOWED_TRANSITIONS: Final[dict[LifecycleState, frozenset[LifecycleState]]] = {
    S.DRAFT: frozenset({S.RESEARCH, S.RETIRED}),
    S.RESEARCH: frozenset({S.BACKTESTED, S.RETIRED}),
    S.BACKTESTED: frozenset({S.VALIDATED, S.RESEARCH, S.RETIRED}),
    S.VALIDATED: frozenset({S.PAPER, S.RESEARCH, S.RETIRED}),
    S.PAPER: frozenset({S.SHADOW_LIVE, S.PAUSED, S.RESEARCH, S.RETIRED}),
    S.SHADOW_LIVE: frozenset({S.LIVE_SMALL, S.PAPER, S.PAUSED, S.RETIRED}),
    S.LIVE_SMALL: frozenset({S.LIVE, S.DEGRADED, S.PAUSED, S.RETIRED}),
    S.LIVE: frozenset({S.LIVE_SMALL, S.DEGRADED, S.PAUSED, S.RETIRED}),
    S.DEGRADED: frozenset({S.LIVE_SMALL, S.PAUSED, S.RETIRED}),
    S.PAUSED: frozenset({S.PAPER, S.SHADOW_LIVE, S.LIVE_SMALL, S.RESEARCH, S.RETIRED}),
    S.RETIRED: frozenset(),
}

_CAPITAL_RANK: Final[dict[LifecycleState, int]] = {
    S.DEGRADED: 1,
    S.LIVE_SMALL: 2,
    S.LIVE: 3,
}

REAL_CAPITAL_STATES: Final = frozenset(_CAPITAL_RANK)


def capital_rank(state: LifecycleState) -> int:
    """0 for states that never trade real money; higher means a larger real-capital tier."""
    return _CAPITAL_RANK.get(state, 0)


def is_allowed(source: LifecycleState, target: LifecycleState) -> bool:
    return target in ALLOWED_TRANSITIONS[source]


def requires_human_approval(source: LifecycleState, target: LifecycleState) -> bool:
    """Any increase in real-capital tier needs a human; decreases never do."""
    return capital_rank(target) > capital_rank(source)


class Actor(DomainModel):
    kind: ActorKind
    actor_id: str = Field(min_length=1)


class HumanApproval(DomainModel):
    """A person's sign-off. There is deliberately no way to construct one for an agent."""

    approval_id: UUID = Field(default_factory=new_id)
    approver_id: str = Field(min_length=1)
    approved_at: UtcDatetime
    note: str = ""


class LifecycleTransition(DomainModel):
    transition_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    from_state: LifecycleState
    to_state: LifecycleState
    actor: Actor
    reason: str = Field(min_length=1)
    occurred_at: UtcDatetime
    approval: HumanApproval | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not is_allowed(self.from_state, self.to_state):
            raise ValueError(f"transition {self.from_state} -> {self.to_state} is not allowed")
        if requires_human_approval(self.from_state, self.to_state):
            if self.approval is None:
                raise ValueError(f"{self.from_state} -> {self.to_state} requires human approval")
            if self.actor.kind is ActorKind.AGENT:
                raise ValueError("an agent cannot apply a capital-increasing transition")
            if self.approval.approved_at > self.occurred_at:
                raise ValueError("approval must precede the transition")
        return self
