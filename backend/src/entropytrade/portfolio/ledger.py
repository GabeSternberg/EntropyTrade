"""Cash, net positions, fills and settlements.

Buying the opposite outcome nets the position: a YES holding plus a NO buy collapses
the overlap into one dollar per contract. Equity is cash plus open cost, which equals
starting cash plus realized P&L, fees included. The same fill id is applied once.
"""

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID

from entropytrade.domain.enums import MarketResult, OutcomeSide
from entropytrade.domain.market import Contract
from entropytrade.domain.numeric import MONEY_QUANTUM, ONE, ZERO, notional, parse_money
from entropytrade.domain.orders import Fill, Order
from entropytrade.domain.portfolio import (
    PortfolioSnapshot,
    Position,
    Settlement,
    SnapshotSource,
    settlement_payout,
    settlement_value_for,
)
from entropytrade.domain.time import UtcDatetime


class LedgerError(ValueError):
    """The ledger refused a fill or a settlement."""


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


class Ledger:
    """One account. Paper and reconciliation share it; it does not talk to an exchange."""

    def __init__(self, cash: Decimal, *, as_of: UtcDatetime) -> None:
        self.starting_cash = parse_money(cash)
        self.cash = self.starting_cash
        self.realized_pnl = parse_money(ZERO)
        self.fees_paid = parse_money(ZERO)
        self.peak_equity = self.starting_cash
        self.as_of = as_of
        self._positions: dict[str, Position] = {}
        self._fills: dict[str, Fill] = {}
        self._orders: dict[UUID, Order] = {}
        self._collateral: dict[UUID, Decimal] = {}
        self._settlements: list[Settlement] = []

    @property
    def positions(self) -> tuple[Position, ...]:
        return tuple(self._positions[ticker] for ticker in sorted(self._positions))

    @property
    def resting_collateral(self) -> Decimal:
        return _money(sum(self._collateral.values(), ZERO))

    @property
    def available_cash(self) -> Decimal:
        return _money(self.cash - self.resting_collateral)

    def equity(self) -> Decimal:
        open_cost = sum((position.total_cost for position in self._positions.values()), ZERO)
        return _money(self.cash + open_cost)

    def drawdown(self) -> Decimal:
        return _money(self.peak_equity - self.equity())

    def position(self, market_ticker: str) -> Position | None:
        return self._positions.get(market_ticker)

    def fills(self) -> tuple[Fill, ...]:
        return tuple(self._fills.values())

    def apply_fill(self, fill: Fill) -> bool:
        """Apply ``fill``. Returns False when this id was already applied."""
        if fill.fill_id in self._fills:
            return False
        self._fills[fill.fill_id] = fill
        self.cash = _money(self.cash - fill.cost - fill.fee)
        self.fees_paid = _money(self.fees_paid + fill.fee)
        self.realized_pnl = _money(self.realized_pnl - fill.fee)
        existing = self._positions.get(fill.contract.market_ticker)
        if existing is None or existing.contract.side is fill.contract.side:
            self._increase(existing, fill)
        else:
            self._net(existing, fill)
        self.as_of = fill.executed_at
        self._touch_peak()
        return True

    def remember_order(self, order: Order) -> None:
        self._orders[order.client_order_id] = order

    def order(self, client_order_id: UUID) -> Order | None:
        return self._orders.get(client_order_id)

    def orders(self) -> tuple[Order, ...]:
        return tuple(self._orders[key] for key in sorted(self._orders, key=str))

    def reserve(self, client_order_id: UUID, amount: Decimal) -> None:
        reserved = parse_money(amount)
        if reserved < ZERO:
            raise LedgerError("collateral cannot be negative")
        if reserved > self.available_cash + self._collateral.get(client_order_id, ZERO):
            raise LedgerError("not enough free cash to reserve collateral")
        self._collateral[client_order_id] = reserved

    def release(self, client_order_id: UUID) -> None:
        self._collateral.pop(client_order_id, None)

    def settle(self, market_ticker: str, result: MarketResult, *, at: UtcDatetime) -> Settlement:
        position = self._positions.get(market_ticker)
        if position is None or position.is_flat:
            raise LedgerError(f"{market_ticker} has no open position to settle")
        yes_value = settlement_value_for(result)
        payout = settlement_payout(position.contract.side, position.quantity, yes_value)
        self.cash = _money(self.cash + payout)
        self.realized_pnl = _money(self.realized_pnl + payout - position.total_cost)
        yes_quantity = position.quantity if position.contract.side is OutcomeSide.YES else ZERO
        no_quantity = position.quantity if position.contract.side is OutcomeSide.NO else ZERO
        settlement = Settlement(
            market_ticker=market_ticker,
            result=result,
            yes_value=yes_value,
            yes_quantity=yes_quantity,
            no_quantity=no_quantity,
            revenue=payout,
            settled_at=at,
        )
        self._settlements.append(settlement)
        del self._positions[market_ticker]
        self.as_of = at
        self._touch_peak()
        return settlement

    def snapshot(self, *, source: SnapshotSource = SnapshotSource.PAPER) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            as_of=self.as_of,
            source=source,
            cash_balance=self.cash,
            resting_order_collateral=self.resting_collateral,
            positions=self.positions,
        )

    def dump(self) -> dict[str, object]:
        return {
            "starting_cash": str(self.starting_cash),
            "cash": str(self.cash),
            "realized_pnl": str(self.realized_pnl),
            "fees_paid": str(self.fees_paid),
            "peak_equity": str(self.peak_equity),
            "as_of": self.as_of.isoformat(),
            "positions": [position.model_dump(mode="json") for position in self.positions],
            "fills": [fill.model_dump(mode="json") for fill in self._fills.values()],
            "orders": [order.model_dump(mode="json") for order in self.orders()],
            "collateral": {str(key): str(amount) for key, amount in self._collateral.items()},
            "settlements": [item.model_dump(mode="json") for item in self._settlements],
        }

    @classmethod
    def load(cls, payload: dict[str, object]) -> "Ledger":
        as_of = _parse_time(payload.get("as_of"))
        ledger = cls(_decimal(payload, "starting_cash"), as_of=as_of)
        ledger.cash = parse_money(_text(payload, "cash"))
        ledger.realized_pnl = parse_money(_text(payload, "realized_pnl"))
        ledger.fees_paid = parse_money(_text(payload, "fees_paid"))
        ledger.peak_equity = parse_money(_text(payload, "peak_equity"))
        positions = _list(payload, "positions")
        fills = _list(payload, "fills")
        orders = _list(payload, "orders")
        settlements = _list(payload, "settlements")
        collateral = payload.get("collateral")
        if not isinstance(collateral, dict):
            raise LedgerError("ledger payload is missing collateral")
        for raw in positions:
            position = Position.model_validate(raw)
            ledger._positions[position.contract.market_ticker] = position
        for raw in fills:
            fill = Fill.model_validate(raw)
            ledger._fills[fill.fill_id] = fill
        for raw in orders:
            order = Order.model_validate(raw)
            ledger._orders[order.client_order_id] = order
        for key, amount in collateral.items():
            ledger._collateral[UUID(str(key))] = parse_money(str(amount))
        for raw in settlements:
            ledger._settlements.append(Settlement.model_validate(raw))
        return ledger

    def _increase(self, existing: Position | None, fill: Fill) -> None:
        added = fill.quantity
        cost = fill.cost
        if existing is None:
            self._positions[fill.contract.market_ticker] = Position(
                contract=fill.contract,
                quantity=added,
                total_cost=cost,
                fees_paid=fill.fee,
                as_of=fill.executed_at,
            )
            return
        self._positions[fill.contract.market_ticker] = existing.revalidated(
            quantity=existing.quantity + added,
            total_cost=_money(existing.total_cost + cost),
            fees_paid=_money(existing.fees_paid + fill.fee),
            as_of=fill.executed_at,
        )

    def _net(self, existing: Position, fill: Fill) -> None:
        matched = min(existing.quantity, fill.quantity)
        closed_cost = _money(existing.total_cost * matched / existing.quantity)
        matched_cost = _money(fill.cost * matched / fill.quantity)
        payoff = notional(ONE, matched)
        self.cash = _money(self.cash + payoff)
        self.realized_pnl = _money(self.realized_pnl + payoff - closed_cost - matched_cost)
        left_qty = existing.quantity - matched
        open_qty = fill.quantity - matched
        ticker = existing.contract.market_ticker
        if left_qty > ZERO:
            self._positions[ticker] = existing.revalidated(
                quantity=left_qty,
                total_cost=_money(existing.total_cost - closed_cost),
                fees_paid=_money(existing.fees_paid + fill.fee),
                as_of=fill.executed_at,
            )
            return
        if open_qty > ZERO:
            self._positions[ticker] = Position(
                contract=Contract(market_ticker=ticker, side=fill.contract.side),
                quantity=open_qty,
                total_cost=_money(fill.cost - matched_cost),
                fees_paid=fill.fee,
                as_of=fill.executed_at,
            )
            return
        del self._positions[ticker]

    def _touch_peak(self) -> None:
        current = self.equity()
        if current > self.peak_equity:
            self.peak_equity = current


def _text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise LedgerError(f"ledger payload field {key} must be a string")
    return value


def _decimal(payload: dict[str, object], key: str) -> Decimal:
    return Decimal(_text(payload, key))


def _list(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise LedgerError(f"ledger payload field {key} must be a list")
    return value


def _parse_time(value: object) -> UtcDatetime:
    if not isinstance(value, str):
        raise LedgerError("ledger timestamp must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise LedgerError("ledger timestamp must be timezone-aware")
    return parsed
