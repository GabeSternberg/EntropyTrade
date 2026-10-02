"""Turn a StrategySpec into a replay strategy, or refuse it.

The callable reads DecisionView features and the book in front of it. It does
not exec code. Exit predicates are not evaluated: a spec that does not say it
holds to settlement is rejected up front.
"""

import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from entropytrade.backtest.replay import DecisionView, Strategy
from entropytrade.domain.enums import OutcomeSide, StrategyFamily, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import ONE, ZERO
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.strategy import (
    ComparisonOp,
    PositionSizing,
    Predicate,
    SizingMethod,
    StrategySpec,
)

_RESTING = TimeInForce.GOOD_TILL_CANCELED


class UnsupportedSpecError(ValueError):
    """The spec is valid data, and this interpreter will not half-run it."""


def compile_strategy(spec: StrategySpec) -> Strategy:
    """Return a replay callable, or raise if the spec is outside the supported subset."""
    _require_supported(spec)

    def strategy(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        if not _covers(spec, book.market_ticker):
            return None
        probabilities: list[Decimal] = []
        for predicate in spec.entry_rules.all_of:
            observed = view.feature(predicate.feature, book.market_ticker)
            if observed is None or observed.value is None:
                return None
            if not _holds(observed.value, predicate):
                return None
            if predicate.feature.endswith("_probability") and ZERO <= observed.value <= ONE:
                probabilities.append(observed.value)
        ask = book.best_ask
        if not probabilities or ask is None:
            return None
        if max(probabilities) - ask.price < spec.minimum_edge:
            return None
        contracts = spec.position_sizing.contracts
        if contracts is None:
            return None
        return OrderIntent(
            intent_id=_intent_id(spec, book.received_at),
            strategy_id=spec.strategy_id,
            strategy_version=spec.version,
            contract=Contract(market_ticker=book.market_ticker, side=OutcomeSide.YES),
            yes_price=ask.price,
            quantity=contracts,
            time_in_force=spec.execution.time_in_force,
            decision_time=book.received_at,
            rationale=spec.hypothesis,
        )

    return strategy


def _require_supported(spec: StrategySpec) -> None:
    if spec.strategy_family is not StrategyFamily.INFORMATIONAL:
        raise UnsupportedSpecError("only informational specs are auto-backtested")
    sizing: PositionSizing = spec.position_sizing
    if sizing.method is not SizingMethod.FIXED_CONTRACTS or sizing.contracts is None:
        raise UnsupportedSpecError("only fixed_contracts sizing is auto-backtested")
    if spec.execution.post_only or spec.execution.time_in_force is _RESTING:
        raise UnsupportedSpecError("auto-backtest orders must be immediate, not resting")
    if "hold to settlement" not in spec.exit_rules.description.casefold():
        raise UnsupportedSpecError("exit rules must hold to settlement; other exits are not run")
    names = tuple(predicate.feature for predicate in spec.entry_rules.all_of)
    if not any(name.endswith("_probability") for name in names):
        raise UnsupportedSpecError(
            "entry rules need a *_probability feature so minimum_edge is checked"
        )


def _covers(spec: StrategySpec, ticker: str) -> bool:
    universe = spec.market_universe
    if ticker in universe.market_tickers:
        return True
    series = universe.series_tickers
    events = universe.event_tickers
    return any(ticker == item or ticker.startswith(f"{item}-") for item in (*series, *events))


def _holds(value: Decimal, predicate: Predicate) -> bool:
    threshold = predicate.threshold
    match predicate.op:
        case ComparisonOp.LT:
            return value < threshold
        case ComparisonOp.LE:
            return value <= threshold
        case ComparisonOp.GT:
            return value > threshold
        case ComparisonOp.GE:
            return value >= threshold
        case ComparisonOp.EQ:
            return value == threshold


def _intent_id(spec: StrategySpec, when: datetime) -> UUID:
    material = f"{spec.spec_hash()}|{when.isoformat()}".encode()
    return UUID(bytes=hashlib.sha256(material).digest()[:16])
