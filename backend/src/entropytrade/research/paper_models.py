"""Data-only exports of acquired-feature models and strict forward scoring.

Paper workers never deserialize fitted Python objects. These bounded JSON coefficients
retain the exact feature definitions and the single horizon actually used in fitting.
"""

import json
import math
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self
from zoneinfo import ZoneInfo

import numpy as np
from pydantic import Field, model_validator

from entropytrade.data.sources import file_hash
from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import MarketStatus, MarketType
from entropytrade.domain.ids import ContentHash
from entropytrade.domain.market import Market, Strike
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import UtcDatetime
from entropytrade.experiments.data import ExperimentData, PredictionBundle, ProbabilityRecord
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.probability import contract_probability, exact_probability, normal_cdf
from entropytrade.research.materialize import decision_times
from entropytrade.research.model import DecisionPoint
from entropytrade.research.registry import FeatureDefinition, FeatureRegistry

if TYPE_CHECKING:
    from entropytrade.ml.models import WeatherModel

PortableKind = Literal["climatology", "raw_forecast", "forecast_error", "ridge"]


class PortableResearchModel(DomainModel):
    schema_version: Literal["research-weather-forward-v1"] = "research-weather-forward-v1"
    family: PortableKind
    model_hash: ContentHash
    data_kind: Literal["real", "synthetic"]
    available_at: UtcDatetime
    fitted_before: UtcDatetime
    calibrated_before: UtcDatetime | None
    seed: int
    features: tuple[FeatureDefinition, ...] = Field(min_length=1, max_length=10)
    feature_names: tuple[str, ...] = Field(min_length=1, max_length=10)
    feature_schema_hash: ContentHash
    forecast_feature: Literal["nws_pfm_max_f"] = "nws_pfm_max_f"
    dataset_versions: tuple[ContentHash, ...] = Field(min_length=1, max_length=256)
    feature_artifacts: tuple[ContentHash, ...] = Field(min_length=1, max_length=128)
    training_events: tuple[str, ...] = Field(min_length=1, max_length=20_000)
    calibration_events: tuple[str, ...] = Field(max_length=20_000)
    protected_events: tuple[str, ...] = Field(max_length=20_000)
    series: tuple[str, ...] = Field(min_length=1, max_length=8)
    series_locations: dict[str, dict[str, str]]
    selected_schedule: DecisionPoint
    max_decision_delay_seconds: Literal[60] = 60
    sigma_f: float = Field(gt=0, allow_inf_nan=False)
    bias_f: float = Field(allow_inf_nan=False)
    target_history: tuple[float, ...] = Field(max_length=20_000)
    ridge_coefficients: tuple[float, ...] = Field(default=(), max_length=10)
    ridge_intercept: float | None = Field(default=None, allow_inf_nan=False)
    ridge_alpha: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    calibration: Literal["none", "platt", "isotonic"]
    platt_slope: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    platt_intercept: float | None = Field(default=None, allow_inf_nan=False)
    isotonic_x: tuple[float, ...] = Field(default=(), max_length=10_000)
    isotonic_y: tuple[float, ...] = Field(default=(), max_length=10_000)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        definitions = [f.model_dump(mode="json") for f in self.features]
        if self.feature_names != tuple(f.feature_id for f in self.features):
            raise ValueError("portable coefficient order differs from exact feature definitions")
        if self.feature_schema_hash != scientific_hash(definitions):
            raise ValueError("portable feature schema hash mismatch")
        registry = FeatureRegistry()
        for definition in self.features:
            if (
                definition.feature_id not in registry.definitions
                or registry.get(definition.feature_id) != definition
                or definition.role != "feature"
                or definition.unit != "degF"
                or definition.materializer != "research"
            ):
                raise ValueError("unsupported or changed acquired feature definition")
        if self.forecast_feature not in self.feature_names or len(set(self.feature_names)) != len(
            self.feature_names
        ):
            raise ValueError("portable weather model requires the exact PFM level feature")
        groups = (self.training_events, self.calibration_events, self.protected_events)
        if any(len(set(group)) != len(group) for group in groups) or any(
            set(a) & set(b) for i, a in enumerate(groups) for b in groups[i + 1 :]
        ):
            raise ValueError("portable model partitions overlap or duplicate an event")
        if self.available_at < self.fitted_before or (
            self.calibrated_before is not None
            and (
                self.calibrated_before < self.fitted_before
                or self.available_at < self.calibrated_before
            )
        ):
            raise ValueError("portable model availability/cutoff mismatch")
        if set(self.series_locations) != set(self.series) or len(set(self.series)) != len(
            self.series
        ):
            raise ValueError("portable model series/location scope mismatch")
        from entropytrade.research.execution_inputs import execution_locations

        current = execution_locations()
        if any(current.get(series) != self.series_locations[series] for series in self.series):
            raise ValueError("portable model reviewed station/timezone mapping changed")
        if any(not math.isfinite(t) or t != round(t) for t in self.target_history):
            raise ValueError("invalid portable fitted integer targets")
        if self.family == "climatology" and not self.target_history:
            raise ValueError("climatology requires fitted target history")
        if self.family == "ridge" and (
            len(self.ridge_coefficients) != len(self.feature_names)
            or not all(math.isfinite(c) for c in self.ridge_coefficients)
            or self.ridge_intercept is None
            or self.ridge_alpha is None
        ):
            raise ValueError("invalid portable ridge dimensions or coefficients")
        if self.family != "ridge" and (self.ridge_coefficients or self.ridge_intercept is not None):
            raise ValueError("non-ridge model contains regression parameters")
        if self.calibration != "none" and (
            self.calibrated_before is None or not self.calibration_events
        ):
            raise ValueError("portable calibrator requires separate known calibration events")
        if self.calibration == "platt" and (
            self.platt_slope is None or self.platt_intercept is None
        ):
            raise ValueError("portable Platt calibration parameters missing")
        if self.calibration == "isotonic" and (
            len(self.isotonic_x) < 2
            or len(self.isotonic_x) != len(self.isotonic_y)
            or any(not math.isfinite(x) or not 0 <= x <= 1 for x in self.isotonic_x)
            or any(not math.isfinite(y) or not 0 <= y <= 1 for y in self.isotonic_y)
            or any(a >= b for a, b in pairwise(self.isotonic_x))
            or any(a > b for a, b in pairwise(self.isotonic_y))
        ):
            raise ValueError("invalid portable isotonic calibration")
        return self

    def probability(self, features: Mapping[str, float | Decimal | None], strike: Strike) -> float:
        values = [features.get(name) for name in self.feature_names]
        if any(v is None or not math.isfinite(float(v)) for v in values):
            raise ValueError("complete finite acquired features required; no forward imputation")
        vector = [float(v) for v in values if v is not None]
        if self.family == "ridge":
            if self.ridge_intercept is None:
                raise ValueError("portable ridge intercept missing")
            mean = self.ridge_intercept + sum(
                value * coefficient
                for value, coefficient in zip(vector, self.ridge_coefficients, strict=True)
            )
        else:
            forecast = features[self.forecast_feature]
            if forecast is None:
                raise ValueError("PFM forecast required")
            mean = float(forecast) + self.bias_f

        def cdf(value: float) -> float:
            probability = (
                sum(t <= value for t in self.target_history) / len(self.target_history)
                if self.family == "climatology"
                else normal_cdf((value - mean) / self.sigma_f)
            )
            if probability <= 0 or probability >= 1 or self.calibration == "none":
                return probability
            if self.calibration == "platt":
                if self.platt_slope is None or self.platt_intercept is None:
                    raise ValueError("portable calibration incomplete")
                z = (
                    self.platt_slope * math.log(probability / (1 - probability))
                    + self.platt_intercept
                )
                return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
            return float(np.interp(probability, self.isotonic_x, self.isotonic_y))

        return contract_probability(strike, cdf, unit="degF")

    def protects(self, *, series: str, target_date: date, event_id: str) -> bool:
        location = self.series_locations.get(series)
        return event_id in self.protected_events or (
            location is not None
            and location["entity"] + ":" + target_date.isoformat() in self.protected_events
        )


