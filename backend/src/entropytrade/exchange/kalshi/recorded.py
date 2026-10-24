"""Current REST body compatibility, confined to the pinned SDK boundary.

Kalshi omits liquidity_dollars on the observed public payloads. It is unused by our
mapping. Preserve absence as None; never inject zero into a financial field.
"""

from datetime import datetime

from kalshi.models.markets import Market as SdkMarket
from kalshi.types import DollarDecimal
from pydantic import AliasChoices, Field

from entropytrade.domain.market import Market
from entropytrade.exchange.kalshi.mapping import market_from_sdk


class CurrentMarket(SdkMarket):
    # The pinned parent requires Decimal. Only this unused, now-absent wire field is relaxed.
    liquidity: DollarDecimal | None = Field(  # type: ignore[assignment]
        default=None, validation_alias=AliasChoices("liquidity_dollars", "liquidity")
    )


def market_from_body(body: object, *, captured_at: datetime, series: str) -> Market:
    return market_from_sdk(
        CurrentMarket.model_validate(body), captured_at=captured_at, series_ticker=series
    )
