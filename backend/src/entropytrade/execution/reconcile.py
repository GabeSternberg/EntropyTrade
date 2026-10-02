"""Compare a local account with an exchange snapshot, and adopt a known order state.

A missing remote order that might still be live is a mismatch. ``UNKNOWN`` leaves only
through a legal transition, keyed by ``client_order_id``.
"""

from entropytrade.domain.orders import Order, check_order_transition
from entropytrade.domain.portfolio import PortfolioSnapshot


class ReconcileMismatchError(Exception):
    """Local and exchange state disagree."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def compare_snapshots(local: PortfolioSnapshot, remote: PortfolioSnapshot) -> tuple[str, ...]:
    """Empty means the cash balance and the open positions agree."""
    reasons: list[str] = []
    if local.cash_balance != remote.cash_balance:
        reasons.append(f"cash local {local.cash_balance} remote {remote.cash_balance}")
    local_positions = {item.contract.market_ticker: item for item in local.open_positions}
    remote_positions = {item.contract.market_ticker: item for item in remote.open_positions}
    if set(local_positions) != set(remote_positions):
        reasons.append("open position tickers differ")
        return tuple(reasons)
    for ticker, position in local_positions.items():
        other = remote_positions[ticker]
        if position.contract.side is not other.contract.side or position.quantity != other.quantity:
            reasons.append(f"{ticker} position differs")
    return tuple(reasons)


def adopt_order(local: Order, remote: Order) -> Order:
    """Move ``local`` to the remote state when the transition table allows it.

    Filled quantity cannot decrease or exceed the requested size. A second
    exchange id for the same client order id is a mismatch. The requested
    contract and size stay the local order's.
    """
    reasons: list[str] = []
    if local.client_order_id != remote.client_order_id:
        reasons.append("client_order_id")
    if local.contract != remote.contract:
        reasons.append("contract")
    if local.requested_quantity != remote.requested_quantity:
        reasons.append("requested_quantity")
    if (
        local.exchange_order_id is not None
        and remote.exchange_order_id is not None
        and local.exchange_order_id != remote.exchange_order_id
    ):
        reasons.append("exchange_order_id")
    if remote.filled_quantity < local.filled_quantity:
        reasons.append("filled_quantity")
    if reasons:
        raise ReconcileMismatchError(tuple(reasons))
    updated_at = remote.updated_at if remote.updated_at >= local.updated_at else local.updated_at
    exchange_order_id = remote.exchange_order_id or local.exchange_order_id
    if local.state is remote.state and local.filled_quantity == remote.filled_quantity:
        if exchange_order_id == local.exchange_order_id:
            return local
        return local.revalidated(exchange_order_id=exchange_order_id, updated_at=updated_at)
    check_order_transition(local.state, remote.state)
    return local.revalidated(
        state=remote.state,
        filled_quantity=remote.filled_quantity,
        exchange_order_id=exchange_order_id,
        updated_at=updated_at,
    )