def freeze_research_model(
    model: "WeatherModel",
    *,
    model_hash: str,
    data_kind: str,
    series: tuple[str, ...],
    protected: tuple[str, ...],
    features: tuple[FeatureDefinition, ...],
    feature_artifacts: tuple[str, ...],
    dataset_versions: tuple[str, ...],
    created_at: datetime,
    selected_schedule: DecisionPoint,
) -> PortableResearchModel:
    """Export trusted in-process fitting state; workers only read the resulting JSON."""
    from entropytrade.research.execution_inputs import execution_locations

    if model.kind not in {"climatology", "raw_forecast", "forecast_error", "ridge"}:
        raise ValueError("model family has no reviewed portable paper scorer")
    expected = {f.feature_id: f.model_dump(mode="json") for f in features}
    if model.feature_schema != expected or model.feature_names != tuple(expected):
        raise ValueError("fitted and portable feature definitions differ")
    payload: dict[str, Any] = {
        "family": model.kind,
        "model_hash": model_hash,
        "data_kind": data_kind,
        "available_at": created_at,
        "fitted_before": model.fit_asof,
        "calibrated_before": model.calibration.fit_asof,
        "seed": model.seed,
        "features": features,
        "feature_names": model.feature_names,
        "feature_schema_hash": scientific_hash([f.model_dump(mode="json") for f in features]),
        "dataset_versions": dataset_versions,
        "feature_artifacts": feature_artifacts,
        "training_events": model.training_events,
        "calibration_events": model.calibration.event_ids,
        "protected_events": protected,
        "series": series,
        "series_locations": {key: execution_locations()[key] for key in series},
        "selected_schedule": selected_schedule,
        "sigma_f": model.raw_sigma_f if model.kind == "raw_forecast" else model.sigma_f,
        "bias_f": model.bias_f,
        "target_history": model.target_history,
        "calibration": model.calibration.method,
    }
    if model.kind == "ridge":
        from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
        from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
        from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
        from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

        pipeline = model.estimator
        if not isinstance(pipeline, Pipeline) or tuple(pipeline.named_steps) != (
            "imputer",
            "scale",
            "model",
        ):
            raise ValueError("unsupported portable ridge pipeline")
        imputer, scaler, regressor = (
            pipeline.named_steps[n] for n in ("imputer", "scale", "model")
        )
        if (
            not isinstance(imputer, SimpleImputer)
            or not isinstance(scaler, StandardScaler)
            or not isinstance(regressor, Ridge)
        ):
            raise ValueError("unsupported portable regression transforms")
        coefficients = np.asarray(regressor.coef_) / np.asarray(scaler.scale_)
        payload.update(
            ridge_coefficients=coefficients.tolist(),
            ridge_intercept=float(regressor.intercept_ - np.dot(coefficients, scaler.mean_)),
            ridge_alpha=float(regressor.alpha),
        )
    if model.calibration.method == "platt":
        payload.update(
            platt_slope=float(model.calibration.estimator.coef_[0, 0]),
            platt_intercept=float(model.calibration.estimator.intercept_[0]),
        )
    elif model.calibration.method == "isotonic":
        payload.update(
            isotonic_x=model.calibration.estimator.X_thresholds_.tolist(),
            isotonic_y=model.calibration.estimator.y_thresholds_.tolist(),
        )
    return PortableResearchModel.model_validate(payload)


