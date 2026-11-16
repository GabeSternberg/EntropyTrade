"""Reproducible event-level modeling of acquired research features.

This is an adapter to the existing weather models and temporal evaluation primitives,
not a second job runner. The research service owns budgets, retries and cancellation.
Statistical threshold probabilities are explicitly distinct from contract predictions.
"""

import json
import math
import re
import shutil
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib.metadata import version
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any, Literal
from uuid import uuid4

import numpy as np
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from entropytrade.data.sources import file_hash
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.experiments.engine import ExperimentConfig
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import TemporalPlan, metrics, temporal_plan, walk_forward_plans
from entropytrade.ml.experiment import ModelingConfig
from entropytrade.ml.models import EventExample, WeatherModel
from entropytrade.research.materialize import FEATURE_SCHEMA, decision_times
from entropytrade.research.model import HypothesisSpec
from entropytrade.research.registry import FeatureDefinition, FeatureRegistry
from entropytrade.research.store import reject_collector_chain
from entropytrade.weather.probability import InsufficientHistoryError

WeatherKind = Literal["climatology", "raw_forecast", "forecast_error", "ridge", "boosting"]
DataKind = Literal["real", "synthetic"]
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
SCHEMA = "entropytrade-research-modeling-v1"


def _path(root: Path, section: str, identifier: str) -> Path:
    if HASH.fullmatch(identifier) is None:
        raise ValueError("invalid content-addressed research artifact identifier")
    path = root / section / ("sha256-" + identifier.removeprefix("sha256:"))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("research artifacts cannot be symlinks")
    return path


