"""Stored NWS hourly generatedAt string.

This module does not open a socket. The 14-period forecast body is not
used. The value counts when it is a non-empty string. A missing or empty
string is skipped and named. The string is not parsed into a clock and is
not used as a decision clock. The string is not compared to 0.40 or to
2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing generatedAt"


@dataclass(frozen=True)
class NwsHourlyGeneratedAt:
    """The stored generation string. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_hourly_generated_at(root: Path) -> NwsHourlyGeneratedAt:
    """Read the stored string. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    value, reason = _generated_at(root / _HOURLY)
    return NwsHourlyGeneratedAt(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_hourly_generated_at_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly_generated_at(root)
    if found.traded or found.promoted:
        raise ValueError("the hourly generatedAt note must not trade")
    if found.value is None:
        listed = "No generatedAt string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly generatedAt string is recorded.",
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


def _generated_at(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get("generatedAt")
    if raw is None or raw == "":
        return None, _MISSING
    if not isinstance(raw, str):
        raise ValueError("generatedAt is not text")
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
