"""Baseline probabilities for a daily-high bracket.

Market-implied probability is the book's displayed midpoint. It is not an
executable price. Climatology and the calibrated blend use only CLI highs
whose ``available_at`` is at or before the decision. A fitted model is refused
until there are thirty scored days; this fixture set does not qualify.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from entropytrade.domain.market import Strike
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import ONE, ZERO, parse_probability
from entropytrade.domain.time import ensure_utc

MIN_ML_OBSERVATIONS = 30

Label = tuple[datetime, Decimal]
"""``(available_at, high_f)`` for one CLI day. The date is not required to score a strike."""


class InsufficientHistoryError(ValueError):
    """A baseline asked for prior labels that are not available yet."""


def market_implied_probability(book: OrderBook) -> Decimal:
    """Displayed midpoint. Callers that need a fill price use the bid or the ask."""
    if book.is_crossed or book.midpoint is None:
        raise ValueError("market-implied probability needs a two-sided uncrossed book")
    return parse_probability(book.midpoint)


def climatology_hit_rate(
    labels: Sequence[Label],
    *,
    decision_time: datetime,
    strike: Strike,
) -> Decimal:
    """Fraction of already-available CLI highs that would have resolved YES."""
    cutoff = ensure_utc(decision_time)
    prior = [high for available_at, high in labels if ensure_utc(available_at) <= cutoff]
    if not prior:
        raise InsufficientHistoryError("no CLI high is available at the decision")
    hits = sum(1 for high in prior if strike.resolves_yes(high))
    return parse_probability(Decimal(hits) / Decimal(len(prior)))


def raw_forecast_probability(forecast_high_f: Decimal, strike: Strike) -> Decimal:
    """One or zero, from whether the forecast value itself would resolve YES."""
    return ONE if strike.resolves_yes(forecast_high_f) else ZERO


def calibrate(raw: Decimal, climatology: Decimal) -> Decimal:
    """Average the raw indicator with the point-in-time climatology hit rate."""
    return parse_probability((parse_probability(raw) + parse_probability(climatology)) / 2)


def refuse_fitted_model(scored_days: int) -> None:
    """Do not fit a statistical or ML model on a short sample."""
    if scored_days < MIN_ML_OBSERVATIONS:
        raise InsufficientHistoryError(
            f"a fitted model needs at least {MIN_ML_OBSERVATIONS} scored days; got {scored_days}"
        )


def brier_score(pairs: Sequence[tuple[Decimal, bool]]) -> Decimal:
    """Mean squared error of probabilities against YES/NO outcomes."""
    if not pairs:
        raise InsufficientHistoryError("no scored days")
    total = ZERO
    for probability, happened in pairs:
        outcome = ONE if happened else ZERO
        total += (parse_probability(probability) - outcome) ** 2
    return total / Decimal(len(pairs))
