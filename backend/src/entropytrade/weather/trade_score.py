"""Forecast rule against public trade prints. A print is not a fill.

Optimistic assumes one contract at the best YES print at or below the 0.40
limit, and says that fill was not guaranteed. Base and conservative do not
take a print as a fill. The taker coefficient is still unpublished, so no
fee is applied. This module does not open a socket.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.domain.numeric import parse_money
from entropytrade.domain.observations import Forecast
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.exchange.trade_prints import TradePrint, load_trade_tape
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.settlement_score import load_stored_forecasts

FIDELITY = "trade-print"
_LIMIT = Decimal("0.4000")
_ONE = Decimal(1)
_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(80), cap=Decimal(81))


@dataclass(frozen=True)
class PrintScenario:
    """One labeled assumption. ``guaranteed_fill`` stays false."""

    name: str
    fidelity: str
    guaranteed_fill: bool
    rule_fires: int
    assumed_fills: int
    equity: Decimal


@dataclass(frozen=True)
class TradeScore:
    """Stored-print answers. Equity is before any taker fee."""

    trade_count: int
    tickers_with_trades: int
    failed_calls: int
    b805_prints_before_decision: int
    fee_applied: bool
    scenarios: tuple[PrintScenario, PrintScenario, PrintScenario]


def load_trade_score(root: Path) -> TradeScore:
    """Score the forecast rule on stored prints. Nothing is promoted."""
    tape = load_trade_tape(root)
    labels, _comparison = load_comparison(root)
    forecasts = {item.valid_from.date(): item for item in load_stored_forecasts(root)}
    _fires, prints_before, scenarios = score_scenarios(labels, forecasts, tape.b805_prints)
    return TradeScore(
        trade_count=tape.trade_count,
        tickers_with_trades=tape.tickers_with_trades,
        failed_calls=tape.failed_calls,
        b805_prints_before_decision=prints_before,
        fee_applied=False,
        scenarios=scenarios,
    )


def score_scenarios(
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
    prints: tuple[TradePrint, ...],
) -> tuple[int, int, tuple[PrintScenario, PrintScenario, PrintScenario]]:
    """Optimistic may assume a print. Base and conservative do not."""
    fires, prints_before, optimistic_pnl = _join(labels, forecasts, prints)
    flat = parse_money(Decimal(100))
    optimistic = _scenario(
        "optimistic",
        fires=fires,
        fills=len(optimistic_pnl),
        equity=parse_money(sum(optimistic_pnl, Decimal(100))),
    )
    base = _scenario("base", fires=fires, fills=0, equity=flat)
    conservative = _scenario("conservative", fires=fires, fills=0, equity=flat)
    return fires, prints_before, (optimistic, base, conservative)


def _scenario(name: str, *, fires: int, fills: int, equity: Decimal) -> PrintScenario:
    return PrintScenario(
        name=name,
        fidelity=FIDELITY,
        guaranteed_fill=False,
        rule_fires=fires,
        assumed_fills=fills,
        equity=equity,
    )


def _join(
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
    prints: tuple[TradePrint, ...],
) -> tuple[int, int, tuple[Decimal, ...]]:
    by_day: dict[date, list[TradePrint]] = {}
    for item in prints:
        valid_on = ticker_target_date(item.ticker)
        if valid_on is not None and item.count > 0:
            by_day.setdefault(valid_on, []).append(item)
    fires = 0
    visible = 0
    pnl: list[Decimal] = []
    for label in labels:
        forecast = forecasts.get(label.valid_on)
        if forecast is None or forecast.available_at >= label.available_at:
            continue
        decision = datetime(
            label.valid_on.year,
            label.valid_on.month,
            label.valid_on.day,
            15,
            tzinfo=UTC,
        )
        day_prints = [
            item
            for item in by_day.get(label.valid_on, [])
            if item.created_at <= decision and item.created_at < label.available_at
        ]
        visible += len(day_prints)
        if not _STRIKE.resolves_yes(forecast.value):
            continue
        fires += 1
        priced = [item.yes_price for item in day_prints if Decimal(0) < item.yes_price <= _LIMIT]
        if not priced:
            continue
        price = min(priced)
        if _STRIKE.resolves_yes(label.high_f):
            pnl.append(_ONE - price)
        else:
            pnl.append(-price)
    return fires, visible, tuple(pnl)
