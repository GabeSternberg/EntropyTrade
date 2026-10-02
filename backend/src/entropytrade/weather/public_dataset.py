"""A stored public pull. This module does not open a socket.

The bodies under ``data/public`` were fetched once over unauthenticated HTTP.
Rows keep ``available_at``, ``source``, and ``endpoint``. Temperatures and
quotes are the values in those bodies. A missing quote is left missing.

Open-Meteo hourly ``temperature_2m_previous_day1`` is the forecast. Its
``available_at`` is 24 hours before the hour, which is what that field name
means. The archive daily max has no issue time. It is treated as available
at 12:00 UTC on the next calendar day, so it is not a same-day label.

The ``B80.5`` contract text in the saved markets is a between strike of 80
and 81. Candle close bid and ask become a book only when both are strictly
inside (0, 1), the book is not crossed, and ``volume_fp`` is positive. The
level quantity is that hour's volume. The candle does not include a size at
the touch. The empty order-book response is stored and is not turned into
levels.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.backtest.replay import DecisionView, Strategy, run_replay
from entropytrade.domain.enums import (
    FeeType,
    MarketResult,
    OutcomeSide,
    StrikeType,
    TimeInForce,
)
from entropytrade.domain.market import Contract, Strike
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import ONE, ZERO
from entropytrade.domain.observations import FeatureObservation, Forecast
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.weather.baseline import mean_absolute_error
from entropytrade.weather.probability import (
    brier_score,
    calibrate,
    climatology_hit_rate,
    market_implied_probability,
    raw_forecast_probability,
    refuse_fitted_model,
)

STATION = "CLIPHL"
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_DECISION_HOUR = 15
_ARCHIVE_BASIS = "archive daily max has no issue time; available at 12:00 UTC the next day"
_FORECAST_BASIS = "temperature_2m_previous_day1 is the run from 24 hours earlier"


@dataclass(frozen=True)
class PublicRow:
    """One immutable fact taken from a stored response."""

    available_at: datetime
    source: str
    endpoint: str
    kind: str
    record_id: str
    available_at_basis: str
    value: Decimal | None = None
    market_ticker: str | None = None
    yes_bid: Decimal | None = None
    yes_ask: Decimal | None = None
    volume: Decimal | None = None
    result: str | None = None


@dataclass(frozen=True)
class RecordedFailure:
    """An HTTP call that did not return a usable body. The body is what came back."""

    endpoint: str
    status: int
    body: str


@dataclass(frozen=True)
class ReplayScore:
    """Equity after one paper replay. Fill count is zero when the rule did not trade."""

    fills: int
    ending_equity: Decimal


@dataclass(frozen=True)
class PublicStudy:
    """Phase 4 questions scored only from the stored rows."""

    rows: tuple[PublicRow, ...]
    failures: tuple[RecordedFailure, ...]
    scored_days: int
    mae: Decimal
    mae_first_half: Decimal
    mae_second_half: Decimal
    brier_raw: Decimal
    brier_climatology: Decimal
    brier_calibrated: Decimal
    probability_days: int
    brier_market: Decimal | None
    market_days: int
    fitted_model_refused: bool
    official_days: int
    official_disagreements: int
    sized_books: int
    forecast_signal_days: int
    forecast_latency_0_fee_0: ReplayScore
    forecast_latency_0_fee_002: ReplayScore
    forecast_latency_2h_fee_0: ReplayScore
    ask_probe_latency_0_fee_0: ReplayScore
    ask_probe_latency_0_fee_002: ReplayScore
    ask_probe_latency_2h_fee_0: ReplayScore
    label_hidden_at_decision: bool


def load_study(root: Path) -> PublicStudy:
    """Score the stored pull. ``root`` is the ``data/public`` directory."""
    manifest = _mapping(_read(root / "manifest.json"), "manifest")
    fetched_at = _stamp(_text(manifest.get("fetched_at"), "fetched_at"), "fetched_at")
    endpoints = _endpoints(manifest)
    failures = _failures(root, manifest)
    rows = _rows(root, endpoints, fetched_at)
    return _study(rows, failures)


def _study(rows: tuple[PublicRow, ...], failures: tuple[RecordedFailure, ...]) -> PublicStudy:
    forecasts, labels = _daily_forecasts(rows)
    mae = mean_absolute_error(forecasts, labels, station=STATION)
    midpoint = len(labels) // 2
    mae_first = mean_absolute_error(forecasts, labels[:midpoint], station=STATION)
    mae_second = mean_absolute_error(forecasts, labels[midpoint:], station=STATION)
    strike = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(80), cap=Decimal(81))
    probabilities = _probabilities(forecasts, labels, strike)
    markets = _markets(rows)
    official_days, disagreements = _official(labels, markets, strike)
    books = _books(rows)
    decisions = _decision_times(books)
    market_brier, market_days = _market_brier(books, markets, decisions)
    signal_days = _signal_days(forecasts, strike)
    records = _features(forecasts, labels, markets)
    settlements = _settlements(markets)
    hidden: list[bool] = []
    forecast_rule = _forecast_strategy(decisions, strike, hidden)
    ask_probe = _ask_strategy(decisions)
    fee_0 = Decimal(0)
    fee_002 = Decimal("0.02")
    immediate = timedelta(0)
    delayed = timedelta(hours=2)
    refused = True
    try:
        refuse_fitted_model(len(labels))
    except ValueError:
        refused = True
    else:
        refused = False
    return PublicStudy(
        rows=rows,
        failures=failures,
        scored_days=len(labels),
        mae=mae,
        mae_first_half=mae_first,
        mae_second_half=mae_second,
        brier_raw=probabilities[0],
        brier_climatology=probabilities[1],
        brier_calibrated=probabilities[2],
        probability_days=probabilities[3],
        brier_market=market_brier,
        market_days=market_days,
        fitted_model_refused=refused,
        official_days=official_days,
        official_disagreements=disagreements,
        sized_books=len(books),
        forecast_signal_days=signal_days,
        forecast_latency_0_fee_0=_replay(
            books, records, settlements, forecast_rule, coefficient=fee_0, latency=immediate
        ),
        forecast_latency_0_fee_002=_replay(
            books, records, settlements, forecast_rule, coefficient=fee_002, latency=immediate
        ),
        forecast_latency_2h_fee_0=_replay(
            books, records, settlements, forecast_rule, coefficient=fee_0, latency=delayed
        ),
        ask_probe_latency_0_fee_0=_replay(
            books, records, settlements, ask_probe, coefficient=fee_0, latency=immediate
        ),
        ask_probe_latency_0_fee_002=_replay(
            books, records, settlements, ask_probe, coefficient=fee_002, latency=immediate
        ),
        ask_probe_latency_2h_fee_0=_replay(
            books, records, settlements, ask_probe, coefficient=fee_0, latency=delayed
        ),
        label_hidden_at_decision=all(hidden) if hidden else False,
    )


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return payload


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{what} has a non-string key")
        mapped[key] = item
    return mapped


def _seq(value: object, what: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return tuple(value)


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("expected text")
    return value


def _decimal(value: object, what: str) -> Decimal:
    if isinstance(value, bool | float):
        raise ValueError(f"{what} is not an exact decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError(f"{what} is not an exact decimal")


def _stamp(value: str, what: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{what} is not a timestamp") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return ensure_utc(parsed)


def _endpoints(manifest: Mapping[str, object]) -> dict[str, str]:
    found: dict[str, str] = {}
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        path = item.get("path")
        url = item.get("url")
        if isinstance(path, str) and isinstance(url, str):
            found[path] = url
    retained = manifest.get("retained_markets")
    if retained is not None:
        item = _mapping(retained, "retained_markets")
        path = item.get("path")
        url = item.get("endpoint")
        if isinstance(path, str) and isinstance(url, str):
            found[path] = url
    return found


def _failures(root: Path, manifest: Mapping[str, object]) -> tuple[RecordedFailure, ...]:
    found: list[RecordedFailure] = []
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        status = item.get("status")
        path = item.get("path")
        url = item.get("url")
        if not isinstance(status, int) or status < 400:
            continue
        if not isinstance(path, str) or not isinstance(url, str):
            raise ValueError("a failed call is missing its url or body path")
        found.append(
            RecordedFailure(
                endpoint=url,
                status=status,
                body=(root / path).read_text(encoding="utf-8"),
            )
        )
    return tuple(found)


def _rows(
    root: Path,
    endpoints: Mapping[str, str],
    fetched_at: datetime,
) -> tuple[PublicRow, ...]:
    rows: list[PublicRow] = []
    rows.extend(_forecast_hours(root, endpoints))
    rows.extend(_archive_days(root, endpoints))
    rows.extend(_market_rows(root, endpoints))
    rows.extend(_candle_rows(root, endpoints))
    rows.append(_orderbook_row(root, endpoints, fetched_at))
    return tuple(rows)


def _endpoint(endpoints: Mapping[str, str], relative: str) -> str:
    try:
        return endpoints[relative]
    except KeyError as exc:
        raise ValueError(f"no endpoint recorded for {relative}") from exc


def _forecast_hours(root: Path, endpoints: Mapping[str, str]) -> tuple[PublicRow, ...]:
    relative = "open-meteo/previous-runs.json"
    body = _mapping(_read(root / relative), relative)
    hourly = _mapping(body.get("hourly"), "hourly")
    times = _seq(hourly.get("time"), "hourly time")
    values = _seq(hourly.get("temperature_2m_previous_day1"), "previous day temperatures")
    if len(times) != len(values):
        raise ValueError("previous-run hours and temperatures differ in length")
    endpoint = _endpoint(endpoints, relative)
    rows: list[PublicRow] = []
    for stamp, raw in zip(times, values, strict=True):
        hour = _stamp(_text(stamp, "hour"), "hour")
        rows.append(
            PublicRow(
                available_at=hour - timedelta(days=1),
                source="open-meteo",
                endpoint=endpoint,
                kind="forecast_hour",
                record_id=hour.isoformat(),
                available_at_basis=_FORECAST_BASIS,
                value=_decimal(raw, "temperature"),
            )
        )
    return tuple(rows)


def _archive_days(root: Path, endpoints: Mapping[str, str]) -> tuple[PublicRow, ...]:
    relative = "open-meteo/archive.json"
    body = _mapping(_read(root / relative), relative)
    daily = _mapping(body.get("daily"), "daily")
    times = _seq(daily.get("time"), "archive dates")
    values = _seq(daily.get("temperature_2m_max"), "archive highs")
    if len(times) != len(values):
        raise ValueError("archive dates and highs differ in length")
    endpoint = _endpoint(endpoints, relative)
    rows: list[PublicRow] = []
    for stamp, raw in zip(times, values, strict=True):
        valid_on = date.fromisoformat(_text(stamp, "archive date"))
        available = datetime(valid_on.year, valid_on.month, valid_on.day, 12, tzinfo=UTC)
        available += timedelta(days=1)
        rows.append(
            PublicRow(
                available_at=available,
                source="open-meteo",
                endpoint=endpoint,
                kind="archive_day",
                record_id=valid_on.isoformat(),
                available_at_basis=_ARCHIVE_BASIS,
                value=_decimal(raw, "archive high"),
            )
        )
    return tuple(rows)


def _market_rows(root: Path, endpoints: Mapping[str, str]) -> tuple[PublicRow, ...]:
    relative = "kalshi-demo/markets-aug23-oct01.json"
    body = _mapping(_read(root / relative), relative)
    endpoint = _endpoint(endpoints, relative)
    rows: list[PublicRow] = []
    for raw in _seq(body.get("markets"), "markets"):
        market = _mapping(raw, "market")
        ticker = _text(market.get("ticker"), "ticker")
        if ticker.endswith("-B80.5"):
            _require_bracket(market, ticker)
        rows.append(
            PublicRow(
                available_at=_stamp(_text(market.get("updated_time"), "updated_time"), ticker),
                source="kalshi-demo",
                endpoint=endpoint,
                kind="market",
                record_id=ticker,
                available_at_basis="updated_time on the market object",
                value=_optional_decimal(market.get("last_price_dollars")),
                market_ticker=ticker,
                yes_bid=_optional_decimal(market.get("yes_bid_dollars")),
                yes_ask=_optional_decimal(market.get("yes_ask_dollars")),
                volume=_optional_decimal(market.get("volume_fp")),
                result=_optional_text(market.get("result")),
            )
        )
    return tuple(rows)


def _require_bracket(market: Mapping[str, object], ticker: str) -> None:
    kind = _text(market.get("strike_type"), ticker)
    floor = _decimal(market.get("floor_strike"), ticker)
    cap = _decimal(market.get("cap_strike"), ticker)
    if kind != StrikeType.BETWEEN or floor != Decimal(80) or cap != Decimal(81):
        raise ValueError(f"{ticker} is not the 80 to 81 bracket stored for this pull")


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value, "number")


def _candle_rows(root: Path, endpoints: Mapping[str, str]) -> tuple[PublicRow, ...]:
    rows: list[PublicRow] = []
    for path in sorted((root / "kalshi-demo" / "candles").glob("*.json")):
        relative = path.relative_to(root).as_posix()
        body = _mapping(_read(path), relative)
        endpoint = _endpoint(endpoints, relative)
        ticker = _text(body.get("ticker"), "candle ticker")
        for raw in _seq(body.get("candlesticks"), ticker):
            candle = _mapping(raw, ticker)
            end = candle.get("end_period_ts")
            if isinstance(end, bool) or not isinstance(end, int):
                raise ValueError(f"{ticker} candlestick has no end_period_ts")
            available = datetime.fromtimestamp(end, UTC)
            bid = _close(candle.get("yes_bid"))
            ask = _close(candle.get("yes_ask"))
            rows.append(
                PublicRow(
                    available_at=available,
                    source="kalshi-demo",
                    endpoint=endpoint,
                    kind="candle",
                    record_id=f"{ticker}@{available.isoformat()}",
                    available_at_basis="candlestick end_period_ts; bid and ask are close_dollars",
                    market_ticker=ticker,
                    yes_bid=bid,
                    yes_ask=ask,
                    volume=_optional_decimal(candle.get("volume_fp")),
                )
            )
    return tuple(rows)


def _close(value: object) -> Decimal | None:
    if value is None:
        return None
    side = _mapping(value, "candle side")
    raw = side.get("close_dollars")
    if raw is None:
        return None
    return _decimal(raw, "close")


def _orderbook_row(
    root: Path,
    endpoints: Mapping[str, str],
    fetched_at: datetime,
) -> PublicRow:
    relative = "kalshi-demo/orderbook.json"
    body = _mapping(_read(root / relative), relative)
    book = _mapping(body.get("orderbook_fp"), "orderbook")
    yes = _seq(book.get("yes_dollars"), "yes_dollars")
    no = _seq(book.get("no_dollars"), "no_dollars")
    if yes or no:
        raise ValueError("the stored order book was not empty; this loader has no size rule for it")
    return PublicRow(
        available_at=fetched_at,
        source="kalshi-demo",
        endpoint=_endpoint(endpoints, relative),
        kind="orderbook",
        record_id="orderbook",
        available_at_basis="the response has no exchange time; available_at is the fetch time",
    )


def _daily_forecasts(
    rows: Sequence[PublicRow],
) -> tuple[tuple[Forecast, ...], tuple[tuple[date, Decimal, datetime], ...]]:
    by_day: dict[date, list[PublicRow]] = {}
    for row in rows:
        if row.kind != "forecast_hour" or row.value is None:
            continue
        valid_on = _stamp(row.record_id, "forecast hour").date()
        by_day.setdefault(valid_on, []).append(row)
    ingested = max(row.available_at for row in rows)
    forecasts: list[Forecast] = []
    for valid_on, hours in sorted(by_day.items()):
        available = datetime(valid_on.year, valid_on.month, valid_on.day, tzinfo=UTC)
        run_time = available - timedelta(days=1)
        forecasts.append(
            Forecast(
                source_id="open-meteo-previous-day1",
                event_time=run_time,
                available_at=available,
                ingested_at=ingested,
                provider="open-meteo",
                model="previous_day1",
                run_time=run_time,
                location_id=STATION,
                variable="daily_high_f",
                valid_from=available,
                valid_to=available.replace(hour=23, minute=59),
                value=max(hour.value for hour in hours if hour.value is not None),
                unit="degF",
            )
        )
    labels: list[tuple[date, Decimal, datetime]] = []
    for row in rows:
        if row.kind != "archive_day" or row.value is None:
            continue
        valid_on = date.fromisoformat(row.record_id)
        labels.append((valid_on, row.value, row.available_at))
    labels.sort(key=lambda item: item[0])
    return tuple(forecasts), tuple(labels)


def _probabilities(
    forecasts: Sequence[Forecast],
    labels: Sequence[tuple[date, Decimal, datetime]],
    strike: Strike,
) -> tuple[Decimal, Decimal, Decimal, int]:
    by_day = {forecast.valid_from.date(): forecast for forecast in forecasts}
    raw_pairs: list[tuple[Decimal, bool]] = []
    climate_pairs: list[tuple[Decimal, bool]] = []
    calibrated_pairs: list[tuple[Decimal, bool]] = []
    prior = [(available, high) for _day, high, available in labels]
    for valid_on, high, available in labels:
        forecast = by_day.get(valid_on)
        if forecast is None:
            continue
        decision = datetime(valid_on.year, valid_on.month, valid_on.day, _DECISION_HOUR, tzinfo=UTC)
        if forecast.available_at > decision or available <= decision:
            continue
        try:
            climate = climatology_hit_rate(prior, decision_time=decision, strike=strike)
        except ValueError:
            continue
        happened = strike.resolves_yes(high)
        raw = raw_forecast_probability(forecast.value, strike)
        raw_pairs.append((raw, happened))
        climate_pairs.append((climate, happened))
        calibrated_pairs.append((calibrate(raw, climate), happened))
    if not raw_pairs:
        raise ValueError("no day had a forecast and a prior label")
    return (
        brier_score(raw_pairs),
        brier_score(climate_pairs),
        brier_score(calibrated_pairs),
        len(raw_pairs),
    )


def _market_brier(
    books: Sequence[OrderBook],
    markets: Sequence[PublicRow],
    decisions: frozenset[tuple[str, datetime]],
) -> tuple[Decimal | None, int]:
    by_ticker = {market.market_ticker: market for market in markets if market.market_ticker}
    pairs: list[tuple[Decimal, bool]] = []
    for book in books:
        if (book.market_ticker, book.received_at) not in decisions:
            continue
        market = by_ticker.get(book.market_ticker)
        if market is None or market.result not in ("yes", "no"):
            continue
        pairs.append((market_implied_probability(book), market.result == "yes"))
    if not pairs:
        return None, 0
    return brier_score(pairs), len(pairs)


def _markets(rows: Sequence[PublicRow]) -> tuple[PublicRow, ...]:
    return tuple(
        row
        for row in rows
        if (
            row.kind == "market"
            and row.market_ticker is not None
            and row.market_ticker.endswith("-B80.5")
        )
    )


def _event_date(ticker: str) -> date:
    token = ticker.split("-")[1]
    month = _MONTHS[token[2:5]]
    return date(2000 + int(token[:2]), month, int(token[5:7]))


def _official(
    labels: Sequence[tuple[date, Decimal, datetime]],
    markets: Sequence[PublicRow],
    strike: Strike,
) -> tuple[int, int]:
    highs = {valid_on: high for valid_on, high, _available in labels}
    days = 0
    disagreements = 0
    for market in markets:
        if market.market_ticker is None or market.result not in ("yes", "no"):
            continue
        high = highs.get(_event_date(market.market_ticker))
        if high is None:
            continue
        days += 1
        archive_yes = strike.resolves_yes(high)
        official_yes = market.result == "yes"
        if archive_yes != official_yes:
            disagreements += 1
    return days, disagreements


def _sized(row: PublicRow) -> bool:
    bid, ask, volume = row.yes_bid, row.yes_ask, row.volume
    if row.kind != "candle" or bid is None or ask is None or volume is None:
        return False
    return ZERO < bid < ONE and ZERO < ask < ONE and bid < ask and volume > ZERO


def _books(rows: Sequence[PublicRow]) -> tuple[OrderBook, ...]:
    books: list[OrderBook] = []
    for row in rows:
        if not _sized(row) or row.market_ticker is None or row.yes_bid is None:
            continue
        if row.yes_ask is None or row.volume is None:
            continue
        books.append(
            OrderBook(
                market_ticker=row.market_ticker,
                bids=(OrderBookLevel(price=row.yes_bid, quantity=row.volume),),
                asks=(OrderBookLevel(price=row.yes_ask, quantity=row.volume),),
                exchange_ts=row.available_at,
                received_at=row.available_at,
            )
        )
    return tuple(books)


def _signal_days(forecasts: Sequence[Forecast], strike: Strike) -> int:
    return sum(1 for forecast in forecasts if strike.resolves_yes(forecast.value))


def _features(
    forecasts: Sequence[Forecast],
    labels: Sequence[tuple[date, Decimal, datetime]],
    markets: Sequence[PublicRow],
) -> tuple[FeatureObservation, ...]:
    by_forecast = {forecast.valid_from.date(): forecast for forecast in forecasts}
    by_label = {valid_on: (high, available) for valid_on, high, available in labels}
    records: list[FeatureObservation] = []
    for market in markets:
        if market.market_ticker is None:
            continue
        valid_on = _event_date(market.market_ticker)
        forecast = by_forecast.get(valid_on)
        if forecast is not None:
            records.append(
                FeatureObservation(
                    source_id=forecast.source_id,
                    event_time=forecast.run_time,
                    available_at=forecast.available_at,
                    ingested_at=forecast.ingested_at,
                    feature_name="forecast_high",
                    feature_version="previous_day1",
                    entity_id=market.market_ticker,
                    value=forecast.value,
                )
            )
        label = by_label.get(valid_on)
        if label is None:
            continue
        high, available = label
        records.append(
            FeatureObservation(
                source_id="open-meteo-archive",
                event_time=available,
                available_at=available,
                ingested_at=available,
                feature_name="archive_high",
                feature_version="1",
                entity_id=market.market_ticker,
                value=high,
            )
        )
    return tuple(records)


def _settlements(
    markets: Sequence[PublicRow],
) -> tuple[tuple[datetime, str, MarketResult], ...]:
    found: list[tuple[datetime, str, MarketResult]] = []
    for market in markets:
        if market.market_ticker is None or market.result not in ("yes", "no"):
            continue
        found.append((market.available_at, market.market_ticker, MarketResult(market.result)))
    return tuple(found)


def _decision_times(books: Sequence[OrderBook]) -> frozenset[tuple[str, datetime]]:
    chosen: dict[str, datetime] = {}
    for book in books:
        cutoff = datetime(
            book.received_at.year,
            book.received_at.month,
            book.received_at.day,
            _DECISION_HOUR,
            tzinfo=UTC,
        )
        if book.received_at > cutoff:
            continue
        current = chosen.get(book.market_ticker)
        if current is None or book.received_at > current:
            chosen[book.market_ticker] = book.received_at
    return frozenset(chosen.items())


def _intent(book: OrderBook) -> OrderIntent:
    return OrderIntent(
        strategy_id="public-b80.5",
        strategy_version=1,
        contract=Contract(market_ticker=book.market_ticker, side=OutcomeSide.YES),
        yes_price=Decimal("0.4000"),
        quantity=Decimal("1.00"),
        time_in_force=TimeInForce.FILL_OR_KILL,
        decision_time=book.received_at,
    )


def _forecast_strategy(
    decisions: frozenset[tuple[str, datetime]],
    strike: Strike,
    hidden: list[bool],
) -> Strategy:
    def trade(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        if (book.market_ticker, book.received_at) not in decisions:
            return None
        label = view.feature("archive_high", book.market_ticker)
        hidden.append(label is None)
        vintage = view.feature("forecast_high", book.market_ticker)
        if vintage is None or vintage.value is None or not strike.resolves_yes(vintage.value):
            return None
        return _intent(book)

    return trade


def _ask_strategy(decisions: frozenset[tuple[str, datetime]]) -> Strategy:
    def trade(_view: DecisionView, book: OrderBook) -> OrderIntent | None:
        if (book.market_ticker, book.received_at) not in decisions:
            return None
        return _intent(book)

    return trade


def _limits() -> RiskLimits:
    return RiskLimits(
        bankroll=Decimal("100"),
        per_trade=Decimal("100"),
        per_event=Decimal("100"),
        total_deployed=Decimal("100"),
        max_loss=Decimal("50"),
        max_drawdown=Decimal("50"),
        max_book_age_seconds=3600,
        min_liquidity=Decimal("1.00"),
        max_spread=Decimal("0.2000"),
        config_version="public-v1",
    )


def _replay(
    books: Sequence[OrderBook],
    records: Sequence[FeatureObservation],
    settlements: Sequence[tuple[datetime, str, MarketResult]],
    strategy: Strategy,
    *,
    coefficient: Decimal,
    latency: timedelta,
) -> ReplayScore:
    start = datetime(2026, 8, 23, tzinfo=UTC)
    ledger = Ledger(Decimal("100"), as_of=start)
    result = run_replay(
        books=books,
        records=records,
        strategy=strategy,
        ledger=ledger,
        broker=PaperBroker(
            ledger,
            FeeSchedule(
                fee_type=FeeType.QUADRATIC,
                fee_multiplier=Decimal(1),
                maker_pays=False,
                quadratic_coefficient=coefficient,
            ),
        ),
        engine=RiskEngine(_limits()),
        latency=latency,
        window=SplitWindow(
            split=SampleSplit.TRAIN,
            start=start,
            end=datetime(2026, 10, 3, tzinfo=UTC),
        ),
        settlements=settlements,
    )
    return ReplayScore(fills=len(result.fill_ids), ending_equity=result.ending_equity)
