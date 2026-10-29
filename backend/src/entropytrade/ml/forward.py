"""Data-only frozen weather scoring. Never deserializes pickle/joblib or fits on live data."""

import math
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Literal, Self

import numpy as np
from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.ids import ContentHash
from entropytrade.domain.market import Strike
from entropytrade.domain.time import UtcDatetime
from entropytrade.features.registry import feature_schema, scientific_hash
from entropytrade.ml.probability import contract_probability, normal_cdf

if TYPE_CHECKING:
    from entropytrade.ml.models import WeatherModel


class FrozenWeather(DomainModel):
    schema_version: Literal["weather-forward-model-v1"] = "weather-forward-model-v1"
    family: Literal["climatology", "raw_forecast", "forecast_error"]
    model_hash: ContentHash
    data_kind: Literal["real", "synthetic"]
    fitted_before: UtcDatetime
    calibrated_before: UtcDatetime | None
    calibration: Literal["none", "platt", "isotonic"]
    feature_schema_hash: ContentHash
    training_events: tuple[str, ...]
    calibration_events: tuple[str, ...]
    protected_events: tuple[str, ...]
    # Series are extracted from the fitting rows; no automatic geographic transfer.
    series: tuple[str, ...] = Field(min_length=1)
    sigma_f: float = Field(gt=0, allow_inf_nan=False)
    bias_f: float = Field(allow_inf_nan=False)
    target_history: tuple[float, ...]
    platt_slope: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    platt_intercept: float | None = Field(default=None, allow_inf_nan=False)
    isotonic_x: tuple[float, ...] = ()
    isotonic_y: tuple[float, ...] = ()

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.feature_schema_hash != scientific_hash(feature_schema()):
            raise ValueError("unsupported trained weather feature schema")
        if not self.training_events or set(self.training_events) & set(self.calibration_events):
            raise ValueError("missing or overlapping model training events")
        if set(self.protected_events) & set(self.training_events + self.calibration_events):
            raise ValueError("protected events overlap model fitting")
        if self.family == "climatology" and not self.target_history:
            raise ValueError("climatology needs fitted targets")
        if any(not math.isfinite(v) or v != round(v) for v in self.target_history):
            raise ValueError("invalid fitted integer targets")
        if self.calibration != "none" and (
            self.calibrated_before is None
            or self.calibrated_before < self.fitted_before
            or not self.calibration_events
        ):
            raise ValueError("calibrated model needs known separate calibration")
        if self.calibration == "platt" and (
            self.platt_slope is None or self.platt_intercept is None
        ):
            raise ValueError("missing Platt parameters")
        if self.calibration == "isotonic" and (
            len(self.isotonic_x) < 2
            or len(self.isotonic_x) != len(self.isotonic_y)
            or any(not math.isfinite(x) for x in self.isotonic_x)
            or any(not math.isfinite(y) or not 0 <= y <= 1 for y in self.isotonic_y)
            or any(a >= b for a, b in pairwise(self.isotonic_x))
            or any(a > b for a, b in pairwise(self.isotonic_y))
        ):
            raise ValueError("invalid isotonic parameters")
        return self

    def probability(self, forecast: float, strike: Strike) -> float:
        if not math.isfinite(forecast):
            raise ValueError("finite point-in-time forecast required")

        def cdf(value: float) -> float:
            p = (
                sum(t <= value for t in self.target_history) / len(self.target_history)
                if self.family == "climatology"
                else normal_cdf((value - forecast - self.bias_f) / self.sigma_f)
            )
            if p <= 0 or p >= 1 or self.calibration == "none":
                return p
            if self.calibration == "platt":
                assert self.platt_slope is not None  # noqa: S101
                assert self.platt_intercept is not None  # noqa: S101
                z = self.platt_slope * math.log(p / (1 - p)) + self.platt_intercept
                return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
            return float(np.interp(p, self.isotonic_x, self.isotonic_y))

        return contract_probability(strike, cdf, unit="degF")


def freeze_weather(
    model: "WeatherModel",
    *,
    model_hash: str,
    data_kind: str,
    protected: tuple[str, ...],
    series: tuple[str, ...],
) -> FrozenWeather | None:
    if model.kind not in {"climatology", "raw_forecast", "forecast_error"}:
        return None  # Ridge/boosting need a separately reviewed data-only representation.
    calibration = model.calibration
    payload: dict[str, Any] = {
        "family": model.kind,
        "model_hash": model_hash,
        "data_kind": data_kind,
        "fitted_before": model.fit_asof,
        "calibrated_before": calibration.fit_asof,
        "calibration": calibration.method,
        "feature_schema_hash": scientific_hash(model.feature_schema),
        "training_events": model.training_events,
        "calibration_events": calibration.event_ids,
        "protected_events": protected,
        "series": series,
        "sigma_f": model.raw_sigma_f if model.kind == "raw_forecast" else model.sigma_f,
        "bias_f": model.bias_f,
        "target_history": model.target_history,
    }
    if calibration.method == "platt":
        payload.update(
            platt_slope=float(calibration.estimator.coef_[0, 0]),
            platt_intercept=float(calibration.estimator.intercept_[0]),
        )
    elif calibration.method == "isotonic":
        payload.update(
            isotonic_x=calibration.estimator.X_thresholds_.tolist(),
            isotonic_y=calibration.estimator.y_thresholds_.tolist(),
        )
    return FrozenWeather.model_validate(payload)
