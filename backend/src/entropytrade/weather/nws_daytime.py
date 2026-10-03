"""Daytime and nighttime counts on the NWS hourly archive.

This module does not open a socket. A period is daytime when
``isDaytime`` is the boolean true, and nighttime when it is the boolean
false. Any other value is skipped and named. Daytime is not a trading
session. The counts are not compared to 0.40. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_hourly

_HOURLY = Path("nws/forecast-hourly-phi-48-75.json")
_OTHER = "isDaytime is not a boolean"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose isDaytime value was not a boolean."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsDaytime:
    """Daytime and nighttime counts. ``traded`` and ``promoted`` stay false."""

    periods: int
    daytime: int
    nighttime: int
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_daytime(root: Path) -> NwsDaytime:
    """Count stored daytime and nighttime periods. Other values are named."""
    hourly = load_nws_hourly(root)
    if hourly.traded or hourly.promoted:
        raise ValueError("the NWS hourly archive was traded")
    daytime = 0
    nighttime = 0
    skipped: list[SkippedPeriod] = []
    for start, value in _flags(root / _HOURLY):
        if value is True:
            daytime += 1
            continue
        if value is False:
            nighttime += 1
            continue
        skipped.append(SkippedPeriod(start, _OTHER))
    return NwsDaytime(
        periods=daytime + nighttime + len(skipped),
        daytime=daytime,
        nighttime=nighttime,
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_daytime_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_daytime(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the daytime note must not trade")
    return " ".join(
        (
            "The stored Philadelphia NWS hourly periods have",
            f"{found.daytime} daytime periods and {found.nighttime} nighttime periods.",
            f"{len(found.skipped)} periods were not a boolean and were not filled in.",
            "Daytime was not treated as a trading session.",
            "The counts were not compared to 0.40.",
            "They were not aligned to the CLI decision clock.",
            "They are not a CLI rescore column.",
            "They are not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _flags(path: Path) -> tuple[tuple[str, bool | None], ...]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    body: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} has a non-string key")
        body[key] = item
    properties = body.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("properties is not an object")
    periods = properties.get("periods")
    if not isinstance(periods, list):
        raise ValueError("periods is not a list")
    found: list[tuple[str, bool | None]] = []
    for item in periods:
        if not isinstance(item, dict):
            raise ValueError("period is not an object")
        start = item.get("startTime")
        if not isinstance(start, str) or start == "":
            raise ValueError("startTime is missing")
        raw = item.get("isDaytime")
        if raw is True or raw is False:
            found.append((start, raw))
            continue
        found.append((start, None))
    return tuple(found)
