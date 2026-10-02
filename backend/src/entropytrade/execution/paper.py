"""Paper broker. Fills against a book. Never calls an exchange.

The only order it accepts is an ``ApprovedOrderIntent``. A raw strategy intent has no
method here. Unfilled immediate-or-cancel and fill-or-kill quantity is cancelled.
Good-till-canceled quantity that the book does not take rests, and the ledger reserves
its collateral.
"""

from decimal import Decimal
from uuid import UUID

from entropytrade.domain.enums import LiquidityRole, OutcomeSide, TimeInForce
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import ZERO, cost_per_contract, notional
from entropytrade.domain.orders import ApprovedOrderIntent, Fill, Order, OrderIntent, OrderState
from entropytrade.domain.time import UtcDatetime
from entropytrade.execution.fees import FeeSchedule, trade_fee
from entropytrade.portfolio.ledger import Ledger, LedgerError


class PaperBrokerError(ValueError):
    """The broker refused the order before any fill."""


def _price_is_marketable(side: OutcomeSide, level_price: Decimal, yes_limit: Decimal) -> bool:
    if side is OutcomeSide.YES:
        return level_price <= yes_limit
    return level_price >= yes_limit


def _slices(
    book: OrderBook,
    *,
    side: OutcomeSide,
    yes_limit: Decimal,
    quantity: Decimal,
) -> list[tuple[Decimal, Decimal]]:
    remaining = quantity
    taken: list[tuple[Decimal, Decimal]] = []
    levels = book.asks if side is OutcomeSide.YES else book.bids
    for level in levels:
        if remaining == ZERO or not _price_is_marketable(side, level.price, yes_limit):
            break
        size = min(remaining, level.quantity)
        taken.append((level.price, size))
        remaining -= size
    return taken


def _would_cross(book: OrderBook, *, side: OutcomeSide, yes_limit: Decimal) -> bool:
    if side is OutcomeSide.YES:
        return book.best_ask is not None and yes_limit >= book.best_ask.price
    return book.best_bid is not None and yes_limit <= book.best_bid.price


def _slice_cost(side: OutcomeSide, yes_price: Decimal, size: Decimal) -> Decimal:
    return notional(cost_per_contract(side, yes_price), size)