def _json(path: Path) -> dict[str, Any]:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("research artifacts cannot be symlinks")
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def _selected(
    spec: HypothesisSpec, registry: FeatureRegistry, artifacts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    names = {registry.resolve(f.name).feature_id for f in (*spec.features, spec.label)} - {None}
    return sorted(
        (
            a
            for a in artifacts
            if a["feature_id"] in names
            and ("hypotheses" not in a or spec.hypothesis_id in a["hypotheses"])
        ),
        key=lambda a: (a["feature_id"], a["entity"], a["artifact_id"]),
    )


def plan_hypothesis(
    *,
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    validation_depth: str = "standard",
    data_kind: DataKind = "real",
    boundaries: tuple[date, date, date] | None = None,
    execution_datasets: tuple[str, ...] = (),
    fee_versions: tuple[FeeVersion, ...] | None = None,
) -> dict[str, Any]:
    """Freeze an identity before fitting; the caller persists boundaries before execution."""
    reject_collector_chain(root)
    from entropytrade.research.execution_inputs import execution_locations

    if root.name == "chain" or root.is_symlink():
        raise ValueError("modeling requires an isolated research store")
    selected = _selected(spec, registry, artifacts)
    if boundaries is None:
        # Use the complete declared window, including missing observations. Coverage can
        # never move the partition boundaries. The service inherits these on reevaluation.
        windows = [a["window"] for a in selected]
        if windows:
            start = min(date.fromisoformat(w[0]) for w in windows)
            end = max(date.fromisoformat(w[1]) for w in windows)
            n = (end - start).days + 1
            if n >= 10:
                boundaries = tuple(  # type: ignore[assignment]
                    start + timedelta(days=int(n * f)) for f in (0.48, 0.6, 0.8)
                )
    config = ModelingConfig(
        boundaries=boundaries,
        min_train_events={"quick": 30, "standard": 60, "thorough": 120}[validation_depth],
    ).model_dump(mode="json")
    package = Path(__file__).parent.parent
    identity = {
        "schema": SCHEMA,
        "spec": spec.model_dump(mode="json"),
        "features": [
            {k: a[k] for k in ("artifact_id", "feature_id", "entity", "definition_hash", "values")}
            for a in selected
        ],
        "definitions": {
            f.name: registry.resolve(f.name).model_dump(mode="json")
            for f in (*spec.features, spec.label)
        },
        "config": config,
        "data_kind": data_kind,
        "execution_datasets": sorted(execution_datasets),
        "execution_locations": execution_locations(),
        "fee_versions": [v.model_dump(mode="json") for v in fee_versions]
        if fee_versions is not None
        else [],
        "execution_config": ExperimentConfig(fee_versions=fee_versions or ()).model_dump(
            mode="json"
        ),
        "code": {
            name: file_hash(package / name)
            for name in (
                "research/modeling.py",
                "research/materialize.py",
                "research/registry.py",
                "research/backtesting.py",
                "research/execution_inputs.py",
                "ml/experiment.py",
                "ml/models.py",
                "ml/evaluation.py",
                "ml/probability.py",
                "experiments/engine.py",
                "backtest/replay.py",
                "domain/strategy.py",
                "domain/market.py",
                "domain/market_data.py",
                "domain/enums.py",
                "domain/numeric.py",
                "domain/observations.py",
                "domain/time.py",
                "domain/base.py",
                "data/schema.py",
                "features/registry.py",
                "strategies/interpret.py",
                "execution/paper.py",
                "portfolio/ledger.py",
                "risk/engine.py",
                "execution/fee_policy.py",
                "execution/fee_evidence.py",
                "execution/fees.py",
            )
        },
        "runtime": {
            "python": sys.version,
            **{name: version(name) for name in ("scikit-learn", "numpy", "joblib")},
        },
        "embargo_days": 2,
        "sensitivity": {
            "threshold_offsets_f": [-5, 5],
            "forecast_shifts_f": [-1, 1],
            "compare_uncalibrated": True,
        },
        "evaluation": "training-median temperature threshold; not an exchange contract",
    }
    freeze_ready = False
    try:
        ready_rows, _ = _rows(
            root, registry, spec, selected, data_kind, boundaries[2] if boundaries else None
        )
        ready_config = ModelingConfig.model_validate(config)
        ready_plan = temporal_plan(ready_rows, boundaries)
        ready_train = _examples(ready_rows, ready_plan.fit, ready_plan.fit_asof)
        if len(ready_train) >= ready_config.min_train_events:
            threshold = math.floor(median(e.target_f for e in ready_train))
            freeze_ready = any(e.target_f <= threshold for e in ready_train) and any(
                e.target_f > threshold for e in ready_train
            )
            if set(spec.candidate_models) & {"gaussian_error", "ridge", "gradient_boosting"}:
                ready_calibration = _examples(
                    ready_rows, ready_plan.calibration, ready_plan.calibration_asof
                )
                freeze_ready = (
                    freeze_ready and len(ready_calibration) >= ready_config.min_calibration_events
                )
    except (OSError, ValueError, TypeError, KeyError):
        # Precise refusals belong to the persisted execution report, not planning.
        freeze_ready = False
    return {
        "experiment_id": scientific_hash(identity),
        "identity": identity,
        "config": config,
        "boundaries": [b.isoformat() for b in boundaries] if boundaries else None,
        "freeze_ready": freeze_ready,
    }


def _dataset(root: Path, identifier: str, data_kind: DataKind) -> None:
    path = _path(root, "datasets", identifier)
    manifest = _json(path / "manifest.json")
    expected = "authentic" if data_kind == "real" else "synthetic"
    if manifest.get("data_kind") != expected:
        raise ValueError("synthetic/authentic dataset and experiment version mismatch")
    checksums = manifest["checksums"]
    if set(checksums) != {"records.jsonl", "receipts.jsonl", "parameters.json"}:
        raise ValueError("research dataset checksum inventory mismatch")
    if manifest["dataset_id"] != identifier or scientific_hash(checksums) != identifier:
        raise ValueError("research dataset identity mismatch")
    for name, digest in checksums.items():
        if (path / name).is_symlink() or file_hash(path / name) != digest:
            raise ValueError("research dataset checksum mismatch")
    # Verify preserved original response bytes as well as derived records. Hashes prove
    # retention, not source truth; synthetic mode remains visibly separate.
    receipt_hashes = sorted(
        {
            json.loads(line)["sha256"]
            for line in (path / "receipts.jsonl").read_text().splitlines()
            if line
        }
    )
    if receipt_hashes != manifest.get("raw_hashes", []):
        raise ValueError("raw response inventory does not match verified receipts")
    for digest in receipt_hashes:
        if HASH.fullmatch(digest) is None:
            raise ValueError("invalid raw response hash")
        hex_digest = digest.removeprefix("sha256:")
        raw = root / "raw" / hex_digest[:2] / hex_digest
        if any(p.is_symlink() for p in (raw, *raw.parents)) or file_hash(raw) != digest:
            raise ValueError("research raw response checksum mismatch")


def _feature(
    root: Path,
    manifest: dict[str, Any],
    definition: FeatureDefinition,
    data_kind: DataKind,
    protected_from: date | None = None,
) -> list[dict[str, Any]]:
    path = _path(root, "features", manifest["artifact_id"])
    stored = _json(path / "manifest.json")
    identity = {
        k: stored[k]
        for k in (
            "feature_id",
            "version",
            "definition_hash",
            "entity",
            "schedule",
            "window",
            "input_datasets",
            "values",
        )
    }
    if (
        stored.get("schema") != FEATURE_SCHEMA
        or scientific_hash(identity) != manifest["artifact_id"]
        or stored["artifact_id"] != manifest["artifact_id"]
        or stored["feature_id"] != definition.feature_id
        or stored["definition_hash"] != definition.definition_hash
        or stored["version"] != definition.version
        or stored["unit"] != definition.unit
        or stored["role"] != definition.role
        or any(stored[k] != manifest[k] for k in ("values", "definition_hash", "entity"))
    ):
        raise ValueError("feature artifact or registered definition version mismatch")
    if (path / "values.jsonl").is_symlink() or file_hash(path / "values.jsonl") != stored["values"]:
        raise ValueError("feature artifact checksum mismatch")
    if not stored["input_datasets"]:
        raise ValueError("feature artifact has no dataset provenance")
    for identifier in stored["input_datasets"]:
        _dataset(root, identifier, data_kind)
    rows = [json.loads(line) for line in (path / "values.jsonl").read_text().splitlines()]
    keys: set[tuple[str, str, str | None]] = set()
    for row in rows:
        key = (row["entity"], row["target_date"], row["decision_time"])
        if key in keys or row["entity"] != stored["entity"]:
            raise ValueError("feature artifact repeats an event/decision or changes entity")
        keys.add(key)
        if not stored["window"][0] <= row["target_date"] <= stored["window"][1]:
            raise ValueError("feature row outside frozen window")
        if (
            definition.role == "label"
            and protected_from
            and row["target_date"] >= protected_from.isoformat()
        ):
            # Retain an identity shell only. Hash the full immutable bytes, but do not
            # inspect a protected target's value/clock or use it in eligibility.
            row.update(value=None, inputs_available_at=None, inputs=[])
            continue
        if row["value"] is None:
            continue
        value = float(row["value"])
        if not math.isfinite(value) or (definition.dtype == "int64" and value != round(value)):
            raise ValueError("feature value has an invalid type")
        available = _clock(row["inputs_available_at"])
        if definition.role == "feature":
            decision = _clock(row["decision_time"])
            if available > decision:
                raise ValueError("future-information leakage: feature postdates decision")
        elif row["decision_time"] is not None:
            raise ValueError("outcome label must not have a feature decision clock")
    return rows


def _clock(value: str) -> datetime:
    at = datetime.fromisoformat(value)
    if at.utcoffset() is None:
        raise ValueError("a timezone-aware availability clock is required")
    return at


def _rows(
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    data_kind: DataKind,
    protected_from: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    from entropytrade.research.execution_inputs import execution_locations

    selected = _selected(spec, registry, artifacts)
    timezones = {
        value["entity"]: value["timezone"]
        for series, value in execution_locations().items()
        if series in spec.universe
    }
    values: dict[str, dict[tuple[str, str, str | None], dict[str, Any]]] = defaultdict(dict)
    for manifest in selected:
        definition = registry.get(manifest["feature_id"])
        for row in _feature(root, manifest, definition, data_kind, protected_from):
            parsed_day = date.fromisoformat(row["target_date"])
            if definition.role == "feature" and (
                row["entity"] not in timezones
                or _clock(row["decision_time"])
                not in decision_times(
                    parsed_day,
                    spec.decision_schedule,
                    timezones[row["entity"]],
                )
            ):
                raise ValueError("feature row decision differs from the frozen hypothesis schedule")
            key = (row["entity"], row["target_date"], row["decision_time"])
            if key in values[definition.feature_id]:
                raise ValueError("multiple current feature versions for one event/decision")
            values[definition.feature_id][key] = row
    features = [registry.resolve(f.name).feature_id for f in spec.features]
    label = registry.resolve(spec.label.name).feature_id
    if label is None:
        raise ValueError("unregistered outcome label")
    forecast = "nws_pfm_max_f" if "nws_pfm_max_f" in features else "forecast_high_f"
    missingness = dict.fromkeys([str(f) for f in features] + [label], 0)
    candidates = sorted({key for f in features for key in values[str(f)] if key[2] is not None})
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entity, day, decision in candidates:
        if (entity, day) in seen:
            continue
        # One predeclared earliest decision per independent station-day. Later nulls or
        # labels never determine which decision is selected.
        seen.add((entity, day))
        feature_values: dict[str, float | None] = {}
        clocks = []
        for name in features:
            raw = values[str(name)].get((entity, day, decision))
            value = raw["value"] if raw else None
            feature_values[str(name)] = float(value) if value is not None else None
            if value is None:
                missingness[str(name)] += 1
            else:
                clocks.append(raw["inputs_available_at"])  # type: ignore[index]
        target = values[label].get((entity, day, None))
        target_value = target["value"] if target else None
        if target_value is None and (protected_from is None or day < protected_from.isoformat()):
            missingness[label] += 1
        # WeatherModel's baseline expects this internal key. The original canonical
        # daytime-maximum feature and its semantics remain in the model schema.
        feature_values["forecast_high_f"] = feature_values.get(forecast)
        rows.append(
            {
                "event_id": entity + ":" + day,
                "target_date": day,
                "entity": entity,
                "decision_time": decision,
                "features": feature_values,
                "features_available_at": max(clocks, default=None),
                "target": float(target_value) if target_value is not None else None,
                "label_available_at": target["inputs_available_at"]
                if target and target_value is not None
                else None,
                "complete": all(feature_values.get(str(f)) is not None for f in features)
                and target_value is not None,
            }
        )
    return rows, missingness


def _examples(
    rows: list[dict[str, Any]], ids: tuple[str, ...], cutoff: datetime
) -> list[EventExample]:
    return [
        EventExample(
            r["event_id"],
            _clock(r["decision_time"]),
            r["target_date"],
            r["entity"],
            r["features"],
            r["target"],
            _clock(r["label_available_at"]),
        )
        for r in rows
        if r["event_id"] in ids
        and r["complete"]
        and _clock(r["label_available_at"]) <= cutoff
        and _clock(r["decision_time"]) < cutoff - timedelta(days=2)
    ]


def _score(
    rows: list[dict[str, Any]],
    ids: tuple[str, ...],
    model: WeatherModel,
    threshold: float,
    *,
    calibrated: bool = True,
    forecast_shift_f: float = 0,
) -> list[dict[str, Any]]:
    return [
        {
            "event_id": r["event_id"],
            "target_date": r["target_date"],
            "outcome": "yes" if r["target"] <= threshold else "no",
            "probability_yes": model.cdf(
                {
                    name: value + forecast_shift_f
                    if name in {"forecast_high_f", "nws_pfm_max_f"} and value is not None
                    else value
                    for name, value in r["features"].items()
                },
                threshold + 0.5,
                calibrated=calibrated,
            ),
            "threshold_f": threshold,
            "decision_time": r["decision_time"],
        }
        for r in rows
        if r["event_id"] in ids and r["complete"]
    ]


def _partition(plan: TemporalPlan) -> dict[str, Any]:
    return {
        k: v.isoformat() if isinstance(v, datetime) else list(v) for k, v in asdict(plan).items()
    }


def _uncertainty(records: list[dict[str, Any]], seed: int) -> dict[str, Any] | None:
    by_date: dict[str, list[float]] = defaultdict(list)
    for row in records:
        by_date[row["target_date"]].append(
            (row["probability_yes"] - (row["outcome"] == "yes")) ** 2
        )
    if len(by_date) < 20:
        return None
    losses = np.array([float(np.mean(v)) for v in by_date.values()])
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(losses, size=len(losses), replace=True))) for _ in range(500)]
    return {
        "lower": float(np.quantile(means, 0.025)),
        "upper": float(np.quantile(means, 0.975)),
        "method": "fixed-seed date-block bootstrap Brier mean",
        "date_blocks": len(losses),
        "nominal_coverage": 0.95,
        "selection_adjusted": False,
    }


