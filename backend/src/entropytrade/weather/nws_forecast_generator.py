"""Stored NWS forecast generator string.

This module does not open a socket. The hourly body is not used. The value
counts when it is a non-empty string. A missing or empty string is skipped
and named. The string is not rewritten into another word. The string is
not compared to 0.40 or to 2°F. Nothing is traded.
"""

from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_metadata import read_nws_metadata


@dataclass(frozen=True)
class NwsForecastGenerator:
    """The stored generator string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_forecast_generator(root: Path) -> NwsForecastGenerator:
    """Read the stored string. A missing value is not invented."""
    value, reason = read_nws_metadata(root, source="forecast", field="forecastGenerator")
    return NwsForecastGenerator(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_forecast_generator_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_generator(root)
    if found.traded or found.promoted:
        raise ValueError("the forecastGenerator note must not trade")
    if found.value is None:
        listed = "No forecastGenerator string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast generator string is recorded.",
            listed,
            "The hourly body was not used.",
            "The string was not rewritten into another word.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
