"""Stored NWS hourly @context strings.

This module does not open a socket. The 14-period forecast body is not
used. A non-empty string is recorded. A list of non-empty strings is
recorded in alphabetical order. A URL is not fetched. A string is not
rewritten. The value is not compared to 0.40 or to 2°F. Nothing is
traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_MISSING = "missing context"
_OTHER = "context is not a string"


@dataclass(frozen=True)
class NwsHourlyContext:
    """The stored context strings. ``traded`` and ``promoted`` stay false."""

    values: tuple[str, ...]
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_hourly_context(root: Path) -> NwsHourlyContext:
    """Read the stored strings. A missing value is not invented."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    values, reason = _context(root / _HOURLY)
    return NwsHourlyContext(
        values=values,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_hourly_context_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_hourly_context(root)
    if found.traded or found.promoted:
        raise ValueError("the hourly context note must not trade")
    if found.values:
        listed = f"In alphabetical order they are {', '.join(found.values)}."
    else:
        listed = "In alphabetical order there are no strings."
    return " ".join(
        (
            "The stored Philadelphia NWS hourly context strings are recorded.",
            f"{len(found.values)} strings were stored.",
            listed,
            "The 14-period forecast body was not used.",
            "A URL was not fetched.",
            "A string was not rewritten.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _context(path: Path) -> tuple[tuple[str, ...], str | None]:
    body = _object(path)
    raw = body.get("@context")
    if raw is None or raw == "":
        return (), _MISSING
    if isinstance(raw, str):
        return (raw,), None
    if not isinstance(raw, list):
        return (), _OTHER
    found: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item == "":
            return (), _OTHER
        found.append(item)
    if not found:
        return (), _MISSING
    return tuple(sorted(set(found))), None


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