def _comparison(
    candidate: list[dict[str, Any]], baseline: list[dict[str, Any]], seed: int
) -> dict[str, Any]:
    reference = {r["event_id"]: r for r in baseline}
    blocks: dict[str, list[float]] = defaultdict(list)
    for row in candidate:
        if row["event_id"] not in reference:
            continue
        other = reference[row["event_id"]]
        outcome = row["outcome"] == "yes"
        blocks[row["target_date"]].append(
            (other["probability_yes"] - outcome) ** 2 - (row["probability_yes"] - outcome) ** 2
        )
    values = np.array([float(np.mean(v)) for v in blocks.values()])
    result: dict[str, Any] = {
        "reference": "climatology",
        "paired_events": sum(len(v) for v in blocks.values()),
        "mean_brier_improvement": float(np.mean(values)) if len(values) else None,
        "improvement_interval": None,
        "selection_adjusted": False,
    }
    if len(values) >= 20:
        rng = np.random.default_rng(seed)
        means = [
            float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(500)
        ]
        result["improvement_interval"] = {
            "lower": float(np.quantile(means, 0.025)),
            "upper": float(np.quantile(means, 0.975)),
            "date_blocks": len(values),
            "method": "paired date-block bootstrap Brier improvement",
            "nominal_coverage": 0.95,
        }
    return result


