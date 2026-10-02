"""Order intents, requests, orders, fills and the order state machine (spec section 18).

Flow: ``OrderIntent`` (strategy) -> ``RiskDecision`` -> ``ApprovedOrderIntent`` ->
``OrderRequest`` (execution engine, idempotent ``client_order_id``) -> ``Order`` (exchange
state) -> ``Fill``.

Prices are always YES-denominated (Kalshi's convention: an order at ``p`` with outcome NO pays
``1 - p`` per contract). ``side`` is the outcome the order makes us long; closing a YES
position is expressed as buying NO with ``reduce_only=True``.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Final, Self
from uuid import UUID

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import LiquidityRole, TimeInForce
from entropytrade.domain.ids import new_id
from entropytrade.domain.market import Contract
from entropytrade.domain.numeric import (
    ZERO,
    NonNegativeMoney,
    OrderPrice,
    PositiveQuantity,
    Price,
    Quantity,
    cost_per_contract,
    notional,
    parse_quantity,
)
from entropytrade.domain.risk import RiskDecision
from entropytrade.domain.signals import EdgeEstimate
from entropytrade.domain.time import UtcDatetime


class OrderState(StrEnum):
    CREATED = "created"
    RISK_APPROVED = "risk_approved"
    SUBMITTING = "submitting"
    ACKNOWLEDGED = "acknowledged"
    RESTING = "resting"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_ORDER_STATES

    @property
    def may_be_live_on_exchange(self) -> bool:
        """States in which the exchange may hold resting quantity for us."""
        return self in _POSSIBLY_LIVE


OS = OrderState

TERMINAL_ORDER_STATES: Final = frozenset({OS.FILLED, OS.CANCELLED, OS.REJECTED})

_POSSIBLY_LIVE: Final = frozenset(
    {OS.SUBMITTING, OS.ACKNOWLEDGED, OS.RESTING, OS.PARTIALLY_FILLED, OS.CANCEL_PENDING, OS.UNKNOWN}
)

ORDER_TRANSITIONS: Final[dict[OrderState, frozenset[OrderState]]] = {
    OS.CREATED: frozenset({OS.RISK_APPROVED, OS.REJECTED, OS.CANCELLED}),
    OS.RISK_APPROVED: frozenset({OS.SUBMITTING, OS.CANCELLED}),
    OS.SUBMITTING: frozenset(
        {
            OS.ACKNOWLEDGED,
            OS.RESTING,
            OS.PARTIALLY_FILLED,
            OS.FILLED,
            OS.CANCELLED,
            OS.REJECTED,
            OS.UNKNOWN,
        }
    ),
    OS.ACKNOWLEDGED: frozenset(
        {OS.RESTING, OS.PARTIALLY_FILLED, OS.FILLED, OS.CANCEL_PENDING, OS.CANCELLED, OS.UNKNOWN}
    ),
    OS.RESTING: frozenset(
        {OS.PARTIALLY_FILLED, OS.FILLED, OS.CANCEL_PENDING, OS.CANCELLED, OS.UNKNOWN}
    ),
    OS.PARTIALLY_FILLED: frozenset(
        {OS.PARTIALLY_FILLED, OS.FILLED, OS.CANCEL_PENDING, OS.CANCELLED, OS.UNKNOWN}
    ),
    OS.CANCEL_PENDING: frozenset({OS.PARTIALLY_FILLED, OS.FILLED, OS.CANCELLED, OS.UNKNOWN}),
    OS.UNKNOWN: frozenset(
        {OS.ACKNOWLEDGED, OS.RESTING, OS.PARTIALLY_FILLED, OS.FILLED, OS.CANCELLED, OS.REJECTED}
    ),
    OS.FILLED: frozenset(),
    OS.CANCELLED: frozenset(),
    OS.REJECTED: frozenset(),
}
"""``UNKNOWN`` (e.g. submit timeout) leaves only via reconciliation with exchange state."""


class InvalidOrderTransitionError(ValueError):
    pass


def check_order_transition(source: OrderState, target: OrderState) -> None:
    if target not in ORDER_TRANSITIONS[source]:
        raise InvalidOrderTransitionError(f"order cannot move {source} -> {target}")


class OrderIntent(DomainModel):
    """What a strategy wants. Carries no exchange identifiers and cannot reach the exchange."""

    intent_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    deployment_id: UUID | None = None
    contract: Contract
    yes_price: OrderPrice
    quantity: PositiveQuantity
    time_in_force: TimeInForce
    post_only: bool = False
    reduce_only: bool = False
    expires_at: UtcDatetime | None = None
    decision_time: UtcDatetime
    edge: EdgeEstimate | None = None
    prediction_id: UUID | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.decision_time:
            raise ValueError("an intent must expire after its decision time")
        if self.post_only and self.time_in_force is not TimeInForce.GOOD_TILL_CANCELED:
            raise ValueError("post-only orders must rest (good_till_canceled)")
        return self

    @property
    def price_per_contract(self) -> Decimal:
        return cost_per_contract(self.contract.side, self.yes_price)

    @property
    def max_cost(self) -> Decimal:
        """Upper bound on capital consumed by this intent, before fees."""
        return notional(self.price_per_contract, self.quantity)


class ApprovedOrderIntent(DomainModel):
    """An intent paired with the approving risk decision. The only input execution accepts."""

    intent: OrderIntent
    decision: RiskDecision

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.decision.intent_id != self.intent.intent_id:
            raise ValueError("risk decision belongs to a different intent")
        if not self.decision.approved:
            raise ValueError("risk decision did not approve this intent")
        if self.decision.approved_quantity > self.intent.quantity:
            raise ValueError("risk cannot approve more than the intent requested")
        if self.decision.decided_at < self.intent.decision_time:
            raise ValueError("risk decision cannot precede the intent")
        return self

    @property
    def quantity(self) -> Decimal:
        return self.decision.approved_quantity


class OrderRequest(DomainModel):
    """An order the execution engine will send, keyed by an idempotent client order id."""

    client_order_id: UUID = Field(default_factory=new_id)
    intent_id: UUID
    contract: Contract
    yes_price: OrderPrice
    quantity: PositiveQuantity
    time_in_force: TimeInForce
    post_only: bool = False
    reduce_only: bool = False
    expires_at: UtcDatetime | None = None
    created_at: UtcDatetime

    @classmethod
    def from_approved(
        cls, approved: ApprovedOrderIntent, *, created_at: UtcDatetime
    ) -> "OrderRequest":
        intent = approved.intent
        return cls(
            intent_id=intent.intent_id,
            contract=intent.contract,
            yes_price=intent.yes_price,
            quantity=approved.quantity,
            time_in_force=intent.time_in_force,
            post_only=intent.post_only,
            reduce_only=intent.reduce_only,
            expires_at=intent.expires_at,
            created_at=created_at,
        )


class Order(DomainModel):
    """Our view of an order's lifecycle. Exchange state wins on reconciliation."""

    client_order_id: UUID
    exchange_order_id: str | None = None
    intent_id: UUID
    contract: Contract
    yes_price: OrderPrice
    requested_quantity: PositiveQuantity
    filled_quantity: Quantity = Decimal(0)
    state: OrderState
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.filled_quantity > self.requested_quantity:
            raise ValueError("filled quantity exceeds requested quantity")
        filled = self.filled_quantity
        match self.state:
            case OS.CREATED | OS.RISK_APPROVED | OS.SUBMITTING | OS.REJECTED if filled != ZERO:
                raise ValueError(f"a {self.state} order cannot have fills")
            case OS.FILLED if filled != self.requested_quantity:
                raise ValueError("a filled order must be completely filled")
            case OS.PARTIALLY_FILLED if not ZERO < filled < self.requested_quantity:
                raise ValueError("a partially filled order needs 0 < filled < requested")
            case _:
                pass
        return self

    @property
    def remaining_quantity(self) -> Decimal:
        return self.requested_quantity - self.filled_quantity

    @property
    def may_be_live_on_exchange(self) -> bool:
        return self.state.may_be_live_on_exchange

    def with_state(self, state: OrderState, *, at: UtcDatetime) -> "Order":
        check_order_transition(self.state, state)
        return self.revalidated(state=state, updated_at=at)

    def with_fill(self, quantity: Decimal, *, at: UtcDatetime) -> "Order":
        """Apply a fill; moves to PARTIALLY_FILLED or FILLED."""
        fill_qty = parse_quantity(quantity)
        if fill_qty <= ZERO:
            raise ValueError("fill quantity must be positive")
        filled = self.filled_quantity + fill_qty
        if filled > self.requested_quantity:
            raise ValueError("fill would exceed the requested quantity")
        target = OS.FILLED if filled == self.requested_quantity else OS.PARTIALLY_FILLED
        check_order_transition(self.state, target)
        return self.revalidated(state=target, filled_quantity=filled, updated_at=at)


class Fill(DomainModel):
    fill_id: str = Field(min_length=1)
    trade_id: str | None = None
    exchange_order_id: str = Field(min_length=1)
    client_order_id: UUID | None = None
    contract: Contract
    yes_price: Price
    quantity: PositiveQuantity
    fee: NonNegativeMoney
    liquidity_role: LiquidityRole
    executed_at: UtcDatetime
    received_at: UtcDatetime | None = None

    @property
    def price_per_contract(self) -> Decimal:
        return cost_per_contract(self.contract.side, self.yes_price)

    @property
    def cost(self) -> Decimal:
        """Cash paid for the contracts, excluding fees."""
        return notional(self.price_per_contract, self.quantity)
