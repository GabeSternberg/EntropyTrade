"""Stored NWS hourly updateTime string.

This module does not open a socket. The 14-period forecast body is not
used. The value counts when it is a non-empty string. A missing or empty
string is skipped and named. The string is not parsed into a clock and is
not used as a decision clock. The string is not compared to 0.40 or to
2°F. Nothing is traded.
"""

from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_metadata import read_nws_metadata


@dataclass(frozen=True)
class NwsHourlyUpdateTime:
    """The stored update string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_hourly_update_time(root: Path) -> NwsHourlyUpdateTime:
    """Read the stored string. A missing value is not invented."""
    value, reason = read_nws_metadata(root, source="hourly", field="updateTime")
    return NwsHourlyUpdateTime(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_hourly_update_time_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly_update_time(root)
    if found.traded or found.promoted:
        raise ValueError("the hourly updateTime note must not trade")
    if found.value is None:
        listed = "No updateTime string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly updateTime string is recorded.",
            listed,
            "The 14-period forecast body was not used.",
            "The string was not parsed into a clock.",
            "It was not used as a decision clock.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