def _read_result(path: Path) -> dict[str, Any]:
    checksums = _json(path / "checksums.json")
    if "results.json" not in checksums:
        raise ValueError("incomplete research experiment checkpoint")
    if set(checksums) != {p.name for p in path.iterdir()} - {"checksums.json"}:
        raise ValueError("research experiment artifact inventory mismatch")
    for name, digest in checksums.items():
        if (
            Path(name).name != name
            or (path / name).is_symlink()
            or file_hash(path / name) != digest
        ):
            raise ValueError("research experiment artifact checksum mismatch")
    return _json(path / "results.json")


def verify_hypothesis(
    *,
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    validation_depth: str = "standard",
    data_kind: DataKind = "real",
    boundaries: tuple[date, date, date] | None = None,
    expected_id: str | None = None,
    execution_datasets: tuple[str, ...] = (),
    fee_versions: tuple[FeeVersion, ...] | None = None,
) -> dict[str, Any]:
    """Verify a completed checkpoint and its frozen inputs without fitting anything."""
    planned = plan_hypothesis(
        root=root,
        registry=registry,
        spec=spec,
        artifacts=artifacts,
        validation_depth=validation_depth,
        data_kind=data_kind,
        boundaries=boundaries,
        execution_datasets=execution_datasets,
        fee_versions=fee_versions,
    )
    if expected_id is not None and expected_id != planned["experiment_id"]:
        raise ValueError("research model/dataset version mismatch")
    for artifact in _selected(spec, registry, artifacts):
        _feature(
            root,
            artifact,
            registry.get(artifact["feature_id"]),
            data_kind,
            date.fromisoformat(planned["boundaries"][2]) if planned["boundaries"] else None,
        )
    for identifier in execution_datasets:
        _dataset(root, identifier, data_kind)
    result = _read_result(_path(root, "experiments", planned["experiment_id"]))
    if result["experiment_id"] != planned["experiment_id"]:
        raise ValueError("research model/dataset version mismatch")
    return result


