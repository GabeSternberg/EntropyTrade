"""Stored HRRR request that was not HTTP 200. This module does not open a socket.

No temperature series is invented from the error body.
"""

import json
from dataclasses import dataclass
from pathlib import Path

_BODY = Path("open-meteo/hrrr-error.json")
_MANIFEST = Path("open-meteo/hrrr-error.manifest.json")
_HOST = "https://api.open-meteo.com/"


@dataclass(frozen=True)
class HrrrArchive:
    """The stored failure. ``traded`` and ``promoted`` stay false."""

    http_status: int
    reason: str
    temperatures_invented: bool
    traded: bool
    promoted: bool


def load_hrrr_archive(root: Path) -> HrrrArchive:
    """Read the stored error. A temperature is not filled in."""
    manifest = _object(root / _MANIFEST)
    url = _text(manifest.get("url"), "url")
    if not url.startswith(_HOST) or _query(url, "models") != "hrrr":
        raise ValueError("the HRRR call was changed")
    if manifest.get("http_status") != 400:
        raise ValueError("the HRRR status was changed")
    if manifest.get("promoted") is not False or manifest.get("traded") is not False:
        raise ValueError("the HRRR archive was traded or promoted")
    body = _object(root / _BODY)
    if body.get("error") is not True:
        raise ValueError("the HRRR body is not the stored error")
    if "hourly" in body:
        raise ValueError("the HRRR error invented an hourly series")
    return HrrrArchive(
        http_status=400,
        reason=_text(body.get("reason"), "reason"),
        temperatures_invented=False,
        traded=False,
        promoted=False,
    )


def hrrr_archive_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_hrrr_archive(root)
    if found.traded or found.promoted or found.temperatures_invented:
        raise ValueError("the HRRR note must not trade")
    return " ".join(
        (
            "The Philadelphia HRRR request returned HTTP",
            f"{found.http_status}.",
            "No temperature series was invented.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _query(url: str, key: str) -> str:
    if "?" not in url:
        raise ValueError("the HRRR url has no query")
    for part in url.split("?", 1)[1].split("&"):
        name, separator, value = part.partition("=")
        if separator == "=" and name == key and value != "":
            return value
    raise ValueError(f"the HRRR url has no {key}")


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} has a non-string key")
        mapped[key] = item
    return mapped


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value
