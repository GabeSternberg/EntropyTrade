"""Calendar month from stored observed-temperature timestamps. No socket.

The month is the month written in the timestamp. Months are not bucketed
into named seasons. This module does not add a threshold or trade.
"""

from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.observed_temperature import load_observed_temperature

_STAMP = 16


@dataclass(frozen=True)
class Seasonality:
    """One month per stored timestamp. ``traded`` and ``promoted`` stay false."""

    months: tuple[int, ...]
    count: int
    first_month: int
    last_month: int
    traded: bool
    promoted: bool


def load_seasonality(root: Path) -> Seasonality:
    """Read months from the stored observed-temperature archive."""
    archive = load_observed_temperature(root)
    if archive.traded or archive.promoted:
        raise ValueError("the observed-temperature archive was traded")
    months = tuple(_month(item) for item in archive.times)
    return Seasonality(
        months=months,
        count=len(months),
        first_month=months[0],
        last_month=months[-1],
        traded=False,
        promoted=False,
    )


def seasonality_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_seasonality(root)
    if found.traded or found.promoted:
        raise ValueError("the seasonality note must not trade")
    return " ".join(
        (
            "The Philadelphia seasonality record has",
            f"{found.count} months taken from the observed-temperature timestamps.",
            "The month is the month in the timestamp.",
            "Months are not bucketed into named seasons.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _month(stamp: str) -> int:
    if len(stamp) != _STAMP or stamp[4] != "-" or stamp[7] != "-" or stamp[10] != "T":
        raise ValueError("an observed-temperature timestamp is not hourly text")
    text = stamp[5:7]
    if not text.isdigit():
        raise ValueError("an observed-temperature month is not a number")
    month = int(text)
    if month < 1 or month > 12:
        raise ValueError("an observed-temperature month is outside the year")
    return month