def verify_research_binding(
    spec: StrategySpec, binding: dict[str, Any], *, data_kind: Literal["real", "synthetic"] = "real"
) -> PortableResearchModel:
    if binding.get("kind") != "research_weather_v1" or binding.get("status") != "bound":
        raise ValueError("no compatible frozen acquired-feature model binding")
    if scientific_hash({k: v for k, v in binding.items() if k != "binding_hash"}) != binding.get(
        "binding_hash"
    ):
        raise ValueError("research model binding hash mismatch")
    model = PortableResearchModel.model_validate(binding["snapshot"])
    if (
        spec.model_ref is None
        or spec.model_ref.family != model.family
        or spec.model_ref.version != model.model_hash
        or binding.get("model_ref") != spec.model_ref.model_dump(mode="json")
        or spec.calibration.value != model.calibration
        or model.data_kind != data_kind
    ):
        raise ValueError("research model reference, calibration or provenance mismatch")
    required = {f.name: f.version for f in spec.features}
    expected = {f.feature_id: f.version for f in model.features}
    if required != expected or not set(spec.market_universe.series_tickers) <= set(model.series):
        raise ValueError("strategy features or series differ from frozen model")
    return model


def load_research_binding(
    root: Path,
    experiment_id: str,
    model_family: str,
    *,
    expected_model_hash: str | None = None,
    data_kind: Literal["real", "synthetic"] = "real",
) -> dict[str, Any]:
    """Load only checksum-verified JSON; no fitted Python object is deserialized."""
    from entropytrade.research.modeling import _dataset, _feature, _path, _read_result

    if model_family not in {"climatology", "raw_forecast", "forecast_error", "ridge"}:
        raise ValueError("model family has no reviewed portable paper scorer")
    path = _path(root, "experiments", experiment_id)
    result = _read_result(path)
    if result["experiment_id"] != experiment_id or result["data_kind"] != data_kind:
        raise ValueError("paper source experiment identity/provenance mismatch")
    entry = result["models"].get(model_family)
    if not entry or not entry.get("portable"):
        raise ValueError("no reviewed data-only portable model export; rerun modeling")
    artifact = entry["portable"]
    filename = model_family + ".paper.json"
    if artifact["file"] != filename or file_hash(path / filename) != artifact["sha256"]:
        raise ValueError("portable model artifact path/hash mismatch")
    model = PortableResearchModel.model_validate_json((path / filename).read_text())
    if (
        model.model_hash != entry["artifact_hash"]
        or model.family != model_family
        or (expected_model_hash is not None and model.model_hash != expected_model_hash)
        or model.data_kind != data_kind
    ):
        raise ValueError("portable and fitted model reference mismatch")
    registry = FeatureRegistry()
    protected_from = min(
        (date.fromisoformat(e.rsplit(":", 1)[-1]) for e in model.protected_events), default=None
    )
    for item in result["provenance"]["feature_artifacts"]:
        directory = _path(root, "features", item["artifact_id"])
        manifest = json.loads((directory / "manifest.json").read_text())
        _feature(root, manifest, registry.get(manifest["feature_id"]), data_kind, protected_from)
    for identifier in model.dataset_versions:
        _dataset(root, identifier, data_kind)
    binding = {
        "kind": "research_weather_v1",
        "status": "bound",
        "reason": None,
        "experiment_id": experiment_id,
        "model_ref": {"family": model.family, "version": model.model_hash},
        "snapshot": model.model_dump(mode="json"),
        "artifact": artifact,
        "report_hash": file_hash(path / "results.json"),
    }
    binding["binding_hash"] = scientific_hash(binding)
    return binding


