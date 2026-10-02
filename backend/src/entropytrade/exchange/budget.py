"""Read-token bucket. The SDK's own retries stay off so this is the only pacer.

Kalshi's 429 body is ``{"error": "too many requests"}`` and, as of 2026-10-02, carries no
``Retry-After``. A call that does not fit in the bucket is refused here, before it is sent.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from entropytrade.domain.limits import EndpointCostSchedule, TokenBucket


class RateLimitExceededError(Exception):
    """The local budget cannot pay for another request at ``now``."""

    def __init__(self, retry_after: timedelta) -> None:
        super().__init__(f"rate budget exhausted; retry after {retry_after.total_seconds()}s")
        self.retry_after = retry_after


class ReadBudget:
    """Token bucket refilled from a :class:`TokenBucket` snapshot."""

    def __init__(
        self,
        limits: TokenBucket,
        *,
        now: datetime,
        costs: EndpointCostSchedule | None = None,
    ) -> None:
        self._capacity = Decimal(limits.capacity)
        self._refill = Decimal(limits.refill_per_second)
        self._tokens = self._capacity
        self._updated = now
        self._default_cost = costs.default_cost if costs is not None else 10
        self._costs = (
            {(item.method.upper(), item.path): item.cost for item in costs.endpoints}
            if costs is not None
            else {}
        )

    def cost_for(self, method: str, path: str) -> int:
        if not path:
            return self._default_cost
        return self._costs.get((method.upper(), path), self._default_cost)

    def use_schedule(self, costs: EndpointCostSchedule) -> None:
        self._default_cost = costs.default_cost
        self._costs = {(item.method.upper(), item.path): item.cost for item in costs.endpoints}

    def take(self, cost: int, now: datetime) -> None:
        if cost <= 0:
            raise ValueError("token cost must be positive")
        elapsed = Decimal(str(max((now - self._updated).total_seconds(), 0)))
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
        self._updated = now
        needed = Decimal(cost)
        if self._tokens < needed:
            short = needed - self._tokens
            wait = timedelta(seconds=float(short / self._refill))
            raise RateLimitExceededError(wait)
        self._tokens -= needed
