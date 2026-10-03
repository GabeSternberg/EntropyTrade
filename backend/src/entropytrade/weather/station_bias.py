"""Arithmetic mean of the stored previous-day errors. No socket.

The mean is not subtracted from a forecast and it is not a threshold.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.previous_day_error import load_previous_day_errors

_DAYS = 39


@dataclass(frozen=True)
class StationBias:
    """One mean. ``traded`` and ``promoted`` stay false."""

    days: int
    total: Decimal
    mean: Decimal
    traded: bool
    promoted: bool


def load_station_bias(root: Path) -> StationBias:
    """Average the eligible errors. Skipped days stay out."""
    found = load_previous_day_errors(root)
    if found.traded or found.promoted:
        raise ValueError("the previous-day errors were traded")
    if len(found.errors) != _DAYS:
        raise ValueError("the eligible day count changed")
    total = sum((item.error for item in found.errors), start=Decimal(0))
    return StationBias(
        days=_DAYS,
        total=total,
        mean=total / Decimal(_DAYS),
        traded=False,
        promoted=False,
    )


def station_bias_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_station_bias(root)
    if found.traded or found.promoted:
        raise ValueError("the station-bias note must not trade")
    return " ".join(
        (
            "The Philadelphia station-bias record is the mean of",
            f"{found.days} eligible previous-day errors.",
            f"The mean is {format(found.mean, 'f')} °F.",
            "It is not subtracted from a forecast.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
