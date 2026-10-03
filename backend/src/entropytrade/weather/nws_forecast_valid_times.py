"""Stored NWS forecast validTimes string.

This module does not open a socket. The hourly body is not used. The value
counts when it is a non-empty string. A missing or empty string is skipped
and named. The string is not parsed into a clock. A duration is not
computed. The string is not used as a decision clock. The string is not
compared to 0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_MISSING = "missing validTimes"


@dataclass(frozen=True)
class NwsForecastValidTimes:
    """The stored valid-times string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_forecast_valid_times(root: Path) -> NwsForecastValidTimes:
    """Read the stored string. A missing value is not invented."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    value, reason = _valid_times(root / _FORECAST)
    return NwsForecastValidTimes(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_forecast_valid_times_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_valid_times(root)
    if found.traded or found.promoted:
        raise ValueError("the validTimes note must not trade")
    if found.value is None:
        listed = "No validTimes string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast validTimes string is recorded.",
            listed,
            "The hourly body was not used.",
            "The string was not parsed into a clock.",
            "A duration was not computed.",
            "It was not used as a decision clock.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _valid_times(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get("validTimes")
    if raw is None or raw == "":
        return None, _MISSING
    if not isinstance(raw, str):
        raise ValueError("validTimes is not text")
    return raw, None


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(payload, path.name)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} has a non-string key")
        mapped[key] = item
    return mapped
