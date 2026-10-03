"""Stored NWS points document type string.

This module does not open a socket. The forecast body and the hourly body
are not used. Geometry is not read. The value counts when it is a
non-empty string. A missing or empty string is skipped and named. Any
other value is skipped and named. The string is not rewritten into
another word. The string is not compared to 0.40 or to 2°F. Nothing is
traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_POINTS = Path("nws/points-39.87--75.23.json")
_MANIFEST = Path("nws/forecast.manifest.json")
_MISSING = "missing type"
_OTHER = "type is not a string"


@dataclass(frozen=True)
class NwsPointsType:
    """The stored document type. ``traded`` and ``promoted`` stay false."""

    value: str | None
    reason: str | None
    traded: bool
    promoted: bool


def load_nws_points_type(root: Path) -> NwsPointsType:
    """Read the stored string. A missing value is not invented."""
    _require_untraded(root / _MANIFEST)
    value, reason = _document_type(root / _POINTS)
    return NwsPointsType(
        value=value,
        reason=reason,
        traded=False,
        promoted=False,
    )


def nws_points_type_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_points_type(root)
    if found.traded or found.promoted:
        raise ValueError("the points type note must not trade")
    if found.value is None:
        listed = "No type string was stored."
    else:
        listed = f"The stored string is {found.value}."
    return " ".join(
        (
            "The stored Philadelphia NWS points document type string is recorded.",
            listed,
            "The forecast body was not used.",
            "The hourly body was not used.",
            "Geometry was not read.",
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


def _document_type(path: Path) -> tuple[str | None, str | None]:
    body = _object(path)
    raw = body.get("type")
    if raw is None or raw == "":
        return None, _MISSING
    if not isinstance(raw, str):
        return None, _OTHER
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
