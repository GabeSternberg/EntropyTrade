"""Bounded data-only strategy execution. No ignored execution semantics or generated code."""

import hashlib
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from uuid import UUID

from entropytrade.backtest.replay import DecisionView, Strategy
from entropytrade.domain.enums import LiquidityRole, OutcomeSide, StrategyFamily, TimeInForce
from entropytrade.domain.market import Contract
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import ONE, QUANTITY_QUANTUM, ZERO
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.signals import EdgeEstimate
from entropytrade.domain.strategy import ComparisonOp, Predicate, SizingMethod, StrategySpec
from entropytrade.execution.fees import trade_fee


class UnsupportedSpecError(ValueError):
    """Valid data outside the executable bounded language."""


def compile_strategy(spec: StrategySpec) -> Strategy:
    """Validate the entire executable subset, then return its deterministic callable.

    Fee and portfolio context come from replay at the decision, not agent prose.
    A fixed-dollar budget includes estimated fees. Position caps include pending orders.
    """
    _require_supported(spec)
    names = [p.feature for p in spec.entry_rules.all_of if p.feature.endswith("_probability")]
    probability_name = spec.probability_feature or names[0]

    def strategy(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        when, ticker = view.decision_time, book.market_ticker
        if not _covers(spec, ticker):
            return None
        held = view.ledger.position(ticker) if view.ledger else None
        closing = (
            held is not None
            and held.contract.side is spec.side
            and spec.exit_mode == "predicate"
            and _rules(spec.exit_rules.all_of, view, book)
        )
        if closing:
            side = OutcomeSide.NO if spec.side is OutcomeSide.YES else OutcomeSide.YES
            limit = (
                book.best_bid.price
                if side is OutcomeSide.NO and book.best_bid
                else (book.best_ask.price if side is OutcomeSide.YES and book.best_ask else None)
            )
            if limit is None or held is None:
                return None
            return _intent(spec, when, ticker, side, limit, held.quantity, reduce=True)
        window = spec.entry_window
        if (window.start and when < window.start) or (window.end and when >= window.end):
            return None
        if window.target_start or window.target_end:
            if view.target_date is None:
                return None
            if (window.target_start and view.target_date < window.target_start) or (
                window.target_end and view.target_date >= window.target_end
            ):
                return None
        if book.is_crossed or book.spread is None:
            return None
        if spec.execution.max_spread is not None and book.spread > spec.execution.max_spread:
            return None
        if not _rules(spec.entry_rules.all_of, view, book):
            return None
        for requirement in spec.features:
            value = view.feature(requirement.name, ticker)
            if value is None or (
                requirement.version is not None and value.feature_version != requirement.version
            ):
                return None
        probability = view.feature(probability_name, ticker)
        if probability is None or probability.value is None or not ZERO <= probability.value <= ONE:
            return None
        if spec.model_ref and (
            probability.source_id != spec.model_ref.family
            or probability.input_manifest_hash != spec.model_ref.version
        ):
            return None
        if view.schedule is None:
            raise UnsupportedSpecError("an explicit fee schedule is required at decision time")
        touch = book.best_ask if spec.side is OutcomeSide.YES else book.best_bid
        if touch is None or (
            spec.min_displayed_quantity is not None and touch.quantity < spec.min_displayed_quantity
        ):
            return None
        cost = touch.price if spec.side is OutcomeSide.YES else ONE - touch.price
        limit_cost = min(Decimal("0.9999"), cost + spec.slippage_allowance).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )
        if limit_cost <= ZERO:
            return None
        if spec.max_entry_price is not None and limit_cost > spec.max_entry_price:
            return None
        yes_limit = limit_cost if spec.side is OutcomeSide.YES else ONE - limit_cost
        # Reserve an extra cent per additional possible depth slice, bounding rounding
        # if a slippage-tolerant order spans multiple recorded levels.
        levels = book.asks if spec.side is OutcomeSide.YES else book.bids
        slices = sum(
            1
            for level in levels
            if (
                level.price <= yes_limit
                if spec.side is OutcomeSide.YES
                else level.price >= yes_limit
            )
        )
        sizing = spec.position_sizing
        current = held.quantity if held and held.contract.side is spec.side else ZERO
        room = sizing.max_contracts - current - view.pending.get((ticker, spec.side), ZERO)
        quantity = min(sizing.contracts or sizing.max_contracts, room)
        if sizing.method is SizingMethod.FIXED_DOLLARS:
            budget = sizing.dollars or ZERO
            low, high = 0, int(max(ZERO, room) / QUANTITY_QUANTUM)
            while low < high:
                middle = (low + high + 1) // 2
                size = middle * QUANTITY_QUANTUM
                fee = trade_fee(
                    view.schedule, yes_price=Decimal("0.5"), quantity=size, role=LiquidityRole.TAKER
                )
                if limit_cost * size + fee + max(0, slices - 1) * Decimal("0.01") <= budget:
                    low = middle
                else:
                    high = middle - 1
            quantity = low * QUANTITY_QUANTUM
        quantity = quantity.quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
        if quantity <= ZERO:
            return None
        fee = trade_fee(
            view.schedule, yes_price=Decimal("0.5"), quantity=quantity, role=LiquidityRole.TAKER
        )
        fee += max(0, slices - 1) * Decimal("0.01")
        edge = EdgeEstimate(
            outcome_probability=probability.value
            if spec.side is OutcomeSide.YES
            else ONE - probability.value,
            price_per_contract=limit_cost,
            fee_per_contract=(fee / quantity).quantize(Decimal("0.000001"), rounding=ROUND_CEILING),
            model_uncertainty_reserve=spec.uncertainty_allowance,
        )
        if edge.net_edge < spec.minimum_edge:
            return None
        intent = _intent(spec, when, ticker, spec.side, yes_limit, quantity, reduce=False)
        return intent.revalidated(edge=edge)

    return strategy


