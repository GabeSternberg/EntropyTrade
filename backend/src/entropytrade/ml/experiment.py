"""One deterministic modeling workflow, tracked with the existing SQLite registry and MLflow."""

import fcntl
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from entropytrade.data.schema import Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.base import DomainModel
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import metrics, temporal_plan, walk_forward_plans
from entropytrade.ml.forward import freeze_weather
from entropytrade.ml.models import EventExample, WeatherModel
from entropytrade.ml.probability import strike_from_json
from entropytrade.strategy_registry.store import Registry
from entropytrade.weather.probability import InsufficientHistoryError


class ModelingConfig(DomainModel):
    boundaries: tuple[date, date, date] | None = None
    seed: int = 17
    min_train_events: int = Field(default=60, ge=30)
    min_calibration_events: int = Field(default=20, ge=20)
    min_evaluation_events: int = Field(default=20, ge=20)
    min_boosting_events: int = Field(default=200, ge=100)
    raw_sigma_f: float = Field(default=3.0, gt=0)
    calibration: Literal["none", "platt", "isotonic"] = "platt"
    walk_forward: bool = True
    evaluate_holdout: bool = False


def _examples(
    rows: Sequence[dict[str, Any]], events: tuple[str, ...], asof: datetime
) -> list[EventExample]:
    examples: dict[str, EventExample] = {}
    for row in sorted(rows, key=lambda r: (r["decision_time"], r["market_ticker"])):
        event = row["event_id"]
        if (
            event not in events
            or event in examples
            or not row["feature_eligible"]
            or datetime.fromisoformat(row["decision_time"]) > asof
        ):
            continue
        available = row["temperature_available_at"]
        target = row["temperature_target_f"]
        candidates = [
            Observation.model_validate(p)
            for p in json.loads(row.get("temperature_labels_json", "[]"))
        ]
        known = [o for o in candidates if o.known_at(asof)]
        if candidates:
            if not known:
                continue
            chosen = known[-1]
            target = float(chosen.value)
            available = (
                max(chosen.available_at, chosen.revised_at or chosen.available_at).isoformat()
                if chosen.available_at
                else None
            )
        if target is None or available is None or datetime.fromisoformat(available) > asof:
            continue
        if (
            row["outcome"] is not None
            and row["outcome_available_at"] is not None
            and datetime.fromisoformat(row["outcome_available_at"]) <= asof
        ):
            actual = strike_from_json(row["strike_json"]).resolves_yes(Decimal(str(target)))
            if actual != (row["outcome"] == "yes"):
                continue
        examples[event] = EventExample(
            event,
            datetime.fromisoformat(row["decision_time"]),
            row["target_date"],
            row["station"],
            json.loads(row["feature_values_json"]),
            float(target),
            datetime.fromisoformat(available),
        )
    return list(examples.values())


