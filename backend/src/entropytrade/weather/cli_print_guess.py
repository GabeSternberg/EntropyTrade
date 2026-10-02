"""Last 2026 B80.5 print before 15:00 UTC, versus the CLI bracket.

The YES line is the same 0.50 used on the historical tape. The clock is the
same 15:00 UTC decision the registered rules already use. A print at or
after the label time is too late. A day with no earlier print gets no
guess. This is not a guaranteed fill and it is not promoted. The historical
trade table is not read. This module does not open a socket.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.exchange.trade_prints import TradePrint, load_trade_tape
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.last_print import GUESS_YES_AT

_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(80), cap=Decimal(81))
DECISION_HOUR = 15


@dataclass(frozen=True)
class CliPrintGuess:
    """How often the pre-decision print matches the CLI bracket."""

    days: int
    with_prints: int
    without_prints: int
    guesses_yes: int
    agreements: int
    fidelity: str
    guaranteed_fill: bool
    promoted: bool


def load_cli_print_guess(root: Path) -> CliPrintGuess:
    """Score the 2026 tape. Days with no eligible print get no guess."""
    labels, _comparison = load_comparison(root)
    return score_cli_print_guess(labels, load_trade_tape(root).b805_prints)


def score_cli_print_guess(
    labels: tuple[CliLabel, ...],
    prints: tuple[TradePrint, ...],
) -> CliPrintGuess:
    """Score only the labels that were passed in."""
    by_day = _prints_by_day(prints)
    guesses_yes = 0
    agreements = 0
    with_prints = 0
    for label in labels:
        price = _last_price(by_day.get(label.valid_on, ()), label.available_at, label.valid_on)
        if price is None:
            continue
        with_prints += 1
        guess_yes = price >= GUESS_YES_AT
        if guess_yes:
            guesses_yes += 1
        if guess_yes == _STRIKE.resolves_yes(label.high_f):
            agreements += 1
    return CliPrintGuess(
        days=len(labels),
        with_prints=with_prints,
        without_prints=len(labels) - with_prints,
        guesses_yes=guesses_yes,
        agreements=agreements,
        fidelity="trade-print",
        guaranteed_fill=False,
        promoted=False,
    )


def _prints_by_day(prints: tuple[TradePrint, ...]) -> dict[date, tuple[TradePrint, ...]]:
    grouped: dict[date, list[TradePrint]] = {}
    for item in prints:
        valid_on = ticker_target_date(item.ticker)
        if valid_on is None:
            continue
        grouped.setdefault(valid_on, []).append(item)
    return {day: tuple(items) for day, items in grouped.items()}


def _last_price(
    prints: tuple[TradePrint, ...],
    available_at: datetime,
    valid_on: date,
) -> Decimal | None:
    decision = datetime(valid_on.year, valid_on.month, valid_on.day, DECISION_HOUR, tzinfo=UTC)
    eligible = [
        item
        for item in prints
        if item.created_at <= decision and item.created_at < available_at and item.count > 0
    ]
    if not eligible:
        return None
    latest = max(item.created_at for item in eligible)
    return max(item.yes_price for item in eligible if item.created_at == latest)
