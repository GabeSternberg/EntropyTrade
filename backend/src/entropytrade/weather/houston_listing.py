"""Houston series listing. No station was named, so nothing is scored.

``KXHIGHHOU`` is the next ticker after Amsterdam. The settled market list
is empty. The sample B80.5 ticker is ``not_found``. This module does not
invent a station or a forecast. Nothing is promoted. This module does not
open a socket.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HoustonListing:
    """The stored listing. ``scored`` stays false."""

    series: str
    title: str
    markets_listed: int
    sample_ticker: str
    sample_http_status: int
    sample_error_code: str
    station_named: bool
    scored: bool
    promoted: bool


def load_houston_listing(root: Path) -> HoustonListing:
    """Read the stored listing. A missing station is not filled in."""
    folder = root / "houston"
    manifest = _object(folder / "manifest.json")
    series_body = _object(folder / "series.json")
    series = series_body.get("series")
    if not isinstance(series, dict):
        raise ValueError("Houston series is not an object")
    markets = _object(folder / "markets.json")
    sample = _object(folder / "sample-market.json")
    if series.get("ticker") != "KXHIGHHOU":
        raise ValueError("Houston series ticker changed")
    if markets.get("markets") != []:
        raise ValueError("Houston market list is no longer empty")
    error = sample.get("error")
    if not isinstance(error, dict) or error.get("code") != "not_found":
        raise ValueError("Houston sample is not a not_found body")
    if manifest.get("station_named") is not False or manifest.get("scored") is not False:
        raise ValueError("Houston was scored without a named station")
    if manifest.get("promoted") is not False:
        raise ValueError("Houston is promoted")
    title = series.get("title")
    if not isinstance(title, str) or title == "":
        raise ValueError("Houston title is missing")
    return HoustonListing(
        series="KXHIGHHOU",
        title=title,
        markets_listed=0,
        sample_ticker="KXHIGHHOU-26AUG23-B80.5",
        sample_http_status=404,
        sample_error_code="not_found",
        station_named=False,
        scored=False,
        promoted=False,
    )


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
