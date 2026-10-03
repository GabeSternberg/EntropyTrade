"""Hour of day from stored observed-temperature timestamps. No socket.

The hour is the hour written in the timestamp. This module does not invent
a decision clock, add a threshold, or trade.
"""

from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.observed_temperature import load_observed_temperature

_STAMP = 16


@dataclass(frozen=True)
class HourOfDay:
    """One hour per stored timestamp. ``traded`` and ``promoted`` stay false."""

    hours: tuple[int, ...]
    count: int
    first_hour: int
    last_hour: int
    traded: bool
    promoted: bool


def load_hour_of_day(root: Path) -> HourOfDay:
    """Read hours from the stored observed-temperature archive."""
    archive = load_observed_temperature(root)
    if archive.traded or archive.promoted:
        raise ValueError("the observed-temperature archive was traded")
    hours = tuple(_hour(item) for item in archive.times)
    return HourOfDay(
        hours=hours,
        count=len(hours),
        first_hour=hours[0],
        last_hour=hours[-1],
        traded=False,
        promoted=False,
    )


def hour_of_day_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_hour_of_day(root)
    if found.traded or found.promoted:
        raise ValueError("the hour-of-day note must not trade")
    return " ".join(
        (
            "The Philadelphia hour-of-day record has",
            f"{found.count} hours taken from the observed-temperature timestamps.",
            "The hour is the hour in the timestamp.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _hour(stamp: str) -> int:
    if len(stamp) != _STAMP or stamp[10] != "T" or stamp[13] != ":":
        raise ValueError("an observed-temperature timestamp is not hourly text")
    text = stamp[11:13]
    if not text.isdigit():
        raise ValueError("an observed-temperature hour is not a number")
    hour = int(text)
    if hour > 23:
        raise ValueError("an observed-temperature hour is outside the day")
    return hour