def _require_supported(spec: StrategySpec) -> None:
    if spec.strategy_family is not StrategyFamily.INFORMATIONAL:
        raise UnsupportedSpecError("only informational strategies are executable")
    sizing = spec.position_sizing
    if sizing.method not in {SizingMethod.FIXED_CONTRACTS, SizingMethod.FIXED_DOLLARS}:
        raise UnsupportedSpecError("only fixed_contracts or fixed_dollars sizing is supported")
    if (
        sizing.kelly_fraction is not None
        or (sizing.method is SizingMethod.FIXED_CONTRACTS and sizing.dollars is not None)
        or (sizing.method is SizingMethod.FIXED_DOLLARS and sizing.contracts is not None)
    ):
        raise UnsupportedSpecError("inapplicable sizing fields are not ignored")
    if spec.execution.post_only or spec.execution.time_in_force is TimeInForce.GOOD_TILL_CANCELED:
        raise UnsupportedSpecError("only immediate taker orders are supported")
    if spec.hedging_rules:
        raise UnsupportedSpecError("hedging is not implemented")
    if spec.maximum_holding_period_seconds is not None:
        raise UnsupportedSpecError(
            "holding-duration exits need lot-level clocks and are unsupported"
        )
    if spec.exit_mode == "hold_to_settlement":
        if "hold to settlement" not in spec.exit_rules.description.casefold():
            raise UnsupportedSpecError("hold-to-settlement exits must identify settlement")
        if any(
            p.feature not in {"settlement", "hold_to_settlement"}
            or p.op is not ComparisonOp.EQ
            or p.threshold != 1
            for p in spec.exit_rules.all_of
        ):
            raise UnsupportedSpecError("only the settlement marker is allowed in settlement exits")
    names = {p.feature for p in spec.entry_rules.all_of if p.feature.endswith("_probability")}
    if spec.probability_feature:
        if spec.probability_feature not in {p.feature for p in spec.entry_rules.all_of}:
            raise UnsupportedSpecError("probability_feature must be part of the entry predicates")
    elif len(names) != 1:
        raise UnsupportedSpecError(
            "exactly one *_probability feature or explicit probability_feature is required"
        )
    for predicate in spec.entry_rules.all_of:
        if predicate.feature.endswith("_probability") and not ZERO <= predicate.threshold <= ONE:
            raise UnsupportedSpecError("probability predicates must be in [0,1]")


def _rules(predicates: tuple[Predicate, ...], view: DecisionView, book: OrderBook) -> bool:
    for predicate in predicates:
        builtin = {
            "yes_bid": book.best_bid.price if book.best_bid else None,
            "yes_ask": book.best_ask.price if book.best_ask else None,
        }
        row = view.feature(predicate.feature, book.market_ticker)
        value = (
            builtin.get(predicate.feature)
            if predicate.feature in builtin
            else (row.value if row else None)
        )
        if value is None or not _holds(value, predicate):
            return False
    return True


def _covers(spec: StrategySpec, ticker: str) -> bool:
    universe = spec.market_universe
    return ticker in universe.market_tickers or any(
        ticker.startswith(item + "-") or ticker == item
        for item in (*universe.series_tickers, *universe.event_tickers)
    )


def _holds(value: Decimal, predicate: Predicate) -> bool:
    match predicate.op:
        case ComparisonOp.LT:
            return value < predicate.threshold
        case ComparisonOp.LE:
            return value <= predicate.threshold
        case ComparisonOp.GT:
            return value > predicate.threshold
        case ComparisonOp.GE:
            return value >= predicate.threshold
        case ComparisonOp.EQ:
            return value == predicate.threshold


def _intent(
    spec: StrategySpec,
    when: datetime,
    ticker: str,
    side: OutcomeSide,
    price: Decimal,
    quantity: Decimal,
    *,
    reduce: bool,
) -> OrderIntent:
    identifier = UUID(
        bytes=hashlib.sha256(
            f"{spec.spec_hash()}|{when.isoformat()}|{ticker}|{side}|{reduce}".encode()
        ).digest()[:16]
    )
    return OrderIntent(
        intent_id=identifier,
        strategy_id=spec.strategy_id,
        strategy_version=spec.version,
        contract=Contract(market_ticker=ticker, side=side),
        yes_price=price,
        quantity=quantity,
        time_in_force=spec.execution.time_in_force,
        reduce_only=reduce,
        expires_at=None if reduce else spec.entry_window.end,
        decision_time=when,
        rationale=spec.hypothesis,
    )
