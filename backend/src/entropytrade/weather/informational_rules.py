"""Pre-registered informational rules. Thresholds are not fit to equity.

The bracket is 80 to 81 inclusive. The price threshold is 0.40, the same
limit the inside rule already uses. A forecast above 81 wants NO on that
bracket. A forecast below 80 wants NO. A forecast above the midpoint 80.5
wants YES, and the optimistic case still requires a YES print at or below
0.40. Base and conservative do not take a print as a fill. Nothing here is
promoted. This module does not open a socket and does not read the
historical trade table.
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
PRICE_THRESHOLD = Decimal("0.4000")
BRACKET_FLOOR = Decimal(80)
BRACKET_CAP = Decimal(81)
MIDPOINT = Decimal("80.5")
_ONE = Decimal(1)
_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=BRACKET_FLOOR, cap=BRACKET_CAP)
RULE_NAMES = (
    "forecast_inside",
    "forecast_above",
    "forecast_below",
    "forecast_gap",
)


@dataclass(frozen=True)
class RuleScenario:
    """One labeled fill assumption. ``guaranteed_fill`` stays false."""

    name: str
    fidelity: str
    guaranteed_fill: bool
    assumed_fills: int
    equity: Decimal


@dataclass(frozen=True)
class RuleScore:
    """One tried hypothesis. ``promoted`` stays false."""

    name: str
    tried: bool
    promoted: bool
    fires: int
    claim_hits: int
    scenarios: tuple[RuleScenario, RuleScenario, RuleScenario]


@dataclass(frozen=True)
class NettedScore:
    """Opposite YES and NO intents on one day become no position."""

    conflict_days: int
    same_side_days: int
    optimistic_fills: int
    optimistic_equity: Decimal
    fidelity: str
    guaranteed_fill: bool
    promoted: bool


def load_netted_score(root: Path) -> NettedScore:
    """Net the registered rules on the 2026 window before an optimistic fill."""
    labels, _comparison = load_comparison(root)
    forecasts = {item.valid_from.date(): item for item in load_stored_forecasts(root)}
    prints = load_trade_tape(root).b805_prints
    return net_rules(labels, forecasts, prints)


def net_rules(
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
    prints: tuple[TradePrint, ...],
) -> NettedScore:
    """One contract per day. Opposite sides cancel. Same sides do not double."""
    by_day = _prints_by_day(prints)
    conflicts = 0
    same_side = 0
    pnl: list[Decimal] = []
    for label in labels:
        forecast = forecasts.get(label.valid_on)
        if forecast is None or forecast.available_at >= label.available_at:
            continue
        yes_names = tuple(
            name for name in ("forecast_inside", "forecast_gap") if _fires(name, forecast.value)
        )
        no_names = tuple(
            name for name in ("forecast_above", "forecast_below") if _fires(name, forecast.value)
        )
        if yes_names and no_names:
            conflicts += 1
            continue
        if len(yes_names) > 1 or len(no_names) > 1:
            same_side += 1
        if not yes_names and not no_names:
            continue
        decision = datetime(
            label.valid_on.year,
            label.valid_on.month,
            label.valid_on.day,
            15,
            tzinfo=UTC,
        )
        day_prints = tuple(
            item
            for item in by_day.get(label.valid_on, ())
            if item.created_at <= decision
            and item.created_at < label.available_at
            and item.count > 0
        )
        if yes_names:
            price = _optimistic_price("forecast_gap", day_prints)
            won = _STRIKE.resolves_yes(label.high_f)
        else:
            price = _optimistic_price("forecast_above", day_prints)
            won = not _STRIKE.resolves_yes(label.high_f)
        if price is None:
            continue
        pnl.append(_ONE - price if won else -price)
    return NettedScore(
        conflict_days=conflicts,
        same_side_days=same_side,
        optimistic_fills=len(pnl),
        optimistic_equity=parse_money(sum(pnl, Decimal(100))),
        fidelity=FIDELITY,
        guaranteed_fill=False,
        promoted=False,
    )


def load_rule_scores(root: Path) -> tuple[RuleScore, ...]:
    """Score the registered rules on the 2026 CLI window and its prints."""
    labels, _comparison = load_comparison(root)
    forecasts = {item.valid_from.date(): item for item in load_stored_forecasts(root)}
    prints = load_trade_tape(root).b805_prints
    return score_rules(labels, forecasts, prints)


def score_rules(
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
    prints: tuple[TradePrint, ...],
) -> tuple[RuleScore, ...]:
    """Score each registered rule. The caller chooses which days are visible."""
    by_day = _prints_by_day(prints)
    return tuple(_score_one(name, labels, forecasts, by_day) for name in RULE_NAMES)


def _score_one(
    name: str,
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
    by_day: Mapping[date, tuple[TradePrint, ...]],
) -> RuleScore:
    fires = 0
    hits = 0
    pnl: list[Decimal] = []
    for label in labels:
        forecast = forecasts.get(label.valid_on)
        if forecast is None or forecast.available_at >= label.available_at:
            continue
        if not _fires(name, forecast.value):
            continue
        fires += 1
        if _claim(name, label.high_f):
            hits += 1
        decision = datetime(
            label.valid_on.year,
            label.valid_on.month,
            label.valid_on.day,
            15,
            tzinfo=UTC,
        )
        day_prints = tuple(
            item
            for item in by_day.get(label.valid_on, ())
            if item.created_at <= decision
            and item.created_at < label.available_at
            and item.count > 0
        )
        price = _optimistic_price(name, day_prints)
        if price is None:
            continue
        won = _contract_wins(name, label.high_f)
        pnl.append(_ONE - price if won else -price)
    flat = parse_money(Decimal(100))
    optimistic = RuleScenario(
        name="optimistic",
        fidelity=FIDELITY,
        guaranteed_fill=False,
        assumed_fills=len(pnl),
        equity=parse_money(sum(pnl, Decimal(100))),
    )
    base = RuleScenario(
        name="base",
        fidelity=FIDELITY,
        guaranteed_fill=False,
        assumed_fills=0,
        equity=flat,
    )
    conservative = RuleScenario(
        name="conservative",
        fidelity=FIDELITY,
        guaranteed_fill=False,
        assumed_fills=0,
        equity=flat,
    )
    return RuleScore(
        name=name,
        tried=True,
        promoted=False,
        fires=fires,
        claim_hits=hits,
        scenarios=(optimistic, base, conservative),
    )


def _fires(name: str, forecast_high: Decimal) -> bool:
    if name == "forecast_inside":
        return _STRIKE.resolves_yes(forecast_high)
    if name == "forecast_above":
        return forecast_high > BRACKET_CAP
    if name == "forecast_below":
        return forecast_high < BRACKET_FLOOR
    if name == "forecast_gap":
        return forecast_high - MIDPOINT > 0
    raise ValueError(f"unknown rule {name}")


def _claim(name: str, high: Decimal) -> bool:
    """Whether the label matches the sentence the rule asserted."""
    return _fires(name, high) if name != "forecast_gap" else _STRIKE.resolves_yes(high)


def _contract_wins(name: str, high: Decimal) -> bool:
    """YES rules win inside the bracket. NO rules win outside it."""
    inside = _STRIKE.resolves_yes(high)
    if name in ("forecast_inside", "forecast_gap"):
        return inside
    return not inside


def _optimistic_price(name: str, prints: tuple[TradePrint, ...]) -> Decimal | None:
    if name in ("forecast_inside", "forecast_gap"):
        priced = [
            item.yes_price for item in prints if Decimal(0) < item.yes_price <= PRICE_THRESHOLD
        ]
        return min(priced) if priced else None
    floor = _ONE - PRICE_THRESHOLD
    priced = [item.yes_price for item in prints if floor <= item.yes_price < _ONE]
    if not priced:
        return None
    return _ONE - max(priced)


def _prints_by_day(prints: tuple[TradePrint, ...]) -> dict[date, tuple[TradePrint, ...]]:
    grouped: dict[date, list[TradePrint]] = {}
    for item in prints:
        valid_on = ticker_target_date(item.ticker)
        if valid_on is None:
            continue
        grouped.setdefault(valid_on, []).append(item)
    return {day: tuple(items) for day, items in grouped.items()}
