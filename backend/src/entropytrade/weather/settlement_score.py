"""Phase 4 questions on CLI labels, not on the Open-Meteo archive.

The label is the earliest post-day NWS CLI high for CLIPHL. The forecast is
the stored previous-day Open-Meteo max. A book enters the replay only when
it has a real size and its time is before that day's CLI. Nothing is fit
and nothing is promoted.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.backtest.replay import DecisionView, run_replay
from entropytrade.domain.enums import FeeType, OutcomeSide, StrikeType, TimeInForce
from entropytrade.domain.market import Contract, Strike
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.observations import FeatureObservation, Forecast
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.exchange.public_tape import PublicBook, load_books
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.weather.baseline import mean_absolute_error
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.probability import (
    InsufficientHistoryError,
    brier_score,
    calibrate,
    climatology_hit_rate,
    raw_forecast_probability,
    refuse_fitted_model,
)

_STATION = "CLIPHL"
_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(80), cap=Decimal(81))


@dataclass(frozen=True)
class AlignedScore:
    """Answers from the joined rows. A model was not fit."""

    scored_days: int
    mae: Decimal
    mae_first_half: Decimal
    mae_second_half: Decimal
    probability_days: int
    brier_raw: Decimal
    brier_climatology: Decimal
    brier_calibrated: Decimal
    forecast_signal_days: int
    sized_books_in_window: int
    replay_fills: int
    replay_equity: Decimal
    model_gate_open: bool
    fitted_model: bool
    promoted: bool


def load_aligned_score(root: Path) -> AlignedScore:
    """Score stored forecasts against CLI labels and replay only real books."""
    labels, _comparison = load_comparison(root)
    forecasts = _forecasts(root, labels)
    label_rows = tuple((item.valid_on, item.high_f, item.available_at) for item in labels)
    mae = mean_absolute_error(forecasts, label_rows, station=_STATION)
    midpoint = len(label_rows) // 2
    mae_first = mean_absolute_error(forecasts, label_rows[:midpoint], station=_STATION)
    mae_second = mean_absolute_error(forecasts, label_rows[midpoint:], station=_STATION)
    raw, climate, blended, days = _briers(forecasts, labels)
    signals = sum(1 for forecast in forecasts if _STRIKE.resolves_yes(forecast.value))
    books = _books_before_the_label(load_books(root), labels)
    fills, equity = _replay(books, forecasts, labels)
    try:
        refuse_fitted_model(len(label_rows))
    except InsufficientHistoryError:
        gate_open = False
    else:
        gate_open = True
    return AlignedScore(
        scored_days=len(label_rows),
        mae=mae,
        mae_first_half=mae_first,
        mae_second_half=mae_second,
        probability_days=days,
        brier_raw=raw,
        brier_climatology=climate,
        brier_calibrated=blended,
        forecast_signal_days=signals,
        sized_books_in_window=len(books),
        replay_fills=fills,
        replay_equity=equity,
        model_gate_open=gate_open,
        fitted_model=False,
        promoted=False,
    )


def _forecasts(root: Path, labels: Sequence[CliLabel]) -> tuple[Forecast, ...]:
    body = _mapping(_read(root / "open-meteo" / "previous-runs.json"), "previous-runs")
    hourly = _mapping(body.get("hourly"), "hourly")
    times = _seq(hourly.get("time"), "time")
    values = _seq(hourly.get("temperature_2m_previous_day1"), "values")
    by_day: dict[date, list[Decimal]] = {}
    for stamp, raw in zip(times, values, strict=True):
        hour = datetime.fromisoformat(_text(stamp, "hour")).replace(tzinfo=UTC)
        by_day.setdefault(hour.date(), []).append(_decimal(raw))
    ingested = max(label.available_at for label in labels)
    forecasts: list[Forecast] = []
    for valid_on, samples in sorted(by_day.items()):
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
                location_id=_STATION,
                variable="daily_high_f",
                valid_from=available,
                valid_to=available.replace(hour=23, minute=59),
                value=max(samples),
                unit="degF",
            )
        )
    return tuple(forecasts)


def _briers(
    forecasts: Sequence[Forecast],
    labels: Sequence[CliLabel],
) -> tuple[Decimal, Decimal, Decimal, int]:
    by_day = {forecast.valid_from.date(): forecast for forecast in forecasts}
    prior = [(label.available_at, label.high_f) for label in labels]
    raw_pairs: list[tuple[Decimal, bool]] = []
    climate_pairs: list[tuple[Decimal, bool]] = []
    blended_pairs: list[tuple[Decimal, bool]] = []
    for label in labels:
        forecast = by_day.get(label.valid_on)
        if forecast is None or forecast.available_at >= label.available_at:
            continue
        decision = datetime(
            label.valid_on.year,
            label.valid_on.month,
            label.valid_on.day,
            15,
            tzinfo=UTC,
        )
        try:
            climate = climatology_hit_rate(prior, decision_time=decision, strike=_STRIKE)
        except ValueError:
            continue
        happened = _STRIKE.resolves_yes(label.high_f)
        raw = raw_forecast_probability(forecast.value, _STRIKE)
        raw_pairs.append((raw, happened))
        climate_pairs.append((climate, happened))
        blended_pairs.append((calibrate(raw, climate), happened))
    return (
        brier_score(raw_pairs),
        brier_score(climate_pairs),
        brier_score(blended_pairs),
        len(raw_pairs),
    )


def _books_before_the_label(
    books: Sequence[PublicBook],
    labels: Sequence[CliLabel],
) -> tuple[OrderBook, ...]:
    by_day = {label.valid_on: label for label in labels}
    kept: list[OrderBook] = []
    for item in books:
        valid_on = ticker_target_date(item.market_ticker)
        label = None if valid_on is None else by_day.get(valid_on)
        if label is None or item.available_at >= label.available_at:
            continue
        kept.append(item.book)
    return tuple(kept)


def _replay(
    books: Sequence[OrderBook],
    forecasts: Sequence[Forecast],
    labels: Sequence[CliLabel],
) -> tuple[int, Decimal]:
    by_day = {forecast.valid_from.date(): forecast for forecast in forecasts}
    records: list[FeatureObservation] = []
    for label in labels:
        forecast = by_day.get(label.valid_on)
        if forecast is None:
            continue
        records.append(
            FeatureObservation(
                source_id=forecast.source_id,
                event_time=forecast.run_time,
                available_at=forecast.available_at,
                ingested_at=forecast.ingested_at,
                feature_name="forecast_high",
                feature_version="previous_day1",
                entity_id=f"CLIPHL-{label.valid_on.isoformat()}",
                value=forecast.value,
            )
        )
    start = datetime(2026, 8, 23, tzinfo=UTC)
    ledger = Ledger(Decimal("100"), as_of=start)

    def trade(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        valid_on = ticker_target_date(book.market_ticker)
        if valid_on is None:
            return None
        feature = view.feature("forecast_high", f"CLIPHL-{valid_on.isoformat()}")
        if feature is None or feature.value is None or not _STRIKE.resolves_yes(feature.value):
            return None
        return OrderIntent(
            strategy_id="cli-aligned",
            strategy_version=1,
            contract=Contract(market_ticker=book.market_ticker, side=OutcomeSide.YES),
            yes_price=Decimal("0.4000"),
            quantity=Decimal("1.00"),
            time_in_force=TimeInForce.FILL_OR_KILL,
            decision_time=book.received_at,
        )

    result = run_replay(
        books=books,
        records=tuple(records),
        strategy=trade,
        ledger=ledger,
        broker=PaperBroker(
            ledger,
            FeeSchedule(
                fee_type=FeeType.QUADRATIC,
                fee_multiplier=Decimal(1),
                maker_pays=False,
                quadratic_coefficient=Decimal(0),
            ),
        ),
        engine=RiskEngine(
            RiskLimits(
                bankroll=Decimal("100"),
                per_trade=Decimal("100"),
                per_event=Decimal("100"),
                total_deployed=Decimal("100"),
                max_loss=Decimal("50"),
                max_drawdown=Decimal("50"),
                max_book_age_seconds=86400,
                min_liquidity=Decimal("1.00"),
                max_spread=Decimal("0.2000"),
                config_version="aligned-v1",
            )
        ),
        latency=timedelta(0),
        window=SplitWindow(
            split=SampleSplit.TRAIN,
            start=start,
            end=datetime(2026, 10, 3, tzinfo=UTC),
        ),
        settlements=(),
    )
    return len(result.fill_ids), result.ending_equity


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


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool | float):
        raise ValueError("temperature is not an exact decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError("temperature is not an exact decimal")
