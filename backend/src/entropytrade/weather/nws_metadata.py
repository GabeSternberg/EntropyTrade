"""Shared parser for recorded NWS forecast metadata.

These strings describe the source document; they are not verified availability
clocks or trading features. The legacy field loaders retain their public result
types and research notes, but all ten use this validation and parsing boundary.
"""

import json
from pathlib import Path
from typing import Literal

from entropytrade.weather.nws_forecast import load_nws_forecast, load_nws_hourly

NwsSource = Literal["forecast", "hourly"]
NwsMetadataField = Literal["generatedAt", "updateTime", "validTimes", "forecastGenerator", "units"]

_FILES: dict[NwsSource, str] = {
    "forecast": "nws/forecast-phi-48-75.json",
    "hourly": "nws/forecast-hourly-phi-48-75.json",
}


def read_nws_metadata(
    root: Path, *, source: NwsSource, field: NwsMetadataField
) -> tuple[str | None, str | None]:
    """Read one property after checking the archive manifest and points URL.

    Missing values stay missing. Legacy units loaders name a malformed value;
    the timestamp and generator loaders raise. No string is parsed as a clock.
    """
    if source == "hourly":
        load_nws_hourly(root)
    else:
        load_nws_forecast(root)
    payload: object = json.loads((root / _FILES[source]).read_text(encoding="utf-8"))
    body = _mapping(payload, _FILES[source])
    properties = _mapping(body.get("properties"), "properties")
    raw = properties.get(field)
    if raw is None or raw == "":
        return None, f"missing {field}"
    if not isinstance(raw, str):
        if field == "units":
            return None, "units is not a string"
        raise ValueError(f"{field} is not text")
    return raw, None


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{label} has a non-string key")
        mapped[key] = item
    return mapped
