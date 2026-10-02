"""Recorded market-data frames. Replay reads these; the Kalshi adapter writes them.

Payloads use domain decimals, never venue SDK models, so a recording can be played back
without the network and without ``kalshi-sdk``.
"""

import json
from decimal import Decimal
from typing import Literal

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import OutcomeSide
from entropytrade.domain.numeric import ExactDecimal, PositiveQuantity, Price
from entropytrade.domain.time import UtcDatetime


class BookLevel(DomainModel):
    price: Price
    quantity: PositiveQuantity


class BookSnapshotFrame(DomainModel):
    channel: Literal["orderbook_snapshot"] = "orderbook_snapshot"
    sid: int = Field(ge=0)
    seq: int = Field(ge=0)
    market_ticker: str = Field(min_length=1)
    yes: tuple[BookLevel, ...] = ()
    no: tuple[BookLevel, ...] = ()
    received_at: UtcDatetime
    exchange_ts: UtcDatetime | None = None


class BookDeltaFrame(DomainModel):
    channel: Literal["orderbook_delta"] = "orderbook_delta"
    sid: int = Field(ge=0)
    seq: int = Field(ge=0)
    market_ticker: str = Field(min_length=1)
    side: Literal["yes", "no"]
    price: Price
    delta: ExactDecimal
    received_at: UtcDatetime
    exchange_ts: UtcDatetime | None = None


class TradeFrame(DomainModel):
    channel: Literal["trade"] = "trade"
    sid: int = Field(ge=0)
    seq: int | None = Field(default=None, ge=0)
    market_ticker: str = Field(min_length=1)
    trade_id: str = Field(min_length=1)
    yes_price: Price
    quantity: PositiveQuantity
    taker_side: OutcomeSide
    executed_at: UtcDatetime
    received_at: UtcDatetime
    is_block_trade: bool = False


class LifecycleFrame(DomainModel):
    channel: Literal["market_lifecycle_v2"] = "market_lifecycle_v2"
    sid: int = Field(ge=0)
    seq: int | None = Field(default=None, ge=0)
    market_ticker: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    result: str | None = None
    exchange_index: int | None = Field(default=None, ge=0)
    received_at: UtcDatetime


MarketFrame = BookSnapshotFrame | BookDeltaFrame | TradeFrame | LifecycleFrame


def parse_frame(payload: str) -> MarketFrame:
    """Rebuild a frame from the JSON the recorder stored."""
    data = json.loads(payload)
    channel = data.get("channel") if isinstance(data, dict) else None
    if channel == "orderbook_snapshot":
        return BookSnapshotFrame.model_validate(data)
    if channel == "orderbook_delta":
        return BookDeltaFrame.model_validate(data)
    if channel == "trade":
        return TradeFrame.model_validate(data)
    if channel == "market_lifecycle_v2":
        return LifecycleFrame.model_validate(data)
    raise ValueError(f"unknown frame channel {channel!r}")


def frame_levels(levels: tuple[BookLevel, ...]) -> tuple[tuple[Decimal, Decimal], ...]:
    return tuple((level.price, level.quantity) for level in levels)