def _snapshot(binding: dict[str, Any]) -> PortableResearchModel:
    if binding.get("kind") != "research_weather_v1" or scientific_hash(
        {k: v for k, v in binding.items() if k != "binding_hash"}
    ) != binding.get("binding_hash"):
        raise ValueError("research scheduling model binding mismatch")
    return PortableResearchModel.model_validate(binding["snapshot"])


def paper_window(binding: dict[str, Any], now: datetime, series: str | None = None) -> date | None:
    if now.utcoffset() is None:
        raise ValueError("research paper scheduling requires an aware clock")
    model = _snapshot(binding)
    for ticker, location in model.series_locations.items():
        if series is not None and ticker != series:
            continue
        local_day = now.astimezone(ZoneInfo(location["timezone"])).date()
        target = local_day - timedelta(days=model.selected_schedule.day_offset)
        decision = decision_times(target, [model.selected_schedule], location["timezone"])[0]
        if decision <= now <= decision + timedelta(seconds=model.max_decision_delay_seconds):
            return target
    return None


def next_research_decision(binding: dict[str, Any], now: datetime) -> datetime:
    if now.utcoffset() is None:
        raise ValueError("research paper scheduling requires an aware clock")
    model = _snapshot(binding)
    candidates = []
    for location in model.series_locations.values():
        local_day = now.astimezone(ZoneInfo(location["timezone"])).date()
        target = local_day - timedelta(days=model.selected_schedule.day_offset)
        decision = decision_times(target, [model.selected_schedule], location["timezone"])[0]
        if decision <= now:
            decision = decision_times(
                target + timedelta(days=1), [model.selected_schedule], location["timezone"]
            )[0]
        candidates.append(decision)
    return min(candidates).astimezone(UTC)


