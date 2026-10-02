"""Boundary between Kalshi's live API and the ``/historical/*`` endpoints.

A recorder that only calls ``/markets`` misses contracts whose settlement time is older than
``market_settled_ts``. Every stored row records which endpoint it came from.
"""

from enum import StrEnum

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import UtcDatetime


class ApiOrigin(StrEnum):
    """Which Kalshi surface produced a row."""

    LIVE = "live"
    HISTORICAL = "historical"


class HistoricalCutoff(DomainModel):
    """Timestamps from ``GET /historical/cutoff``. Older rows live under ``/historical``."""

    market_settled_ts: UtcDatetime
    trades_created_ts: UtcDatetime
    orders_updated_ts: UtcDatetime
    market_positions_last_updated_ts: UtcDatetime | None = None
    observed_at: UtcDatetime
    exchange_index: int | None = Field(default=None, ge=0)