def run_hypothesis(
    *,
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    now: datetime,
    validation_depth: str = "standard",
    data_kind: DataKind = "real",
    boundaries: tuple[date, date, date] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    execution_datasets: tuple[str, ...] = (),
    fee_versions: tuple[FeeVersion, ...] | None = None,
) -> dict[str, Any]:
    """Fit only causal examples and publish immutable reports, including precise refusals."""
    from entropytrade.research.backtesting import backtest_hypothesis

    planned = plan_hypothesis(
        root=root,
        registry=registry,
        spec=spec,
        artifacts=artifacts,
        validation_depth=validation_depth,
        data_kind=data_kind,
        boundaries=boundaries,
        execution_datasets=execution_datasets,
        fee_versions=fee_versions,
    )
    destination = _path(root, "experiments", planned["experiment_id"])
    if cancelled():
        raise InterruptedError("research modeling cancelled or budget exhausted")
    if destination.exists():
        # A cached report must not hide changed/absent input evidence. Verify frozen
        # source bytes before returning an earlier scientific result.
        return verify_hypothesis(
            root=root,
            registry=registry,
            spec=spec,
            artifacts=artifacts,
            validation_depth=validation_depth,
            data_kind=data_kind,
            boundaries=boundaries,
            expected_id=planned["experiment_id"],
            execution_datasets=execution_datasets,
            fee_versions=fee_versions,
        )
    config = ModelingConfig.model_validate(planned["config"])
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "experiment_id": planned["experiment_id"],
        "status": "awaiting_data",
        "config": planned["config"],
        "boundaries": planned["boundaries"],
        "data_kind": data_kind,
        "eligibility": {"eligible": False, "reasons": []},
        "models": {},
        "baselines": {},
        "validation": {
            "status": "awaiting_data",
            "holdout_evaluated": False,
            "prospective": False,
            "walk_forward": [],
            "uncertainty": {},
            "baseline_comparisons": {},
            "sensitivity": {},
        },
        "backtest": backtest_hypothesis(spec=spec, registry=registry),
        "provenance": {
            "feature_artifacts": planned["identity"]["features"],
            "feature_definitions": planned["identity"]["definitions"],
            "identity": planned["identity"],
        },
        "warnings": [
            "Historical replay only; generated historical predictions are never prospective.",
            "Temperature-threshold scores are predictive analysis, not contract returns.",
            "All requested model families and previous searches count toward selection effects.",
            "Intervals are descriptive after model search; no strategy promotion is authorized.",
            "Protected holdout outcomes are not scored or used to fit/calibrate models.",
        ],
    }
    selected = _selected(spec, registry, artifacts)
    result["provenance"]["dataset_versions"] = sorted(
        {d for a in selected for d in a.get("inputs", a.get("input_datasets", []))}
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (".building-" + uuid4().hex)
    staging.mkdir()
    try:
        try:
            _evaluate(
                root,
                registry,
                spec,
                selected,
                now,
                data_kind,
                config,
                staging,
                result,
                cancelled,
                execution_datasets,
                fee_versions or (),
            )
        except (ValueError, TypeError, KeyError) as exc:
            result["status"] = "invalid"
            result["eligibility"].update(eligible=False, reasons=[str(exc)])
            result["validation"]["status"] = "refused"
        if cancelled():
            raise InterruptedError("research modeling cancelled or budget exhausted")
        report = "\n".join(
            [
                "# Acquired-feature research experiment",
                "",
                f"Status: {result['status']}. Evidence: {data_kind}.",
                f"Experiment: {result['experiment_id']}",
                "",
                *result["eligibility"]["reasons"],
                "",
                "Model scores: " + json.dumps(result["models"], sort_keys=True),
                "",
                "Executable backtest: " + json.dumps(result["backtest"], sort_keys=True),
                "",
                *result["warnings"],
                "",
            ]
        )
        (staging / "report.md").write_text(report)
        result["report"] = {
            "path": str(destination.relative_to(root) / "report.md"),
            "hash": file_hash(staging / "report.md"),
        }
        (staging / "results.json").write_text(json.dumps(result, sort_keys=True, indent=2))
        (staging / "checksums.json").write_text(
            json.dumps(
                {p.name: file_hash(p) for p in staging.iterdir()},
                sort_keys=True,
                indent=2,
            )
        )
        if destination.exists():
            return _read_result(destination)
        staging.rename(destination)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _evaluate(
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    now: datetime,
    data_kind: DataKind,
    config: ModelingConfig,
    staging: Path,
    result: dict[str, Any],
    cancelled: Callable[[], bool],
    execution_datasets: tuple[str, ...],
    fee_versions: tuple[FeeVersion, ...],
) -> None:
    from entropytrade.research.execution_inputs import acquired_backtest

    reasons = result["eligibility"]["reasons"]
    definitions: list[FeatureDefinition] = []
    for need in (*spec.features, spec.label):
        resolution = registry.resolve(need.name)
        if resolution.feature_id is None:
            reasons.append("Unregistered feature: " + need.name)
            continue
        definition = registry.get(resolution.feature_id)
        definitions.append(definition)
        if (
            definition.role != need.role
            or definition.unit != "degF"
            or definition.dtype != "float64"
        ):
            reasons.append("Unsupported role/type/unit for weather modeling: " + need.name)
        if definition.materializer != "research":
            reasons.append("Feature is not materialized by the acquired-data adapter: " + need.name)
    if spec.family != "weather" or not any(
        d.feature_id in {"nws_pfm_max_f", "forecast_high_f"} for d in definitions
    ):
        reasons.append("Weather modeling requires a registered point-in-time forecast level")
    if reasons:
        result["status"] = "unsupported"
        return
    missing = {d.feature_id for d in definitions} - {a["feature_id"] for a in artifacts}
    if missing:
        reasons.append("Missing materialized features: " + ", ".join(sorted(missing)))
        return
    schedule = [point.model_dump(mode="json") for point in spec.decision_schedule]
    if any(artifact["schedule"] != schedule for artifact in artifacts):
        raise ValueError("feature decision schedule differs from the frozen hypothesis")
    rows, missingness = _rows(
        root,
        registry,
        spec,
        artifacts,
        data_kind,
        config.boundaries[2] if config.boundaries else None,
    )
    for identifier in execution_datasets:
        _dataset(root, identifier, data_kind)
    result["eligibility"].update(
        independent_events=len({r["event_id"] for r in rows}),
        independent_dates=len({r["target_date"] for r in rows}),
        complete_events=sum(r["complete"] for r in rows),
        protected_events=sum(r["target_date"] >= config.boundaries[2].isoformat() for r in rows)
        if config.boundaries
        else 0,
        missingness=missingness,
    )
    if any(r["label_available_at"] and _clock(r["label_available_at"]) > now for r in rows):
        raise ValueError("outcome receipt clock is in the future")
    try:
        plan = temporal_plan(rows, config.boundaries)
    except ValueError as exc:
        reasons.append(str(exc))
        return
    partitions = (plan.fit, plan.calibration, plan.validation, plan.holdout)
    for earlier, later in pairwise(partitions):
        if (
            earlier
            and later
            and max(_clock(r["decision_time"]) for r in rows if r["event_id"] in earlier)
            >= min(_clock(r["decision_time"]) for r in rows if r["event_id"] in later)
        ):
            raise ValueError("decision schedules overlap frozen temporal partitions")
    result["validation"].update(
        partitions=_partition(plan), partition_hash=scientific_hash(_partition(plan))
    )
    train = _examples(rows, plan.fit, plan.fit_asof)
    calibration = _examples(rows, plan.calibration, plan.calibration_asof)
    result["eligibility"].update(
        train_eligible_events=len(train),
        calibration_eligible_events=len(calibration),
        training_cutoff=plan.fit_asof.isoformat(),
        calibration_cutoff=plan.calibration_asof.isoformat(),
        training_late_labels=sum(
            r["event_id"] in plan.fit
            and r["complete"]
            and _clock(r["label_available_at"]) > plan.fit_asof
            for r in rows
        ),
    )
    if len(train) < config.min_train_events:
        reasons.append(
            f"{len(train)} independent training events with labels available before cutoff "
            f"< {config.min_train_events}; late receipts cannot be backdated. "
            "A longer window of timely, independent labeled events is required"
        )
        return
    if (
        set(spec.candidate_models) & {"gaussian_error", "ridge", "gradient_boosting"}
        and len(calibration) < config.min_calibration_events
    ):
        reasons.append(
            f"{len(calibration)} independent calibration events with timely labels and embargo "
            f"< {config.min_calibration_events}; a longer window is required before fitting"
        )
        return
    threshold = float(math.floor(median(e.target_f for e in train)))
    balance = {
        "yes": sum(e.target_f <= threshold for e in train),
        "no": sum(e.target_f > threshold for e in train),
    }
    result["eligibility"].update(training_class_balance=balance, threshold_f=threshold)
    if not all(balance.values()):
        reasons.append("Single-class training targets at the training-only median threshold")
        return
    kinds: list[WeatherKind] = ["climatology", "raw_forecast"]
    mapping: dict[str, WeatherKind] = {
        "gaussian_error": "forecast_error",
        "ridge": "ridge",
        "gradient_boosting": "boosting",
    }
    for proposed in spec.candidate_models:
        if proposed in mapping and mapping[proposed] not in kinds:
            kinds.append(mapping[proposed])
    result["model_refusals"] = {
        p: "Requires genuine contract probabilities/decision-time quotes; no surrogate substituted"
        for p in spec.candidate_models
        if p not in {*mapping, "climatology"}
    }
    result["requested_trial_count"] = len(spec.candidate_models) + 2
    result["validation"]["threshold_definition"] = {
        "kind": "training-only integer temperature threshold",
        "threshold_f": threshold,
        "yes": "settlement high at or below threshold",
        "exchange_contract": False,
    }
    predictions: dict[str, list[dict[str, Any]]] = {}
    names = tuple(d.feature_id for d in definitions if d.role == "feature")
    for kind in kinds:
        if cancelled():
            raise InterruptedError("research modeling cancelled or budget exhausted")
        model = WeatherModel(kind, seed=config.seed, feature_names=names)
        model.feature_schema = {
            d.feature_id: d.model_dump(mode="json") for d in definitions if d.role == "feature"
        }
        try:
            with threadpool_limits(limits=1):
                model.fit(
                    train,
                    asof=plan.fit_asof,
                    min_events=config.min_boosting_events
                    if kind == "boosting"
                    else config.min_train_events,
                )
                if kind not in {"climatology", "raw_forecast"}:
                    model.calibrate(
                        calibration,
                        asof=plan.calibration_asof,
                        method=config.calibration,
                        min_events=config.min_calibration_events,
                    )
        except InsufficientHistoryError as exc:
            result["model_refusals"][kind] = str(exc)
            continue
        digest = model.save(staging / (kind + ".joblib"))
        records = _score(rows, plan.validation, model, threshold)
        predictions[kind] = records
        scored = metrics(records, min_events=config.min_evaluation_events)
        result["models"][kind] = {
            "artifact_hash": digest,
            "file": kind + ".joblib",
            "calibration": model.calibration.method,
            "training_events": list(model.training_events),
            "calibration_events": list(model.calibration.event_ids),
            "metrics": scored,
        }
        fitted_thresholds = {}
        for rule in spec.rules:
            if rule.threshold is not None:
                continue
            canonical = registry.resolve(rule.feature).feature_id
            values = [e.features.get(canonical or "") for e in train]
            if any(value is None for value in values):
                raise ValueError("strategy threshold lacks complete registered training features")
            fitted_thresholds[rule.feature] = Decimal(
                str(median(value for value in values if value is not None))
            )
        result["models"][kind]["backtest"] = acquired_backtest(
            root=root,
            registry=registry,
            spec=spec,
            rows=rows,
            model=model,
            model_hash=digest,
            plan=plan,
            execution_datasets=execution_datasets,
            fee_versions=fee_versions,
            data_kind=data_kind,
            fitted_thresholds=fitted_thresholds,
            asof=now,
        )
        result["validation"]["uncertainty"][kind] = _uncertainty(records, config.seed)
        diagnostics = {
            "uncalibrated": _score(rows, plan.validation, model, threshold, calibrated=False),
            "threshold_minus_5f": _score(rows, plan.validation, model, threshold - 5),
            "threshold_plus_5f": _score(rows, plan.validation, model, threshold + 5),
            "forecast_minus_1f": _score(
                rows, plan.validation, model, threshold, forecast_shift_f=-1
            ),
            "forecast_plus_1f": _score(rows, plan.validation, model, threshold, forecast_shift_f=1),
        }
        result["validation"]["sensitivity"][kind] = {
            name: metrics(items, min_events=config.min_evaluation_events)
            for name, items in diagnostics.items()
        }
        if kind in {"climatology", "raw_forecast"}:
            result["baselines"][kind] = scored
    if any(predictions.values()):
        # Use configured order, never validation-score selection. Every model's replay
        # remains visible for search accounting and inspection.
        replay_kind = next(
            (
                k
                for k in kinds
                if k in result["models"] and k not in {"climatology", "raw_forecast"}
            ),
            "raw_forecast",
        )
        if replay_kind in result["models"]:
            result["backtest"] = result["models"][replay_kind]["backtest"]
            result["backtest_model"] = replay_kind
        result["validation"]["baseline_comparisons"] = {
            kind: _comparison(records, predictions.get("climatology", []), config.seed)
            for kind, records in predictions.items()
        }
        result["diagnostic_score_count"] = len(predictions) * 6
        result["warnings"].append(
            "Sensitivity scores are fixed diagnostic perturbations; they do not select a model "
            "or establish observed trading performance."
        )
        (staging / "predictions.json").write_text(json.dumps(predictions, sort_keys=True, indent=2))
        result["status"] = "evaluated"
        result["eligibility"]["eligible"] = True
        enough = max(len(p) for p in predictions.values()) >= config.min_evaluation_events
        result["validation"]["status"] = "evaluated" if enough else "descriptive_small_sample"
        if not enough:
            reasons.append("Insufficient independent validation events for acceptance")
    if config.walk_forward:
        permitted = set(plan.fit + plan.calibration + plan.validation)
        walk_rows = [row for row in rows if row["event_id"] in permitted]
        for index, fold in enumerate(walk_forward_plans(walk_rows), 1):
            if cancelled():
                raise InterruptedError("research modeling cancelled or budget exhausted")
            fold_train = _examples(rows, fold.fit, fold.fit_asof)
            fold_calibration = _examples(rows, fold.calibration, fold.calibration_asof)
            model = WeatherModel("ridge", seed=config.seed, feature_names=names)
            diagnostic: dict[str, Any] = {"fold": index, "partitions": _partition(fold)}
            try:
                with threadpool_limits(limits=1):
                    model.fit(fold_train, asof=fold.fit_asof, min_events=config.min_train_events)
                    model.calibrate(
                        fold_calibration,
                        asof=fold.calibration_asof,
                        min_events=config.min_calibration_events,
                    )
                diagnostic["metrics"] = metrics(
                    _score(
                        rows,
                        fold.validation,
                        model,
                        float(math.floor(median(e.target_f for e in fold_train))),
                    ),
                    min_events=config.min_evaluation_events,
                )
            except InsufficientHistoryError as exc:
                diagnostic["refusal"] = str(exc)
            result["validation"]["walk_forward"].append(diagnostic)
