"""Exchange status and API-limit snapshots returned by a gateway.

Kalshi meters reads and writes as separate token buckets (spec section 37). The budgeter that
spends them is Phase 1; this is only the observation.
"""

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import UtcDatetime


class TokenBucket(DomainModel):
    refill_per_second: int = Field(gt=0)
    capacity: int = Field(gt=0)


class ApiLimits(DomainModel):
    usage_tier: str = Field(min_length=1)
    read: TokenBucket
    write: TokenBucket
    observed_at: UtcDatetime


class EndpointCost(DomainModel):
    """Token cost of one HTTP route. Unlisted routes use ``EndpointCostSchedule.default_cost``."""

    method: str = Field(min_length=1)
    path: str = Field(min_length=1)
    cost: int = Field(gt=0)


class EndpointCostSchedule(DomainModel):
    """``GET /account/endpoint_costs``. The budgeter prices reads from this, not a constant."""

    default_cost: int = Field(gt=0)
    endpoints: tuple[EndpointCost, ...]
    observed_at: UtcDatetime


class ExchangeStatus(DomainModel):
    trading_active: bool
    exchange_ts: UtcDatetime | None = None
    observed_at: UtcDatetime
