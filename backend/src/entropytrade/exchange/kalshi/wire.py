"""Turn a Kalshi WebSocket JSON envelope into a domain frame.

The socket itself is not opened here. A recording or a test supplies the envelope, and the
same function is what a live session would call on each message.
"""

from datetime import UTC, datetime
from decimal import Decimal

from kalshi.ws.models.market_lifecycle import MarketLifecycleMessage
from kalshi.ws.models.orderbook_delta import OrderbookDeltaMessage, OrderbookSnapshotMessage
from kalshi.ws.models.trade import TradeMessage

from entropytrade.domain.enums import OutcomeSide
from entropytrade.exchange.frames import (
    BookDeltaFrame,
    BookLevel,
    BookSnapshotFrame,
    LifecycleFrame,
    MarketFrame,
    TradeFrame,
)
from entropytrade.exchange.gateway import GatewayError


def frame_from_wire(envelope: object, *, received_at: datetime) -> MarketFrame | None:
    """Map one server envelope. Subscription acks are ignored. Unknown types are refused."""
    if not isinstance(envelope, dict):
        raise GatewayError("websocket envelope is not an object")
    kind = envelope.get("type")
    if kind in {"subscribed", "ok", "unsubscribed", "event_fee_update"}:
        return None
    if kind == "orderbook_snapshot":
        snapshot = OrderbookSnapshotMessage.model_validate(envelope)
        return BookSnapshotFrame(
            sid=snapshot.sid,
            seq=snapshot.seq,
            market_ticker=snapshot.msg.market_ticker,
            yes=_levels(snapshot.msg.yes),
            no=_levels(snapshot.msg.no),
            received_at=received_at,
        )
    if kind == "orderbook_delta":
        delta = OrderbookDeltaMessage.model_validate(envelope)
        return BookDeltaFrame(
            sid=delta.sid,
            seq=delta.seq,
            market_ticker=delta.msg.market_ticker,
            side=delta.msg.side,
            price=delta.msg.price,
            delta=delta.msg.delta,
            received_at=received_at,
            exchange_ts=(
                datetime.fromtimestamp(delta.msg.ts_ms / 1000, tz=UTC)
                if delta.msg.ts_ms is not None
                else delta.msg.ts
            ),
        )
    if kind == "trade":
        trade = TradeMessage.model_validate(envelope)
        return TradeFrame(
            sid=trade.sid,
            seq=trade.seq,
            market_ticker=trade.msg.market_ticker,
            trade_id=trade.msg.trade_id,
            yes_price=trade.msg.yes_price,
            quantity=trade.msg.count,
            taker_side=OutcomeSide(trade.msg.taker_outcome_side),
            executed_at=datetime.fromtimestamp(trade.msg.ts_ms / 1000, tz=UTC),
            received_at=received_at,
            is_block_trade=trade.msg.is_block_trade,
        )
    if kind == "market_lifecycle_v2":
        lifecycle = MarketLifecycleMessage.model_validate(envelope)
        return LifecycleFrame(
            sid=lifecycle.sid,
            seq=lifecycle.seq,
            market_ticker=lifecycle.msg.market_ticker,
            event_type=lifecycle.msg.event_type,
            result=lifecycle.msg.result,
            exchange_index=lifecycle.msg.exchange_index,
            received_at=received_at,
        )
    raise GatewayError(f"unsupported websocket type {kind!r}")


def _levels(levels: dict[Decimal, Decimal]) -> tuple[BookLevel, ...]:
    return tuple(
        BookLevel(price=price, quantity=quantity)
        for price, quantity in levels.items()
        if quantity > 0
    )