class PaperBroker:
    """Match one approved intent against the current book and record it on ``ledger``."""

    def __init__(self, ledger: Ledger, schedule: FeeSchedule) -> None:
        self._ledger = ledger
        self._schedule = schedule

    @property
    def schedule(self) -> FeeSchedule:
        return self._schedule

    def use_schedule(self, schedule: FeeSchedule) -> None:
        """Replace the schedule before the next fill. Replay uses this per series."""
        self._schedule = schedule

    def submit(
        self,
        approved: ApprovedOrderIntent,
        book: OrderBook,
        *,
        now: UtcDatetime,
    ) -> Order:
        if not isinstance(approved, ApprovedOrderIntent):
            raise PaperBrokerError("only an approved intent can be submitted")
        intent = approved.intent
        if intent.contract.market_ticker != book.market_ticker:
            raise PaperBrokerError("book is for a different market")
        if book.is_crossed:
            raise PaperBrokerError("refusing a crossed book")
        walk = approved.quantity
        if intent.reduce_only:
            walk = _reduce_cap(self._ledger, intent, walk)
            if walk == ZERO:
                rejected = _spawn(
                    intent,
                    quantity=approved.quantity,
                    state=OrderState.REJECTED,
                    now=now,
                )
                self._ledger.remember_order(rejected)
                return rejected
        order = _spawn(intent, quantity=approved.quantity, state=OrderState.SUBMITTING, now=now)
        self._ledger.remember_order(order)
        if intent.post_only:
            if _would_cross(book, side=intent.contract.side, yes_limit=intent.yes_price):
                return self._finish(order, OrderState.REJECTED, now=now)
            return self._rest(order, now=now)
        planned = _slices(
            book,
            side=intent.contract.side,
            yes_limit=intent.yes_price,
            quantity=walk,
        )
        filled = sum((size for _, size in planned), ZERO)
        if intent.time_in_force is TimeInForce.FILL_OR_KILL and filled < walk:
            return self._finish(order, OrderState.CANCELLED, now=now)
        if not _affordable(self._ledger, intent.contract.side, planned, self._schedule):
            return self._finish(order, OrderState.REJECTED, now=now)
        for index, (price, size) in enumerate(planned):
            order = self._fill(order, price=price, size=size, index=index, now=now)
        if order.remaining_quantity == ZERO:
            return order
        if intent.time_in_force is TimeInForce.IMMEDIATE_OR_CANCEL or intent.reduce_only:
            return self._finish(order, OrderState.CANCELLED, now=now)
        return self._rest(order, now=now)

    def _fill(
        self,
        order: Order,
        *,
        price: Decimal,
        size: Decimal,
        index: int,
        now: UtcDatetime,
    ) -> Order:
        fee = trade_fee(
            self._schedule,
            yes_price=price,
            quantity=size,
            role=LiquidityRole.TAKER,
        )
        fill = Fill(
            fill_id=f"paper-{order.client_order_id}-{index}",
            exchange_order_id=str(order.client_order_id),
            client_order_id=order.client_order_id,
            contract=order.contract,
            yes_price=price,
            quantity=size,
            fee=fee,
            liquidity_role=LiquidityRole.TAKER,
            executed_at=now,
            received_at=now,
        )
        self._ledger.apply_fill(fill)
        updated = order.with_fill(size, at=now)
        self._ledger.remember_order(updated)
        return updated

    def _rest(self, order: Order, *, now: UtcDatetime) -> Order:
        if order.state is OrderState.SUBMITTING:
            order = order.with_state(OrderState.RESTING, at=now)
        remaining_cost = notional(
            cost_per_contract(order.contract.side, order.yes_price),
            order.remaining_quantity,
        )
        try:
            self._ledger.reserve(order.client_order_id, remaining_cost)
        except LedgerError:
            self._ledger.release(order.client_order_id)
            target = OrderState.REJECTED if order.filled_quantity == ZERO else OrderState.CANCELLED
            return self._finish(order, target, now=now)
        self._ledger.remember_order(order)
        return order

    def _finish(self, order: Order, state: OrderState, *, now: UtcDatetime) -> Order:
        self._ledger.release(order.client_order_id)
        if order.state is not state:
            order = order.with_state(state, at=now)
        self._ledger.remember_order(order)
        return order


def _reduce_cap(ledger: Ledger, intent: OrderIntent, quantity: Decimal) -> Decimal:
    held = ledger.position(intent.contract.market_ticker)
    if held is None or held.contract.side is intent.contract.side:
        return ZERO
    return min(quantity, held.quantity)


def _affordable(
    ledger: Ledger,
    side: OutcomeSide,
    planned: list[tuple[Decimal, Decimal]],
    schedule: FeeSchedule,
) -> bool:
    cost = ZERO
    fee = ZERO
    for price, size in planned:
        cost += _slice_cost(side, price, size)
        fee += trade_fee(schedule, yes_price=price, quantity=size, role=LiquidityRole.TAKER)
    return cost + fee <= ledger.available_cash


def _spawn(
    intent: OrderIntent,
    *,
    quantity: Decimal,
    state: OrderState,
    now: UtcDatetime,
) -> Order:
    order = Order(
        client_order_id=UUID(int=intent.intent_id.int),
        intent_id=intent.intent_id,
        contract=intent.contract,
        yes_price=intent.yes_price,
        requested_quantity=quantity,
        state=OrderState.CREATED,
        created_at=now,
        updated_at=now,
    )
    order = order.with_state(OrderState.RISK_APPROVED, at=now).with_state(
        OrderState.SUBMITTING, at=now
    )
    if state is OrderState.SUBMITTING:
        return order
    return order.with_state(state, at=now)
