"""Mexico City series listing. No station was named, so nothing is scored.

``KXHIGHTMMMX`` is the next ticker after Oklahoma City. The public market
list and the public event list are empty. The sample B80.5 ticker is
``not_found``. This module does not invent a station, a strike, or a
forecast. Nothing is promoted. This module does not open a socket.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MexicoCityListing:
    """The stored listing. ``scored`` stays false."""

    series: str
    title: str
    markets_listed: int
    events_listed: int
    sample_ticker: str
    sample_http_status: int
    sample_error_code: str
    station_named: bool
    scored: bool
    promoted: bool


def load_mexico_city_listing(root: Path) -> MexicoCityListing:
    """Read the stored listing. A missing station is not filled in."""
    folder = root / "mexicocity"
    manifest = _object(folder / "manifest.json")
    series = _object(folder / "series.json")["series"]
    if not isinstance(series, dict):
        raise ValueError("Mexico City series is not an object")
    markets = _object(folder / "markets.json")
    events = _object(folder / "events.json")
    sample = _object(folder / "sample-market.json")
    if series.get("ticker") != "KXHIGHTMMMX":
        raise ValueError("Mexico City series ticker changed")
    if markets.get("markets") != []:
        raise ValueError("Mexico City market list is no longer empty")
    if events.get("events") != []:
        raise ValueError("Mexico City event list is no longer empty")
    error = sample.get("error")
    if not isinstance(error, dict) or error.get("code") != "not_found":
        raise ValueError("Mexico City sample is not a not_found body")
    if manifest.get("station_named") is not False or manifest.get("scored") is not False:
        raise ValueError("Mexico City was scored without a named station")
    if manifest.get("promoted") is not False:
        raise ValueError("Mexico City is promoted")
    title = series.get("title")
    if not isinstance(title, str) or title == "":
        raise ValueError("Mexico City title is missing")
    return MexicoCityListing(
        series="KXHIGHTMMMX",
        title=title,
        markets_listed=0,
        events_listed=0,
        sample_ticker="KXHIGHTMMMX-26AUG23-B80.5",
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
