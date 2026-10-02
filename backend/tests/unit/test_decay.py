"""Decay flags and downward lifecycle moves. No socket and no submit."""

from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.domain.enums import ActorKind
from entropytrade.domain.lifecycle import (
    HumanApproval,
    LifecycleState,
    LifecycleTransition,
)
from entropytrade.execution.shadow import ShadowComparison
from entropytrade.monitoring.decay import (
    downward_state,
    is_decayed,
    propose_downward,
    reduced_quantity,
    scored_differences,
)
from tests.support import utc

FORBIDDEN = (
    "attempt_submit",
    "KalshiGateway",
    "httpx",
    "kalshi",
    "api.elections.kalshi.com",
    "demo-api.kalshi.co",
)


def _row(difference: str | None, *, gap: bool = False) -> ShadowComparison:
    if gap:
        return ShadowComparison(
            filled=True,
            price=Decimal("0.40"),
            next_print=None,
            difference=None,
        )
    if difference is None:
        return ShadowComparison(
            filled=False,
            price=None,
            next_print=None,
            difference=None,
        )
    value = Decimal(difference)
    return ShadowComparison(
        filled=True,
        price=Decimal("0.40"),
        next_print=Decimal("0.40") + value,
        difference=value,
    )


def test_decay_uses_the_recent_non_gap_mean() -> None:
    rows = (
        _row("-0.10"),
        _row(None, gap=True),
        _row("0.04"),
        _row("-0.02"),
    )
    assert scored_differences(rows) == (Decimal("-0.10"), Decimal("0.04"), Decimal("-0.02"))
    # Last two scored rows average (0.04 + -0.02) / 2 = 0.01, which is below 0.02.
    assert is_decayed(rows, window=2, threshold=Decimal("0.02"))
    assert not is_decayed(rows, window=2, threshold=Decimal("0.01"))
    assert is_decayed(rows, window=3, threshold=Decimal("0"))
    assert not is_decayed(rows, window=4, threshold=Decimal("-1"))
    with pytest.raises(ValueError, match="window"):
        is_decayed(rows, window=0, threshold=Decimal("0"))
    with pytest.raises(ValueError, match="float"):
        is_decayed(rows, window=2, threshold=0.01)  # type: ignore[arg-type]


def test_equal_to_the_threshold_is_not_decay() -> None:
    rows = (_row("-0.02"), _row("0.02"))
    assert not is_decayed(rows, window=2, threshold=Decimal("0"))


def test_downward_targets_never_include_a_live_tier() -> None:
    assert downward_state(LifecycleState.LIVE) is LifecycleState.DEGRADED
    assert downward_state(LifecycleState.LIVE_SMALL) is LifecycleState.DEGRADED
    assert downward_state(LifecycleState.DEGRADED) is LifecycleState.PAUSED
    assert downward_state(LifecycleState.PAPER) is LifecycleState.PAUSED
    assert downward_state(LifecycleState.SHADOW_LIVE) is LifecycleState.PAUSED
    assert downward_state(LifecycleState.BACKTESTED) is LifecycleState.RESEARCH
    assert downward_state(LifecycleState.VALIDATED) is LifecycleState.RESEARCH
    assert downward_state(LifecycleState.PAUSED) is LifecycleState.RETIRED
    assert downward_state(LifecycleState.RETIRED) is None
    for state in LifecycleState:
        target = downward_state(state)
        assert target not in (LifecycleState.LIVE, LifecycleState.LIVE_SMALL)


def test_an_agent_can_apply_the_downward_move_and_not_an_upward_one() -> None:
    moved = propose_downward(
        state=LifecycleState.PAPER,
        strategy_id="phl",
        strategy_version=1,
        occurred_at=utc(2026, 10, 2, 12),
        reason="recent fill quality is below the threshold",
        decayed=True,
    )
    assert moved is not None
    assert moved.to_state is LifecycleState.PAUSED
    assert moved.actor.kind is ActorKind.AGENT
    assert moved.approval is None
    assert (
        propose_downward(
            state=LifecycleState.PAPER,
            strategy_id="phl",
            strategy_version=1,
            occurred_at=utc(2026, 10, 2, 12),
            reason="no decay",
            decayed=False,
        )
        is None
    )
    assert (
        propose_downward(
            state=LifecycleState.RETIRED,
            strategy_id="phl",
            strategy_version=1,
            occurred_at=utc(2026, 10, 2, 12),
            reason="already retired",
            decayed=True,
        )
        is None
    )
    with pytest.raises(ValueError, match="agent"):
        LifecycleTransition(
            strategy_id="phl",
            strategy_version=1,
            from_state=LifecycleState.SHADOW_LIVE,
            to_state=LifecycleState.LIVE_SMALL,
            actor=moved.actor,
            reason="raise capital",
            occurred_at=utc(2026, 10, 2, 12),
            approval=HumanApproval(approver_id="gabe", approved_at=utc(2026, 10, 2, 11)),
        )


def test_size_is_halved_and_never_increased() -> None:
    assert reduced_quantity(Decimal("1.00"), decayed=True) == Decimal("0.50")
    assert reduced_quantity(Decimal("0.03"), decayed=True) == Decimal("0.01")
    assert reduced_quantity(Decimal("0.01"), decayed=True) == Decimal("0.01")
    assert reduced_quantity(Decimal("1.00"), decayed=False) == Decimal("1.00")
    assert reduced_quantity(Decimal("0"), decayed=True) == Decimal("0.00")


def test_decay_module_does_not_name_a_submit_path() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/monitoring/decay.py")
        .read_text(encoding="utf-8")
    )
    for name in FORBIDDEN:
        assert name not in text
