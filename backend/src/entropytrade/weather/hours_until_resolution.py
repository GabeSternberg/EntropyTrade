"""Hours from the stored decision clock to each CLI label. No socket.

The decision time is 15:00 UTC on the valid day. A negative span is kept.
This module does not add a threshold or trade.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.revision_rule import DECISION_HOUR_UTC

_DAY_SECONDS = Decimal(86400)
_HOUR_SECONDS = Decimal(3600)
_MICRO = Decimal(1_000_000)


@dataclass(frozen=True)
class ResolutionHours:
    """One label. ``hours`` may be negative. ``traded`` stays false."""

    valid_on: str
    hours: Decimal


@dataclass(frozen=True)
class ResolutionRecord:
    """Every stored Philadelphia label. ``promoted`` stays false."""

    rows: tuple[ResolutionHours, ...]
    negative: int
    traded: bool
    promoted: bool


def load_hours_until_resolution(root: Path) -> ResolutionRecord:
    """Read stored labels. Missing ``available_at`` is not invented."""
    if DECISION_HOUR_UTC != 15:
        raise ValueError("the decision hour was changed")
    labels, _comparison = load_comparison(root)
    rows = tuple(_row(label) for label in sorted(labels, key=lambda item: item.valid_on))
    return ResolutionRecord(
        rows=rows,
        negative=sum(1 for item in rows if item.hours < 0),
        traded=False,
        promoted=False,
    )


def hours_until_resolution_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_hours_until_resolution(root)
    if found.traded or found.promoted:
        raise ValueError("the resolution-hours note must not trade")
    return " ".join(
        (
            "The Philadelphia hours-until-resolution record has",
            f"{len(found.rows)} labels and {found.negative} negative spans.",
            "The decision time is 15:00 UTC on the valid day.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _row(label: CliLabel) -> ResolutionHours:
    if label.available_at.tzinfo is None:
        raise ValueError("a CLI label has no available_at timezone")
    decision = datetime(
        label.valid_on.year,
        label.valid_on.month,
        label.valid_on.day,
        DECISION_HOUR_UTC,
        tzinfo=UTC,
    )
    delta = label.available_at - decision
    seconds = (
        Decimal(delta.days) * _DAY_SECONDS
        + Decimal(delta.seconds)
        + Decimal(delta.microseconds) / _MICRO
    )
    return ResolutionHours(valid_on=label.valid_on.isoformat(), hours=seconds / _HOUR_SECONDS)
