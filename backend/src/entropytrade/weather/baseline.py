"""Daily-high baselines scored only on vintages that existed before the label.

The label is a CLI daily high. It is not the maximum of hourly temperatures, and
a forecast available after that CLI cannot enter the score. Persistence may
repeat the previous CLI high only once that CLI is already available.
"""

from datetime import date, datetime
from decimal import Decimal

from entropytrade.domain.numeric import ZERO, parse_exact_decimal
from entropytrade.domain.observations import Forecast
from entropytrade.domain.time import ensure_utc


class NoScoredForecastError(ValueError):
    """Every forecast was issued after the label, or none matched the day."""


def persistence_forecast(
    *,
    previous_high_f: Decimal,
    previous_available_at: datetime,
    station: str,
    valid_on: date,
    run_time: datetime,
    available_at: datetime,
) -> Forecast:
    """Repeat the last CLI high. Refuses a previous high that is not yet known."""
    if ensure_utc(previous_available_at) > ensure_utc(available_at):
        raise ValueError("persistence cannot use a CLI high before it is available")
    issued = ensure_utc(run_time)
    start = datetime(valid_on.year, valid_on.month, valid_on.day, tzinfo=issued.tzinfo)
    end = start.replace(hour=23, minute=59)
    return Forecast(
        source_id="persistence",
        event_time=ensure_utc(run_time),
        available_at=ensure_utc(available_at),
        ingested_at=ensure_utc(available_at),
        provider="entropytrade",
        model="persistence",
        run_time=ensure_utc(run_time),
        location_id=station,
        variable="daily_high_f",
        valid_from=start,
        valid_to=end,
        value=parse_exact_decimal(previous_high_f),
        unit="degF",
    )


def mean_absolute_error(
    forecasts: tuple[Forecast, ...] | list[Forecast],
    labels: tuple[tuple[date, Decimal, datetime], ...] | list[tuple[date, Decimal, datetime]],
    *,
    station: str,
) -> Decimal:
    """Mean absolute error using only forecasts available strictly before each label."""
    if not labels:
        raise NoScoredForecastError("no labels")
    total = ZERO
    for valid_on, label_high_f, label_available_at in labels:
        chosen = latest_before_label(
            forecasts,
            station=station,
            valid_on=valid_on,
            label_available_at=label_available_at,
        )
        if chosen is None:
            raise NoScoredForecastError(f"no {station} forecast for {valid_on} before the label")
        total += abs(chosen.value - parse_exact_decimal(label_high_f))
    return total / Decimal(len(labels))


def latest_before_label(
    forecasts: tuple[Forecast, ...] | list[Forecast],
    *,
    station: str,
    valid_on: date,
    label_available_at: datetime,
) -> Forecast | None:
    cutoff = ensure_utc(label_available_at)
    eligible = [
        forecast
        for forecast in forecasts
        if forecast.location_id == station
        and forecast.variable == "daily_high_f"
        and forecast.valid_from.date() == valid_on
        and forecast.available_at < cutoff
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda forecast: (forecast.available_at, forecast.run_time))
