"""Point-in-time feature materialization from verified research datasets.

Every value records the latest availability clock of its inputs, and publication fails if
any input became available after its decision time. Missing inputs give null, never an
imputed or carried-forward value. Labels are materialized separately and never become
decision-time features.
"""

import json
import shutil
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import fmean
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import DecisionPoint
from entropytrade.research.registry import FeatureDefinition

FEATURE_SCHEMA = "entropytrade-research-feature-v1"


@dataclass(frozen=True)
class Vintage:
    valid_on: date
    available_at: datetime
    value: Decimal
    revision: str


def vintages(
    records: Iterable[dict[str, Any]], *, entity: str, variable: str | set[str]
) -> dict[date, list[Vintage]]:
    """Strict observations only: a usable availability clock is required."""
    from entropytrade.data.schema import Observation

    wanted = {variable} if isinstance(variable, str) else variable
    result: dict[date, list[Vintage]] = defaultdict(list)
    for raw in records:
        if raw.get("entity_id") != entity or raw.get("variable") not in wanted:
            continue
        item = Observation.model_validate(raw)
        if (
            item.timing_basis not in {"received", "provider_publication"}
            or item.available_at is None
        ):
            continue
        result[item.valid_on].append(
            Vintage(item.valid_on, item.available_at, item.value, item.revision_id or item.raw_hash)
        )
    for items in result.values():
        items.sort(key=lambda v: (v.available_at, v.revision))
    return result


def decision_times(
    target: date, schedule: Sequence[DecisionPoint], timezone: str
) -> list[datetime]:
    zone = ZoneInfo(timezone)
    return [
        datetime.combine(target + timedelta(days=p.day_offset), p.local_time, zone).astimezone(UTC)
        for p in schedule
    ]


def _known(items: list[Vintage], at: datetime) -> list[Vintage]:
    return [v for v in items if v.available_at <= at]


def _distinct(items: list[Vintage]) -> list[Vintage]:
    """Latest value per distinct availability clock (a reissue replaces nothing earlier)."""
    by_clock: dict[datetime, Vintage] = {}
    for item in items:
        by_clock[item.available_at] = item
    return [by_clock[k] for k in sorted(by_clock)]


def materialize(
    definition: FeatureDefinition,
    *,
    entity: str,
    timezone: str,
    schedule: Sequence[DecisionPoint],
    window: tuple[date, date],
    inputs: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Rows of (target date, decision time, value, latest input clock)."""
    start, end = window
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rows: list[dict[str, Any]] = []
    if definition.transform == "label_value":
        # The label service names the authority value after the label itself.
        labels = vintages(
            inputs["label"],
            entity=entity,
            variable={definition.inputs[0].variable, definition.feature_id},
        )
        for day in days:
            found = labels.get(day, [])
            chosen = found[-1] if found else None
            rows.append(
                {
                    "entity": entity,
                    "target_date": day.isoformat(),
                    "decision_time": None,
                    "value": str(chosen.value) if chosen else None,
                    "inputs_available_at": chosen.available_at.isoformat() if chosen else None,
                    "inputs": [chosen.revision] if chosen else [],
                }
            )
        return rows
    forecasts = vintages(inputs["forecast"], entity=entity, variable=definition.inputs[0].variable)
    observations = (
        vintages(inputs["observation"], entity=entity, variable=definition.inputs[1].variable)
        if definition.transform == "trailing_mean_error"
        else {}
    )
    window_days = int(definition.params.get("window_days", 21))
    min_count = int(definition.params.get("min_count", 5))
    for day in days:
        for decision in decision_times(day, schedule, timezone):
            value: Decimal | None = None
            used: list[Vintage] = []
            known = _distinct(_known(forecasts.get(day, []), decision))
            if definition.transform == "latest_vintage" and known:
                used = [known[-1]]
                value = known[-1].value
            elif definition.transform == "vintage_revision" and len(known) >= 2:
                used = known[-2:]
                value = known[-1].value - known[-2].value
            elif definition.transform == "trailing_mean_error":
                errors: list[float] = []
                for back in range(1, window_days + 1):
                    prior = day - timedelta(days=back)
                    reported = _known(observations.get(prior, []), decision)
                    issued = _distinct(
                        _known(forecasts.get(prior, []), decision - timedelta(days=back))
                    )
                    if reported and issued:
                        errors.append(float(reported[-1].value - issued[-1].value))
                        used += [reported[-1], issued[-1]]
                if len(errors) >= min_count:
                    value = Decimal(str(round(fmean(errors), 4)))
            elif definition.transform not in {
                "latest_vintage",
                "vintage_revision",
                "trailing_mean_error",
            }:
                raise ValueError(f"no research materializer for {definition.transform}")
            latest = max((v.available_at for v in used), default=None)
            if value is None:
                used, latest = [], None
            if latest is not None and latest > decision:
                raise ValueError("point-in-time violation: an input postdates the decision")
            rows.append(
                {
                    "entity": entity,
                    "target_date": day.isoformat(),
                    "decision_time": decision.isoformat(),
                    "value": str(value) if value is not None else None,
                    "inputs_available_at": latest.isoformat() if latest else None,
                    "inputs": sorted({v.revision for v in used})[:6],
                }
            )
    return rows


def validate_rows(definition: FeatureDefinition, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row["value"] is None:
            continue
        value = Decimal(row["value"])
        if not value.is_finite():
            raise ValueError("feature value is not finite")
        if definition.transform == "latest_vintage" and not -60 <= value <= 140:
            raise ValueError("feature value outside the plausible range")
        if row["decision_time"] is not None and row["inputs_available_at"] > row["decision_time"]:
            raise ValueError("point-in-time violation in a published feature row")


def publish_feature(
    root: Path,
    definition: FeatureDefinition,
    *,
    entity: str,
    schedule: Sequence[DecisionPoint],
    window: tuple[date, date],
    input_datasets: list[str],
    rows: list[dict[str, Any]],
    created_at: datetime,
) -> dict[str, Any]:
    """Immutable, content-addressed feature artifact with lineage."""
    from entropytrade.data.sources import file_hash

    validate_rows(definition, rows)
    features = root / "features"
    features.mkdir(parents=True, exist_ok=True)
    staging = features / (".building-" + uuid4().hex)
    staging.mkdir()
    try:
        (staging / "values.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
        )
        values_hash = file_hash(staging / "values.jsonl")
        identity = {
            "feature_id": definition.feature_id,
            "version": definition.version,
            "definition_hash": definition.definition_hash,
            "entity": entity,
            "schedule": [p.model_dump(mode="json") for p in schedule],
            "window": [window[0].isoformat(), window[1].isoformat()],
            "input_datasets": sorted(input_datasets),
            "values": values_hash,
        }
        artifact_id = scientific_hash(identity)
        non_null = [r for r in rows if r["value"] is not None]
        manifest = {
            "schema": FEATURE_SCHEMA,
            "artifact_id": artifact_id,
            **identity,
            "role": definition.role,
            "transform": definition.transform,
            "params": definition.params,
            "unit": definition.unit,
            "rows": len(rows),
            "non_null": len(non_null),
            "events": len({r["target_date"] for r in non_null}),
            "created_at": created_at.isoformat(),
            "checks": [
                "every non-null value's input clocks are at or before its decision time",
                "missing inputs are null; nothing imputed",
                *definition.validation,
            ],
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1))
        target = features / ("sha256-" + artifact_id.removeprefix("sha256:"))
        if target.exists():
            shutil.rmtree(staging)
            return dict(json.loads((target / "manifest.json").read_text()))
        staging.replace(target)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
