"""Stored NWS forecast units string.

This module does not open a socket. The hourly body is not used. The value
counts when it is a non-empty string. A missing or empty string is skipped
and named. Any other value is skipped and named. A unit is not converted
into another scale. The value is not compared to 0.40 or to 2°F. Nothing
is traded.
"""

from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_metadata import read_nws_metadata


@dataclass(frozen=True)
class NwsForecastUnits:
    """The stored units string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_forecast_units(root: Path) -> NwsForecastUnits:
    """Read the stored string. A missing value is not invented."""
    value, reason = read_nws_metadata(root, source="forecast", field="units")
    return NwsForecastUnits(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_forecast_units_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_units(root)
    if found.traded or found.promoted:
        raise ValueError("the units note must not trade")
    if found.value is None:
        listed = "No units string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast units string is recorded.",
            listed,
            "The hourly body was not used.",
            "A unit was not converted into another scale.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )
