"""Walk-forward on the stored CLI days. No provider call and no live order.

Train, then validation. The holdout window is built and then refused. Feature
rows for holdout days are not passed into the replay. There is still no sized
book, so the run does not trade.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.backtest.replay import DecisionView, ReplayError, run_replay, run_walk_forward
from entropytrade.domain.enums import FeeType
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.observations import FeatureObservation, Forecast
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.exchange.trade_prints import load_trade_tape
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.weather.baseline import mean_absolute_error
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.cli_print_guess import CliPrintGuess, score_cli_print_guess
from entropytrade.weather.informational_rules import RuleScore, score_rules
from entropytrade.weather.settlement_score import load_stored_forecasts

_STATION = "CLIPHL"


@dataclass(frozen=True)
class StoredWalkForward:
    """Split counts and the replay the strategy was allowed to see."""

    train_days: int
    validation_days: int
    holdout_days: int
    train_mae: Decimal
    validation_mae: Decimal
    ran_splits: tuple[str, ...]
    holdout_blocked: bool
    replay_fills: int
    replay_equity: Decimal
    promoted: bool


def load_stored_walk_forward(root: Path) -> StoredWalkForward:
    """Split the stored labels in time and run the existing walk-forward."""
    labels, _comparison = load_comparison(root)
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    forecasts = load_stored_forecasts(root)
    train_rows = _rows(train)
    validation_rows = _rows(validation)
    windows = (
        _window(SampleSplit.TRAIN, train[0], validation[0]),
        _window(SampleSplit.VALIDATION, validation[0], holdout[0]),
        _window(SampleSplit.HOLDOUT, holdout[0], _day_after(holdout[-1])),
    )
    visible = train + validation
    records = _features(forecasts, visible)
    holdout_ids = {f"{_STATION}-{label.valid_on.isoformat()}" for label in holdout}
    if any(record.entity_id in holdout_ids for record in records):
        raise ValueError("a holdout day was passed into walk-forward")
    start = windows[0].start
    ledger = Ledger(Decimal("100"), as_of=start)
    results = run_walk_forward(
        books=(),
        records=records,
        strategy=_no_trade,
        ledger=ledger,
        broker=_broker(ledger),
        engine=_engine(),
        latency=timedelta(0),
        splits=windows,
    )
    if SampleSplit.HOLDOUT in results:
        raise ValueError("walk-forward ran the holdout")
    blocked = _holdout_is_blocked(windows[2])
    fills = sum(len(result.fill_ids) for result in results.values())
    return StoredWalkForward(
        train_days=len(train),
        validation_days=len(validation),
        holdout_days=len(holdout),
        train_mae=mean_absolute_error(forecasts, train_rows, station=_STATION),
        validation_mae=mean_absolute_error(forecasts, validation_rows, station=_STATION),
        ran_splits=tuple(result.value for result in results),
        holdout_blocked=blocked,
        replay_fills=fills,
        replay_equity=results[SampleSplit.VALIDATION].ending_equity,
        promoted=False,
    )


@dataclass(frozen=True)
class RuleWalkForward:
    """Train and validation scores. The holdout days are not scored."""

    train_days: int
    validation_days: int
    holdout_days: int
    ran_splits: tuple[str, ...]
    holdout_blocked: bool
    holdout_scored: bool
    promoted: bool
    train: tuple[RuleScore, ...]
    validation: tuple[RuleScore, ...]


def load_rule_walk_forward(root: Path) -> RuleWalkForward:
    """Walk the registered rules forward. Holdout labels are not passed in."""
    labels, _comparison = load_comparison(root)
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    reject_holdout(
        {label.valid_on for label in train + validation},
        {label.valid_on for label in holdout},
    )
    forecast_rows = load_stored_forecasts(root)
    forecasts = {item.valid_from.date(): item for item in forecast_rows}
    prints = load_trade_tape(root).b805_prints
    windows = (
        _window(SampleSplit.TRAIN, train[0], validation[0]),
        _window(SampleSplit.VALIDATION, validation[0], holdout[0]),
        _window(SampleSplit.HOLDOUT, holdout[0], _day_after(holdout[-1])),
    )
    visible = train + validation
    records = _features(forecast_rows, visible)
    holdout_ids = {f"{_STATION}-{label.valid_on.isoformat()}" for label in holdout}
    if any(record.entity_id in holdout_ids for record in records):
        raise ValueError("a holdout day was passed into walk-forward")
    start = windows[0].start
    ledger = Ledger(Decimal("100"), as_of=start)
    results = run_walk_forward(
        books=(),
        records=records,
        strategy=_no_trade,
        ledger=ledger,
        broker=_broker(ledger),
        engine=_engine(),
        latency=timedelta(0),
        splits=windows,
    )
    if SampleSplit.HOLDOUT in results:
        raise ValueError("walk-forward ran the holdout")
    return RuleWalkForward(
        train_days=len(train),
        validation_days=len(validation),
        holdout_days=len(holdout),
        ran_splits=tuple(result.value for result in results),
        holdout_blocked=_holdout_is_blocked(windows[2]),
        holdout_scored=False,
        promoted=False,
        train=score_rules(train, forecasts, prints),
        validation=score_rules(validation, forecasts, prints),
    )


@dataclass(frozen=True)
class GuessWalkForward:
    """The 0.50 print guess on train and validation. Holdout is not scored."""

    train_days: int
    validation_days: int
    holdout_days: int
    ran_splits: tuple[str, ...]
    holdout_blocked: bool
    holdout_scored: bool
    promoted: bool
    train: CliPrintGuess
    validation: CliPrintGuess


def load_guess_walk_forward(root: Path) -> GuessWalkForward:
    """Walk the pre-decision print guess forward. Holdout labels are not passed."""
    labels, _comparison = load_comparison(root)
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    reject_holdout(
        {label.valid_on for label in train + validation},
        {label.valid_on for label in holdout},
    )
    prints = load_trade_tape(root).b805_prints
    visible = train + validation
    records = _features(load_stored_forecasts(root), visible)
    holdout_ids = {f"{_STATION}-{label.valid_on.isoformat()}" for label in holdout}
    if any(record.entity_id in holdout_ids for record in records):
        raise ValueError("a holdout day was passed into walk-forward")
    windows = (
        _window(SampleSplit.TRAIN, train[0], validation[0]),
        _window(SampleSplit.VALIDATION, validation[0], holdout[0]),
        _window(SampleSplit.HOLDOUT, holdout[0], _day_after(holdout[-1])),
    )
    start = windows[0].start
    ledger = Ledger(Decimal("100"), as_of=start)
    results = run_walk_forward(
        books=(),
        records=records,
        strategy=_no_trade,
        ledger=ledger,
        broker=_broker(ledger),
        engine=_engine(),
        latency=timedelta(0),
        splits=windows,
    )
    if SampleSplit.HOLDOUT in results:
        raise ValueError("walk-forward ran the holdout")
    return GuessWalkForward(
        train_days=len(train),
        validation_days=len(validation),
        holdout_days=len(holdout),
        ran_splits=tuple(result.value for result in results),
        holdout_blocked=_holdout_is_blocked(windows[2]),
        holdout_scored=False,
        promoted=False,
        train=score_cli_print_guess(train, prints),
        validation=score_cli_print_guess(validation, prints),
    )


def reject_holdout(scored: set[date], holdout: set[date]) -> None:
    """A scored day and a holdout day cannot be the same day."""
    if scored & holdout:
        raise ValueError("a holdout day was scored")


def _thirds(
    labels: tuple[CliLabel, ...],
) -> tuple[tuple[CliLabel, ...], tuple[CliLabel, ...], tuple[CliLabel, ...]]:
    count = len(labels)
    train_n = count // 2
    valid_n = count // 4
    train = labels[:train_n]
    validation = labels[train_n : train_n + valid_n]
    holdout = labels[train_n + valid_n :]
    if not train or not validation or not holdout:
        raise ValueError("the stored days do not fill train, validation, and holdout")
    return train, validation, holdout


def _rows(
    labels: tuple[CliLabel, ...],
) -> tuple[tuple[date, Decimal, datetime], ...]:
    return tuple((label.valid_on, label.high_f, label.available_at) for label in labels)


def _window(split: SampleSplit, first: CliLabel, end_on: CliLabel | datetime) -> SplitWindow:
    start = datetime(first.valid_on.year, first.valid_on.month, first.valid_on.day, tzinfo=UTC)
    if isinstance(end_on, datetime):
        end = end_on
    else:
        end = datetime(end_on.valid_on.year, end_on.valid_on.month, end_on.valid_on.day, tzinfo=UTC)
    return SplitWindow(split=split, start=start, end=end)


def _day_after(label: CliLabel) -> datetime:
    day = datetime(label.valid_on.year, label.valid_on.month, label.valid_on.day, tzinfo=UTC)
    return day + timedelta(days=1)


def _features(
    forecasts: tuple[Forecast, ...],
    labels: tuple[CliLabel, ...],
) -> tuple[FeatureObservation, ...]:
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
                entity_id=f"{_STATION}-{label.valid_on.isoformat()}",
                value=forecast.value,
            )
        )
    return tuple(records)


def _no_trade(view: DecisionView, book: OrderBook) -> OrderIntent | None:
    del view, book
    return None


def _holdout_is_blocked(window: SplitWindow) -> bool:
    ledger = Ledger(Decimal("100"), as_of=window.start)
    try:
        run_replay(
            books=(),
            records=(),
            strategy=_no_trade,
            ledger=ledger,
            broker=_broker(ledger),
            engine=_engine(),
            latency=timedelta(0),
            window=window,
        )
    except ReplayError:
        return True
    return False


def _broker(ledger: Ledger) -> PaperBroker:
    return PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=Decimal(0),
        ),
    )


def _engine() -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            bankroll=Decimal("100"),
            per_trade=Decimal("100"),
            per_event=Decimal("100"),
            total_deployed=Decimal("100"),
            max_loss=Decimal("50"),
            max_drawdown=Decimal("50"),
            max_book_age_seconds=86400,
            min_liquidity=Decimal("1.00"),
            config_version="walk-forward-v1",
            max_spread=Decimal("0.2000"),
        )
    )
