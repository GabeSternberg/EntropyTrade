"""What a research agent is allowed to see. There is no order method and no label feed."""

from dataclasses import dataclass, field

from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.observations import Forecast


@dataclass
class ResearchDeps:
    """Forecast vintages and books. Settlement labels are not on this object."""

    forecasts: tuple[Forecast, ...]
    books: tuple[OrderBook, ...]
    tool_log: list[str] = field(default_factory=list)

    def forecast_rows(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "location_id": forecast.location_id,
                "variable": forecast.variable,
                "valid_on": forecast.valid_from.date().isoformat(),
                "value": format(forecast.value, "f"),
                "available_at": forecast.available_at.isoformat(),
            }
            for forecast in self.forecasts
        )

    def book_rows(self) -> tuple[dict[str, str], ...]:
        rows: list[dict[str, str]] = []
        for book in self.books:
            bid = book.best_bid
            ask = book.best_ask
            rows.append(
                {
                    "market_ticker": book.market_ticker,
                    "bid": "" if bid is None else format(bid.price, "f"),
                    "ask": "" if ask is None else format(ask.price, "f"),
                    "received_at": book.received_at.isoformat(),
                }
            )
        return tuple(rows)
