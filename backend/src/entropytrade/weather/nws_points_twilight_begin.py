"""Stored NWS points astronomical twilight begin string.

This module does not open a socket. The forecast body and the hourly body
are not used. The value counts when it is a non-empty string. A missing
parent is skipped and named. A missing or empty string is skipped and
named. Any other value is skipped and named. The string is not parsed
into a clock. A URL is not fetched. The string is not rewritten. The
string is not compared to 0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_POINTS = Path("nws/points-39.87--75.23.json")
_MANIFEST = Path("nws/forecast.manifest.json")
_PARENT = "missing astronomical data"
_MISSING = "missing astronomical twilight begin"
_OTHER = "astronomical twilight begin is not a string"


@dataclass(frozen=True)
class NwsPointsTwilightBegin:
    """The stored twilight begin. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_points_twilight_begin(root: Path) -> NwsPointsTwilightBegin:
    """Read the stored string. A missing value is not invented."""
    _require_untraded(root / _MANIFEST)
    value, reason = _begin(root / _POINTS)
    return NwsPointsTwilightBegin(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_points_twilight_begin_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_points_twilight_begin(root)
    if found.traded or found.promoted:
        raise ValueError("the twilight begin note must not trade")
    if found.value is None:
        listed = "No astronomical twilight begin string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS points astronomical twilight begin is recorded.",
            listed,
            "The forecast body was not used.",
            "The hourly body was not used.",
            "The string was not parsed into a clock.",
            "It was not used as a decision clock.",
            "A URL was not fetched.",
            "The string was not rewritten into another word.",
            "A missing string was not invented.",
            "It was not compared to 0.40 or to 2°F.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _require_untraded(path: Path) -> None:
    manifest = _object(path)
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the NWS points archive was traded or promoted")


def _begin(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get("astronomicalData")
    if not isinstance(raw, dict):
        return None, _PARENT
    item = _mapping(raw, "astronomicalData")
    value = item.get("astronomicalTwilightBegin")
    if value is None or value == "":
        return None, _MISSING
    if not isinstance(value, str):
        return None, _OTHER
    return value, None


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
