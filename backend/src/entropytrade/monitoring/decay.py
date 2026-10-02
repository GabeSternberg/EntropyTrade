"""Decay from paper and shadow comparisons, and a downward lifecycle move.

A comparison is scored only when ``difference`` is set. That value is the
next print minus the price that was filled or would have been paid. A gap
has a price and no later print, so its difference is missing and it is
left out.

Decay is true when at least ``window`` scored rows exist and the mean of
the last ``window`` of them is strictly below the caller's threshold.
Matching the threshold is not decay. Fewer scored rows than the window is
not decay.

A decay flag proposes one allow-listed move that does not raise capital
rank and is never ``live`` or ``live_small``. ``live`` goes to ``degraded``.
``paper`` goes to ``paused``. ``backtested`` has neither of those edges, so
it goes to ``research``. ``retired`` has no move. The actor is an agent and
the transition carries no approval, which the lifecycle type already
permits for a decrease. The same actor still cannot apply an increase.

Size is halved on the 0.01 contract grid, rounding down, and is never
returned larger. A quantity that would halve to zero stays put; the
lifecycle move is what stops it.

Comparisons do not carry a model, a calibration series, a backtest equity
path, or a feature vector. Those diagnostics from the spec are not scored
here. The mean difference is the fill-quality number.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from entropytrade.domain.enums import ActorKind
from entropytrade.domain.lifecycle import (
    Actor,
    LifecycleState,
    LifecycleTransition,
    capital_rank,
    is_allowed,
)
from entropytrade.domain.numeric import QUANTITY_QUANTUM, parse_quantity, to_decimal
from entropytrade.execution.shadow import ShadowComparison

# First legal non-increasing target wins. ``live`` and ``live_small`` are absent.
_DOWNWARD: dict[LifecycleState, tuple[LifecycleState, ...]] = {
    LifecycleState.LIVE: (
        LifecycleState.DEGRADED,
        LifecycleState.PAUSED,
        LifecycleState.RETIRED,
    ),
    LifecycleState.LIVE_SMALL: (
        LifecycleState.DEGRADED,
        LifecycleState.PAUSED,
        LifecycleState.RETIRED,
    ),
    LifecycleState.DEGRADED: (LifecycleState.PAUSED, LifecycleState.RETIRED),
    LifecycleState.PAPER: (
        LifecycleState.PAUSED,
        LifecycleState.RESEARCH,
        LifecycleState.RETIRED,
    ),
    LifecycleState.SHADOW_LIVE: (
        LifecycleState.PAUSED,
        LifecycleState.PAPER,
        LifecycleState.RETIRED,
    ),
    LifecycleState.VALIDATED: (LifecycleState.RESEARCH, LifecycleState.RETIRED),
    LifecycleState.BACKTESTED: (LifecycleState.RESEARCH, LifecycleState.RETIRED),
    LifecycleState.RESEARCH: (LifecycleState.RETIRED,),
    LifecycleState.DRAFT: (LifecycleState.RETIRED,),
    LifecycleState.PAUSED: (LifecycleState.RETIRED,),
    LifecycleState.RETIRED: (),
}


def _window(window: int) -> int:
    if window < 1:
        raise ValueError("window must be an integer of at least 1")
    return window


def scored_differences(comparisons: Sequence[ShadowComparison]) -> tuple[Decimal, ...]:
    """Differences that are present. Gaps and unpriced rows are omitted."""
    return tuple(
        row.difference for row in comparisons if row.difference is not None and not row.gap
    )


def recent_mean(
    comparisons: Sequence[ShadowComparison],
    *,
    window: int,
) -> Decimal | None:
    """Mean of the last ``window`` scored differences, or None if there are fewer."""
    size = _window(window)
    values = scored_differences(comparisons)
    if len(values) < size:
        return None
    recent = values[-size:]
    return sum(recent, Decimal(0)) / Decimal(size)


def is_decayed(
    comparisons: Sequence[ShadowComparison],
    *,
    window: int,
    threshold: Decimal,
) -> bool:
    """True when the recent mean is strictly worse than ``threshold``."""
    limit = to_decimal(threshold)
    mean = recent_mean(comparisons, window=window)
    if mean is None:
        return False
    return mean < limit


def downward_state(state: LifecycleState) -> LifecycleState | None:
    """The next legal state that does not increase capital and is not a live tier."""
    for target in _DOWNWARD[state]:
        if target in (LifecycleState.LIVE, LifecycleState.LIVE_SMALL):
            continue
        if not is_allowed(state, target):
            continue
        if capital_rank(target) > capital_rank(state):
            continue
        return target
    return None


def propose_downward(
    *,
    state: LifecycleState,
    strategy_id: str,
    strategy_version: int,
    occurred_at: datetime,
    reason: str,
    decayed: bool,
) -> LifecycleTransition | None:
    """An agent-applied downward transition, or None when there is no decay or no edge."""
    if not decayed:
        return None
    target = downward_state(state)
    if target is None:
        return None
    return LifecycleTransition(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        from_state=state,
        to_state=target,
        actor=Actor(kind=ActorKind.AGENT, actor_id="decay"),
        reason=reason,
        occurred_at=occurred_at,
    )


def reduced_quantity(quantity: Decimal, *, decayed: bool) -> Decimal:
    """Half of ``quantity`` when decayed, never a larger count, never below zero.

    A positive quantity that rounds down to zero is left unchanged.
    """
    current = parse_quantity(quantity)
    if not decayed:
        return current
    halved = (current / Decimal(2)).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
    if halved <= 0 or halved > current:
        return current
    return halved
