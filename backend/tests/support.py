"""Shared builders for domain tests."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from entropytrade.domain.enums import OutcomeSide, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.orders import OrderRequest


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def order_request(
    *,
    price: str = "0.40",
    quantity: str = "1.00",
    side: OutcomeSide = OutcomeSide.YES,
) -> OrderRequest:
    return OrderRequest(
        intent_id=uuid4(),
        contract=Contract(market_ticker="KXHIGHPHIL-26OCT02-T89", side=side),
        yes_price=Decimal(price),
        quantity=Decimal(quantity),
        time_in_force=TimeInForce.GOOD_TILL_CANCELED,
        created_at=utc(2026, 10, 2, 15),
    )