def score_research_model(
    spec: StrategySpec, data: ExperimentData, binding: dict[str, Any], markets: dict[str, Market]
) -> PredictionBundle:
    records = []
    refusals: dict[str, str] = {}
    metadata: dict[str, Any] = {"data_kind": data.data_kind, "status": "blocked"}
    identity = scientific_hash(binding)
    try:
        from entropytrade.research.execution_inputs import _known_rules

        model = verify_research_binding(spec, binding, data_kind=data.data_kind)
        metadata["split"] = {"holdout": model.protected_events}
        if data.provenance.get("adapter") != "research-forward-v1:weather":
            raise ValueError("acquired model requires the reviewed exact-source forward adapter")
        definitions = data.feature_definitions.get("features", [])
        parsed = tuple(FeatureDefinition.model_validate(f) for f in definitions)
        if {f.feature_id: f for f in parsed} != {f.feature_id: f for f in model.features}:
            raise ValueError("forward and trained feature definitions/source semantics differ")
        if data.provenance.get("feature_schema_hash") != model.feature_schema_hash:
            raise ValueError("forward acquired-feature schema hash mismatch")
        deployment_at = datetime.fromisoformat(
            str(data.provenance.get("deployment_created_at", ""))
        )
        if deployment_at.utcoffset() is None or deployment_at < model.available_at:
            raise ValueError("trusted paper deployment clock missing or before model availability")
        for sample in data.samples:
            try:
                if sample.family not in model.series:
                    raise ValueError("series outside frozen training scope")
                entity = model.series_locations[sample.family]["entity"]
                event = entity + ":" + sample.target_date.isoformat()
                if (
                    sample.event_id in data.protected_events
                    or event in data.protected_events
                    or event in model.protected_events
                ):
                    raise ValueError("protected station-day cannot enter paper decisions")
                if (
                    sample.decision_time < max(model.available_at, deployment_at)
                    or paper_window(binding, sample.decision_time, sample.family)
                    != sample.target_date
                ):
                    raise ValueError("model unavailable or decision outside the trained horizon")
                if (
                    not sample.eligible
                    or not sample.rules_known
                    or sample.features_available_at > sample.decision_time
                ):
                    raise ValueError(
                        "missing point-in-time source features or known contract rules"
                    )
                if sample.versions != {f.feature_id: f.version for f in model.features}:
                    raise ValueError("forward feature versions differ from frozen model")
                market = markets[sample.ticker]
                if (
                    market.strike is None
                    or market.market_type is not MarketType.BINARY
                    or market.status is not MarketStatus.ACTIVE
                    or not _known_rules(
                        market, entity=entity, name=model.series_locations[sample.family]["name"]
                    )
                    or market.ticker != sample.ticker
                    or market.event_ticker != sample.event_id
                    or market.series_ticker != sample.family
                    or market.close_time != sample.close_time
                    or market.rules.captured_at > sample.decision_time
                    or not market.open_time <= sample.decision_time < market.close_time
                    or market.rules.settlement_basis != "contract_text"
                    or market.rules.settlement_target_date != sample.target_date
                ):
                    raise ValueError("matching authentic contract strike/rules unavailable")
                probability = exact_probability(model.probability(sample.features, market.strike))
                records.append(
                    ProbabilityRecord(
                        event_id=sample.event_id,
                        ticker=sample.ticker,
                        decision_time=sample.decision_time,
                        family=model.family,
                        model_hash=model.model_hash,
                        feature_hash=sample.feature_hash,
                        feature_version=data.feature_version,
                        fitted_before=model.available_at,
                        calibrated_before=model.calibrated_before,
                        calibration=model.calibration,
                        probability_yes=probability,
                        partition="forward",
                        prediction_id=scientific_hash(
                            {
                                "binding": identity,
                                "sample": sample.feature_hash,
                                "probability": str(probability),
                            }
                        ),
                    )
                )
            except (ValueError, KeyError) as exc:
                refusals[sample.ticker] = str(exc)
        metadata["status"] = "scored" if records else "blocked"
    except (ValueError, KeyError) as exc:
        refusals["model"] = str(exc)
    return PredictionBundle(
        records=tuple(records), source_hash=identity, model_metadata=metadata, refusals=refusals
    )
