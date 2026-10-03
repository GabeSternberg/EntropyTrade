"""Distinct NWS forecast-period numbers.

This module does not open a socket. The hourly body is not used. A number
counts when it is an integer. A boolean is not an integer. A missing value
is skipped as missing number. A non-integer is skipped as number is not an
integer. A missing number is not invented. The count is not compared to
0.40 or to 2°F. Nothing is traded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.nws_forecast import load_nws_forecast

_FORECAST = Path("nws/forecast-phi-48-75.json")
_MISSING = "missing number"
_OTHER = "number is not an integer"


@dataclass(frozen=True)
class SkippedPeriod:
    """A named period whose number was missing or not an integer."""

    start: str
    reason: str


@dataclass(frozen=True)
class NwsForecastNumber:
    """Distinct period numbers. ``traded`` and ``promoted`` stay false."""

    periods: int
    values: tuple[int, ...]
    skipped: tuple[SkippedPeriod, ...]
    traded: bool
    promoted: bool


def load_nws_forecast_number(root: Path) -> NwsForecastNumber:
    """Count the stored period numbers. A missing value is not invented."""
    forecast = load_nws_forecast(root)
    if forecast.traded or forecast.promoted:
        raise ValueError("the NWS forecast archive was traded")
    found: list[int] = []
    skipped: list[SkippedPeriod] = []
    for start, value, reason in _numbers(root / _FORECAST):
        if value is None:
            skipped.append(SkippedPeriod(start, reason))
            continue
        found.append(value)
    return NwsForecastNumber(
        periods=len(found) + len(skipped),
        values=tuple(sorted(set(found))),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def nws_forecast_number_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_nws_forecast_number(root)
    if found.traded or found.promoted or found.periods == 0:
        raise ValueError("the forecast period-number note must not trade")
    if found.values:
        listed = (
            "In ascending order they are " + ", ".join(str(item) for item in found.values) + "."
        )
    else:
        listed = "In ascending order there are no integers."
    return " ".join(
        (
            "The stored Philadelphia NWS forecast period numbers have",
            f"{len(found.values)} distinct values.",
            listed,
            f"{len(found.skipped)} numbers were missing and were not filled in.",
            "The hourly body was not used.",
            "A missing number was not invented.",
            "The count was not compared to 0.40 or to 2°F.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _numbers(path: Path) -> tuple[tuple[str, int | None, str], ...]:
    body = _object(path)
    periods = _sequence(
        _mapping(body.get("properties"), "properties").get("periods"),
        "periods",
    )
    found: list[tuple[str, int | None, str]] = []
    for index, item in enumerate(periods, start=1):
        period = _mapping(item, "period")
        start = period.get("startTime")
        label = start if isinstance(start, str) and start != "" else f"period {index}"
        raw = period.get("number")
        if raw is None:
            found.append((label, None, _MISSING))
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            found.append((label, None, _OTHER))
            continue
        found.append((label, raw, ""))
    return tuple(found)


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


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not a list")
    return tuple(value)
