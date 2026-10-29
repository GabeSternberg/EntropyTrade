"""Current REST body compatibility, confined to the pinned SDK boundary.

Kalshi omits liquidity_dollars on the observed public payloads. It is unused by our
mapping. Preserve absence as None; never inject zero into a financial field.
"""

from datetime import datetime

from kalshi.models.markets import Market as SdkMarket
from kalshi.models.markets import Orderbook as SdkOrderbook
from kalshi.models.series import Series as SdkSeries
from kalshi.types import DollarDecimal
from pydantic import AliasChoices, Field

from entropytrade.domain.market import Market, Series
from entropytrade.domain.market_data import OrderBook
from entropytrade.exchange.kalshi.mapping import (
    market_from_sdk,
    order_book_from_sdk,
    series_from_sdk,
)


class CurrentMarket(SdkMarket):
    # The pinned parent requires Decimal. Only this unused, now-absent wire field is relaxed.
    liquidity: DollarDecimal | None = Field(  # type: ignore[assignment]
        default=None, validation_alias=AliasChoices("liquidity_dollars", "liquidity")
    )


def market_from_body(body: object, *, captured_at: datetime, series: str) -> Market:
    return market_from_sdk(
        CurrentMarket.model_validate(body), captured_at=captured_at, series_ticker=series
    )


def series_from_body(body: object) -> Series:
    return series_from_sdk(SdkSeries.model_validate(body))


def public_book_from_body(body: object, *, ticker: str, received_at: datetime) -> OrderBook:
    """Strict current public envelope; malformed/legacy/unsized books are never inferred."""
    if not isinstance(body, dict) or not isinstance(body.get("orderbook_fp"), dict):
        raise ValueError("missing fixed-point book envelope")
    book = body["orderbook_fp"]
    sides = {}
    for side in ("yes", "no"):
        pairs = book.get(side + "_dollars")
        if not isinstance(pairs, list) or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(value, str) for value in pair)
            for pair in pairs
        ):
            raise ValueError("book levels need exact dollar and quantity strings")
        sides[side] = [{"price": pair[0], "quantity": pair[1]} for pair in pairs]
    parsed = SdkOrderbook.model_validate({"ticker": ticker, **sides})
    return order_book_from_sdk(parsed, received_at=received_at)
