"""Rank of the stored ensemble control. This module does not open a socket.

The rank is 1 plus the number of series strictly colder than the control.
It is not divided and it is not a probability. It is not aligned to the
CLI decision clock. This module does not add a threshold or trade.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.gfs_ensemble import load_gfs_ensemble

_BODY = Path("open-meteo/gfs-ensemble.json")
_MEMBERS = tuple(f"temperature_2m_member{index:02d}" for index in range(1, 31))
_SERIES = ("temperature_2m", *_MEMBERS)
_CONTROL = "temperature_2m"
_NULL = "an hour is null"


@dataclass(frozen=True)
class HourRank:
    """One eligible hour. The rank is not a trading threshold."""

    time: str
    rank: int


@dataclass(frozen=True)
class SkippedHour:
    """An hour that failed the written eligibility rule."""

    time: str
    reason: str


@dataclass(frozen=True)
class EnsembleRank:
    """Eligible hours and named skips. ``traded`` and ``promoted`` stay false."""

    hours: tuple[HourRank, ...]
    skipped: tuple[SkippedHour, ...]
    traded: bool
    promoted: bool


def load_ensemble_rank(root: Path) -> EnsembleRank:
    """Apply the written rank rule. A tie does not increase the rank."""
    archive = load_gfs_ensemble(root)
    if archive.traded or archive.promoted:
        raise ValueError("the ensemble was traded")
    if archive.series != len(_SERIES):
        raise ValueError("the ensemble series count changed")
    body = _object(root / _BODY)
    hourly = _mapping(body.get("hourly"), "hourly")
    times = _times(hourly.get("time"))
    columns = tuple(_values(hourly.get(name), len(times), name) for name in _SERIES)
    control_index = _SERIES.index(_CONTROL)
    ranks: list[HourRank] = []
    skipped: list[SkippedHour] = []
    for index, stamp in enumerate(times):
        sample = tuple(column[index] for column in columns)
        if any(item is None for item in sample):
            skipped.append(SkippedHour(stamp, _NULL))
            continue
        values = tuple(item for item in sample if item is not None)
        control = values[control_index]
        colder = sum(1 for item in values if item < control)
        ranks.append(HourRank(time=stamp, rank=1 + colder))
    return EnsembleRank(hours=tuple(ranks), skipped=tuple(skipped), traded=False, promoted=False)


def ensemble_rank_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_ensemble_rank(root)
    if found.traded or found.promoted:
        raise ValueError("the rank note must not trade")
    return " ".join(
        (
            "The Philadelphia ensemble-control rank record has",
            f"{len(found.hours)} eligible hours and {len(found.skipped)} skipped hours.",
            "The rank is 1 plus the number of series strictly colder than the control.",
            "A tie does not increase the rank.",
            "The rank was not divided and is not a probability.",
            "It was not aligned to the CLI decision clock.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _times(value: object) -> tuple[str, ...]:
    rows = _sequence(value, "time")
    found: list[str] = []
    for item in rows:
        if not isinstance(item, str) or item == "":
            raise ValueError("an ensemble hour is not text")
        found.append(item)
    return tuple(found)


def _values(value: object, hours: int, label: str) -> tuple[Decimal | None, ...]:
    rows = _sequence(value, label)
    if len(rows) != hours:
        raise ValueError("ensemble hours and values differ")
    found: list[Decimal | None] = []
    for item in rows:
        if item is None:
            found.append(None)
            continue
        found.append(_decimal(item, label))
    return tuple(found)


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
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


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise ValueError(f"{label} is not a number")
    return Decimal(value)
