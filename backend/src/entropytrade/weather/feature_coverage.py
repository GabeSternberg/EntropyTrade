"""Which spec section 27 names appear in the stored CLI rescore rows.

A spec name counts as stored only when that exact string is a manifest
feature or a previous-runs hourly field. Empty bid and ask stay empty.
This module does not invent a value, fetch, or fit a model. It does not
open a socket.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from entropytrade.weather.provenance import load_feature_manifest, load_prediction_records

_SPEC = Path("docs/project-spec.md")
_PREVIOUS_RUNS = Path("open-meteo/previous-runs.json")
_MARKER = "Potential features:"


@dataclass(frozen=True)
class FeatureCoverage:
    """Stored columns beside the spec's feature names. No filled-in values."""

    manifest_features: tuple[str, ...]
    row_keys: tuple[str, ...]
    previous_runs_hourly: tuple[str, ...]
    row_count: int
    record_count: int
    station: str
    decision: str
    empty_bids: int
    empty_asks: int
    sized_book_false: int
    spec_features: tuple[str, ...]
    absent_spec_features: tuple[str, ...]


def load_feature_coverage(root: Path) -> FeatureCoverage:
    """Read the manifest, the previous-runs keys, and the spec's feature list."""
    manifest = load_feature_manifest(root)
    features = _strings(manifest.get("features"), "features")
    rows = _rows(manifest.get("rows"))
    if not rows:
        raise ValueError("the feature manifest has no rows")
    keys = tuple(rows[0])
    if any(tuple(row) != keys for row in rows):
        raise ValueError("feature rows do not share one set of keys")
    stations = {_text(row.get("station"), "station") for row in rows}
    if len(stations) != 1:
        raise ValueError("feature rows do not share one station")
    sized_false = sum(1 for row in rows if row.get("sized_book") is False)
    hourly = _hourly_keys(root / _PREVIOUS_RUNS)
    records = load_prediction_records(root)
    spec = spec_feature_names(root.parents[1] / _SPEC)
    stored = set(features) | set(hourly)
    absent = tuple(name for name in spec if name not in stored)
    return FeatureCoverage(
        manifest_features=features,
        row_keys=keys,
        previous_runs_hourly=hourly,
        row_count=len(rows),
        record_count=len(records),
        station=stations.pop(),
        decision=_text(manifest.get("decision"), "decision"),
        empty_bids=sum(1 for record in records if record.market_yes_bid is None),
        empty_asks=sum(1 for record in records if record.market_yes_ask is None),
        sized_book_false=sized_false,
        spec_features=spec,
        absent_spec_features=absent,
    )


def spec_feature_names(path: Path) -> tuple[str, ...]:
    """The lines inside the section 27 potential-features block."""
    text = path.read_text(encoding="utf-8")
    start = text.find(_MARKER)
    if start < 0:
        raise ValueError("spec section 27 has no potential features")
    fence = text.find("```text", start)
    end = text.find("```", fence + len("```text"))
    if fence < 0 or end < 0:
        raise ValueError("spec section 27 features are not in a text block")
    block = text[fence + len("```text") : end]
    names = tuple(line.strip() for line in block.splitlines() if line.strip())
    if not names:
        raise ValueError("spec section 27 features are empty")
    return names


def _hourly_keys(path: Path) -> tuple[str, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("previous-runs is not an object")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("previous-runs hourly is not an object")
    keys: list[str] = []
    for key in hourly:
        if not isinstance(key, str):
            raise ValueError("previous-runs hourly has a non-string key")
        keys.append(key)
    return tuple(keys)


def _rows(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        raise ValueError("rows is not a list")
    found: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("a feature row is not an object")
        row: dict[str, object] = {}
        for key, cell in item.items():
            if not isinstance(key, str):
                raise ValueError("a feature row has a non-string key")
            row[key] = cell
        found.append(row)
    return tuple(found)


def _strings(value: object, what: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return tuple(_text(item, what) for item in value)


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value