def run_modeling(
    *,
    features: Path,
    output: Path,
    registry_path: Path,
    tracking: Path,
    config: ModelingConfig,
    data_kind: str = "real",
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_modeling(
            features=features,
            output=output,
            registry_path=registry_path,
            tracking=tracking,
            config=config,
            data_kind=data_kind,
        )


def _run_modeling(
    *,
    features: Path,
    output: Path,
    registry_path: Path,
    tracking: Path,
    config: ModelingConfig,
    data_kind: str = "real",
) -> dict[str, Any]:
    feature_manifest = json.loads((features / "manifest.json").read_text())
    if feature_manifest["data_kind"] != data_kind:
        raise ValueError("modeling data kind does not match feature manifest")
    if (
        file_hash(features / "features.parquet")
        != (features / "features.sha256").read_text().strip()
    ):
        raise ValueError("feature file checksum mismatch")
    rows = pq.read_table(features / "features.parquet").to_pylist()
    code = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    identity = {
        "feature_version": feature_manifest["feature_version"],
        "feature_file_hash": file_hash(features / "features.parquet"),
        "config": config.model_dump(mode="json"),
        "data_kind": data_kind,
        "code": code,
        "runtime": {
            "python": sys.version,
            **{name: version(name) for name in ("scikit-learn", "numpy", "joblib", "pyarrow")},
        },
        "feature_schema": feature_manifest["schema"],
        "target_assumption": "distribution over source-reported integer Fahrenheit highs",
    }
    run_id = scientific_hash(identity)
    destination = output / run_id.removeprefix("sha256:")
    if destination.exists():
        hashes = json.loads((destination / "checksums.json").read_text())
        for name, digest in hashes.items():
            if file_hash(destination / name) != digest:
                raise ValueError("modeling artifact checksum mismatch")
        cached: dict[str, Any] = json.loads((destination / "results.json").read_text())
        _register(cached, destination, registry_path, tracking)
        return cached
    staging = output / (".building-" + run_id.removeprefix("sha256:"))
    if staging.exists():
        # Only this exact run's incomplete staging directory is replaced after interruption.
        import shutil

        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    result: dict[str, Any] = {
        "run_id": run_id,
        **identity,
        "independent_events": len({r["event_id"] for r in rows}),
        "independent_date_blocks": len({r["target_date"] for r in rows}),
        "contracts": len({r["market_ticker"] for r in rows}),
        "feature_rows": len(rows),
        "scalar_label_events": len(
            {r["event_id"] for r in rows if r["temperature_target_f"] is not None}
        ),
        "eligible_events": len({r["event_id"] for r in rows if r["feature_eligible"]}),
        "source_dataset": feature_manifest["source_dataset"],
        "models": {},
        "refusals": {},
        "status": "insufficient_data",
        "holdout_evaluated": False,
        "coverage": {
            "missing_forecast_rows": sum(
                json.loads(r["feature_values_json"])["forecast_high_f"] is None for r in rows
            ),
            "unknown_rule_rows": sum(not r["rules_known_at_decision"] for r in rows),
            "missing_features": {
                definition["name"]: sum(
                    definition["name"] in json.loads(r["missing_features_json"]) for r in rows
                )
                for definition in feature_manifest["schema"]["features"]
            },
        },
        "claims": "Forecast evaluation only; no fills, fees, trading P&L or strategy promotion.",
    }
    predictions: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    try:
        plan = temporal_plan(rows, config.boundaries)
    except ValueError as exc:
        result["reason"] = str(exc)
        result["refusals"] = dict.fromkeys(
            ("climatology", "raw_forecast", "forecast_error", "ridge", "boosting"),
            "insufficient independent dates/known forecasts/source-matched labels",
        )
    else:
        result["split"] = {
            k: (v.isoformat() if isinstance(v, datetime) else list(v))
            for k, v in asdict(plan).items()
        }
        train = _examples(rows, plan.fit, plan.fit_asof)
        calibration = _examples(rows, plan.calibration, plan.calibration_asof)
        result["train_eligible_events"] = len(train)
        result["calibration_eligible_events"] = len(calibration)
        for kind in ("climatology", "raw_forecast", "forecast_error", "ridge", "boosting"):
            model = WeatherModel(kind, seed=config.seed, raw_sigma_f=config.raw_sigma_f)
            minimum = config.min_boosting_events if kind == "boosting" else config.min_train_events
            try:
                with threadpool_limits(limits=1):
                    model.fit(train, asof=plan.fit_asof, min_events=minimum)
            except (InsufficientHistoryError, ValueError) as exc:
                result["refusals"][kind] = str(exc)
                continue
            calibration_note = "uncalibrated baseline"
            if kind in {"forecast_error", "ridge", "boosting"} and config.calibration != "none":
                try:
                    model.calibrate(
                        calibration,
                        asof=plan.calibration_asof,
                        method=config.calibration,
                        min_events=config.min_calibration_events,
                    )
                    calibration_note = model.calibration.method
                except InsufficientHistoryError as exc:
                    calibration_note = "refused: " + str(exc)
            filename = kind + ".joblib"
            digest = model.save(staging / filename)
            forward = freeze_weather(
                model,
                model_hash=digest,
                data_kind=data_kind,
                protected=plan.holdout,
                series=tuple(
                    sorted(
                        {
                            json.loads(r["provenance_json"])["metadata"]["market"]["series_ticker"]
                            for r in rows
                            if r["event_id"] in model.training_events
                        }
                    )
                ),
            )
            if forward is not None:
                (staging / (kind + ".forward.json")).write_text(forward.model_dump_json(indent=2))
            artifacts[digest] = json.dumps(
                {
                    "kind": kind,
                    "file": filename,
                    "hash": digest,
                    "training_events": model.training_events,
                    "calibration_events": model.calibration.event_ids,
                },
                sort_keys=True,
            )
            evaluated: dict[str, list[dict[str, Any]]] = {"validation": []}
            if config.evaluate_holdout:
                evaluated["holdout"] = []
                result["holdout_evaluated"] = True
            for split in evaluated:
                selected = plan.validation if split == "validation" else plan.holdout
                records = _predict_rows(
                    rows,
                    selected,
                    model=model,
                    kind=kind,
                    digest=digest,
                    run_id=run_id,
                    feature_manifest=feature_manifest,
                    split=split,
                    data_kind=data_kind,
                    calibration_note=calibration_note,
                )
                predictions.extend(records)
                evaluated[split].extend(records)
            result["models"][kind] = {
                "artifact_hash": digest,
                "calibration": calibration_note,
                "metrics": {
                    split: metrics(found, min_events=config.min_evaluation_events)
                    for split, found in evaluated.items()
                },
            }
        if config.walk_forward and config.boundaries is None:
            result["walk_forward"] = []
            for index, fold in enumerate(walk_forward_plans(rows), 1):
                fold_result: dict[str, Any] = {
                    "fold": index,
                    "fit_events": list(fold.fit),
                    "calibration_events": list(fold.calibration),
                    "validation_events": list(fold.validation),
                    "fit_asof": fold.fit_asof.isoformat(),
                    "calibration_asof": fold.calibration_asof.isoformat(),
                    "models": {},
                    "refusals": {},
                }
                # Fixed low-complexity diagnostics; no tuning or final-holdout access.
                for fold_kind in ("forecast_error", "ridge"):
                    model = WeatherModel(
                        fold_kind, seed=config.seed, raw_sigma_f=config.raw_sigma_f
                    )
                    try:
                        with threadpool_limits(limits=1):
                            model.fit(
                                _examples(rows, fold.fit, fold.fit_asof),
                                asof=fold.fit_asof,
                                min_events=config.min_train_events,
                            )
                            if config.calibration != "none":
                                model.calibrate(
                                    _examples(rows, fold.calibration, fold.calibration_asof),
                                    asof=fold.calibration_asof,
                                    method=config.calibration,
                                    min_events=config.min_calibration_events,
                                )
                    except InsufficientHistoryError as exc:
                        fold_result["refusals"][fold_kind] = str(exc)
                        continue
                    filename = f"walk-{index}-{fold_kind}.joblib"
                    digest = model.save(staging / filename)
                    artifacts[digest] = json.dumps(
                        {"file": filename, "fold_kind": fold_kind, "fold": index, "hash": digest},
                        sort_keys=True,
                    )
                    records = _predict_rows(
                        rows,
                        fold.validation,
                        model=model,
                        kind=fold_kind,
                        digest=digest,
                        run_id=run_id,
                        feature_manifest=feature_manifest,
                        split=f"walk_forward_{index}",
                        data_kind=data_kind,
                        calibration_note=model.calibration.method,
                    )
                    predictions.extend(records)
                    fold_result["models"][fold_kind] = metrics(
                        records, min_events=config.min_evaluation_events
                    )
                result["walk_forward"].append(fold_result)
        benchmark = []
        for row in rows:
            if (
                row["event_id"] in plan.validation
                and row["outcome"] is not None
                and row["feature_eligible"]
            ):
                reference = _market_reference(row)
                if reference is not None:
                    benchmark.append(
                        {
                            "event_id": row["event_id"],
                            "outcome": row["outcome"],
                            "probability_yes": reference["midpoint"],
                        }
                    )
        result["market_benchmark"] = metrics(benchmark, min_events=config.min_evaluation_events)
        result["market_benchmark"]["basis"] = "timed quoted midpoint; not executable fills"
        if result["models"]:
            result["status"] = "evaluated" if predictions else "no_eligible_evaluation_predictions"
        else:
            result["reason"] = (
                "insufficient independent events with known forecasts "
                "and source-matched scalar labels"
            )
    _write_run(staging, result, predictions)
    output.mkdir(parents=True, exist_ok=True)
    staging.rename(destination)
    _register(result, destination, registry_path, tracking)
    return result


def _register(result: dict[str, Any], path: Path, registry_path: Path, tracking: Path) -> None:
    artifacts = {
        file_hash(p): json.dumps({"file": p.name, "hash": file_hash(p)}, sort_keys=True)
        for p in path.glob("*.joblib")
    }
    predictions = [
        json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()
    ]
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry = Registry(registry_path)
    try:
        registry.record_probability_run(
            result["run_id"], json.dumps(result, sort_keys=True), artifacts, predictions
        )
    finally:
        registry.close()
    _track(result, path, tracking)


def _predict_rows(
    rows: Sequence[dict[str, Any]],
    selected: tuple[str, ...],
    *,
    model: WeatherModel,
    kind: str,
    digest: str,
    run_id: str,
    feature_manifest: dict[str, Any],
    split: str,
    data_kind: str,
    calibration_note: str,
) -> list[dict[str, Any]]:
    predictions = []
    for row in rows:
        if row["event_id"] not in selected or not row["feature_eligible"] or row["outcome"] is None:
            continue
        decision = datetime.fromisoformat(row["decision_time"])
        cutoff = model.calibration.fit_asof or model.fit_asof
        if cutoff is None or decision < cutoff:
            raise ValueError("evaluation decision precedes model/calibration availability")
        vector = json.loads(row["feature_values_json"])
        with threadpool_limits(limits=1):
            probability = model.predict_proba(
                vector, strike_from_json(row["strike_json"]), unit="degF"
            )
        price = _market_reference(row)
        record = {
            "model": kind,
            "model_hash": digest,
            "model_run": run_id,
            "event_id": row["event_id"],
            "target_date": row["target_date"],
            "market_ticker": row["market_ticker"],
            "decision_time": row["decision_time"],
            "probability_yes": probability,
            "feature_version": feature_manifest["feature_version"],
            "feature_hash": row["feature_hash"],
            "source_dataset": feature_manifest["source_dataset"],
            "feature_values": vector,
            "outcome": row["outcome"],
            "split": split,
            "data_kind": data_kind,
            "calibration": calibration_note,
            "fit_asof": model.fit_asof.isoformat() if model.fit_asof else None,
            "calibration_asof": model.calibration.fit_asof.isoformat()
            if model.calibration.fit_asof
            else None,
            "market_reference": price,
            "uncertainty": {
                "sigma_f": (
                    None
                    if kind == "climatology"
                    else model.raw_sigma_f
                    if kind == "raw_forecast"
                    else model.sigma_f
                ),
                "basis": "empirical training-temperature CDF"
                if kind == "climatology"
                else "assumed spread"
                if kind == "raw_forecast"
                else "train residual spread; not a confidence interval",
            },
            "gross_edge": None if price is None else probability - price["midpoint"],
            "net_edge": None,
            "executable_price": None,
        }
        record["prediction_id"] = scientific_hash(record)
        predictions.append(record)
    return predictions


def _market_reference(row: dict[str, Any]) -> dict[str, Any] | None:
    value = row.get("market_state_json")
    if value is None:
        return None
    state = json.loads(value)
    if state["available_at"] is None or state["fidelity"] not in {"order_book", "quote"}:
        return None
    at = datetime.fromisoformat(state["available_at"])
    decision = datetime.fromisoformat(row["decision_time"])
    if at > decision or (decision - at).total_seconds() > 300:
        return None
    payload = state["payload"]
    if state["fidelity"] == "order_book":
        if not payload.get("bids") or not payload.get("asks"):
            return None
        bid = float(payload["bids"][0]["price"])
        ask = float(payload["asks"][0]["price"])
    else:
        if payload.get("bid") is None or payload.get("ask") is None:
            return None
        bid = float(payload["bid"])
        ask = float(payload["ask"])
    if not 0 <= bid <= ask <= 1:
        return None
    return {
        "midpoint": (bid + ask) / 2,
        "fidelity": state["fidelity"],
        "available_at": state["available_at"],
        "raw_ref": state["raw_ref"],
        "is_executable_fill": False,
    }


def _write_run(path: Path, result: dict[str, Any], predictions: list[dict[str, Any]]) -> None:
    (path / "results.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    (path / "predictions.jsonl").write_text(
        "".join(json.dumps(p, sort_keys=True) + "\n" for p in predictions)
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"prediction_id": p["prediction_id"], "payload_json": json.dumps(p, sort_keys=True)}
                for p in predictions
            ],
            schema=pa.schema([("prediction_id", pa.string()), ("payload_json", pa.string())]),
        ),
        path / "predictions.parquet",
    )
    report = [
        "# Probability modeling evaluation",
        "",
        f"Data kind: **{result['data_kind']}**.",
        f"Status: **{result['status']}**.",
        f"Independent events: {result['independent_events']}.",
        f"Eligible forecast events: {result['eligible_events']}.",
        result.get(
            "reason",
            "Metrics use independent-event weights; held-out dates are never used in fitting.",
        ),
        "",
        result["claims"],
    ]
    report += [
        "",
        f"Source-matched scalar-label events: {result['scalar_label_events']}.",
        f"Independent date blocks: {result['independent_date_blocks']}.",
        f"Missing forecast rows: {result['coverage']['missing_forecast_rows']}.",
        f"Unknown historic rule rows: {result['coverage']['unknown_rule_rows']}.",
        f"Final holdout evaluated: {result['holdout_evaluated']}.",
        "",
        "| Model | Split | Events | Brier | Log loss |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for name, model in result["models"].items():
        for split, values in model["metrics"].items():
            if "brier" in values:
                report.append(
                    f"| {name} | {split} | {values['independent_events']} | "
                    f"{values['brier']:.4f} | {values['log_loss']:.4f} |"
                )
    for name, reason in result["refusals"].items():
        report.append(f"\n{name} refused: {reason}.")
    report += [
        "",
        "Full reliability, calibration, coverage and walk-forward diagnostics: results.json.",
    ]
    (path / "report.md").write_text("\n".join(report) + "\n")
    (path / "checksums.json").write_text(
        json.dumps({p.name: file_hash(p) for p in path.iterdir()}, sort_keys=True)
    )


def _track(result: dict[str, Any], path: Path, tracking: Path) -> None:
    import mlflow

    tracking.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking.resolve().as_uri())
    mlflow.set_experiment("entropytrade-probability-models")
    experiment = mlflow.get_experiment_by_name("entropytrade-probability-models")
    if experiment is None:
        raise ValueError("MLflow experiment creation failed")
    if mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"params.run_id = '{result['run_id']}' AND attributes.status = 'FINISHED'",
        output_format="list",
    ):
        return
    with mlflow.start_run(run_name=result["run_id"]):
        mlflow.log_params(
            {
                "run_id": result["run_id"],
                "data_kind": result["data_kind"],
                "feature_version": result["feature_version"],
                "status": result["status"],
            }
        )
        mlflow.log_metric("independent_events", result["independent_events"])
        for kind, model in result["models"].items():
            for split, values in model["metrics"].items():
                for key in ("brier", "log_loss"):
                    if key in values:
                        mlflow.log_metric(f"{kind}.{split}.{key}", values[key])
        mlflow.log_artifacts(str(path))
