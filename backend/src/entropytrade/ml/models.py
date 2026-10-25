"""Event-level statistical/ML temperature models and CDF calibration using scikit-learn."""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import joblib  # type: ignore[import-untyped]
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression, Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from entropytrade.data.sources import file_hash
from entropytrade.domain.market import Strike
from entropytrade.features.registry import FEATURE_NAMES, feature_schema
from entropytrade.ml.probability import contract_probability, normal_cdf
from entropytrade.weather.probability import InsufficientHistoryError


@dataclass(frozen=True)
class EventExample:
    event_id: str
    decision: datetime
    target_date: str
    station: str
    features: dict[str, float | None]
    target_f: float
    label_available: datetime


def matrix(examples: list[EventExample], names: tuple[str, ...] = FEATURE_NAMES) -> Any:
    return np.array(
        [[np.nan if e.features.get(n) is None else e.features[n] for n in names] for e in examples],
        dtype=float,
    )


@dataclass
class CDFCalibration:
    method: str = "none"
    estimator: Any = None
    event_ids: tuple[str, ...] = ()
    fit_asof: datetime | None = None

    def transform(self, p: float) -> float:
        if p <= 0 or p >= 1 or self.estimator is None:
            return max(0.0, min(1.0, p))
        if self.method == "platt":
            logit = math.log(p / (1 - p))
            return float(self.estimator.predict_proba([[logit]])[0, 1])
        return float(self.estimator.predict([p])[0])


@dataclass
class WeatherModel:
    kind: Literal["climatology", "raw_forecast", "forecast_error", "ridge", "boosting"]
    seed: int = 17
    raw_sigma_f: float = 3.0
    estimator: Any = None
    sigma_f: float = 3.0
    bias_f: float = 0.0
    target_history: tuple[float, ...] = ()
    training_events: tuple[str, ...] = ()
    fit_asof: datetime | None = None
    calibration: CDFCalibration = field(default_factory=CDFCalibration)
    feature_names: tuple[str, ...] = FEATURE_NAMES
    feature_schema: dict[str, object] = field(default_factory=feature_schema)
    training_range: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"climatology", "raw_forecast", "forecast_error", "ridge", "boosting"}:
            raise ValueError("unsupported weather model")
        if not math.isfinite(self.raw_sigma_f) or self.raw_sigma_f <= 0:
            raise ValueError("positive finite raw forecast spread required")

    def fit(self, examples: list[EventExample], *, asof: datetime, min_events: int = 60) -> None:
        ids = {e.event_id for e in examples}
        if len(ids) < min_events:
            raise InsufficientHistoryError(
                f"{self.kind}: {len(ids)} independent events < {min_events}"
            )
        if len(ids) != len(examples):
            raise ValueError("fit expects one frozen decision per independent event")
        if any(e.label_available > asof or e.decision >= asof for e in examples):
            raise ValueError("training label/decision is not available before fit cutoff")
        if any(not math.isfinite(e.target_f) or e.target_f != round(e.target_f) for e in examples):
            raise ValueError("integer reported Fahrenheit target required")
        if any(e.features.get("forecast_high_f") is None for e in examples):
            raise ValueError("forecast feature is required")
        self.calibration = CDFCalibration()
        self.estimator = None
        self.training_events = tuple(sorted(ids))
        self.fit_asof = asof
        self.training_range = {
            "decision_start": min(e.decision for e in examples).isoformat(),
            "decision_end": max(e.decision for e in examples).isoformat(),
            "target_start": min(e.target_date for e in examples),
            "target_end": max(e.target_date for e in examples),
            "labels_available_through": max(e.label_available for e in examples).isoformat(),
        }
        targets = np.array([e.target_f for e in examples], dtype=float)
        self.target_history = tuple(float(v) for v in targets)
        if self.kind in {"ridge", "boosting"}:
            regressor = (
                Ridge(alpha=10.0)
                if self.kind == "ridge"
                else HistGradientBoostingRegressor(
                    max_iter=80, max_leaf_nodes=7, l2_regularization=10, random_state=self.seed
                )
            )
            self.estimator = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                    ("scale", StandardScaler()),
                    ("model", regressor),
                ]
            )
            self.estimator.fit(matrix(examples, self.feature_names), targets)
            residuals = targets - self.estimator.predict(matrix(examples, self.feature_names))
        else:
            residuals = targets - np.array(
                [e.features["forecast_high_f"] for e in examples], dtype=float
            )
            self.bias_f = float(np.mean(residuals)) if self.kind == "forecast_error" else 0.0
        self.sigma_f = max(0.5, float(np.std(residuals, ddof=1)))

    def mean(self, features: dict[str, float | None]) -> float:
        forecast = features.get("forecast_high_f")
        if forecast is None:
            raise ValueError("cannot predict without a point-in-time forecast")
        if self.kind in {"ridge", "boosting"}:
            if self.estimator is None:
                raise ValueError("model is not fitted")
            sample = EventExample(
                "",
                datetime.min.replace(tzinfo=UTC),
                "",
                "",
                features,
                0,
                datetime.min.replace(tzinfo=UTC),
            )
            return float(self.estimator.predict(matrix([sample], self.feature_names))[0])
        return forecast + self.bias_f

    def cdf(
        self, features: dict[str, float | None], value: float, *, calibrated: bool = True
    ) -> float:
        if self.fit_asof is None:
            raise ValueError("model is not fitted")
        if self.kind == "climatology":
            if not self.target_history:
                raise ValueError("climatology is not fitted")
            probability = sum(t <= value for t in self.target_history) / len(self.target_history)
        else:
            sigma = self.raw_sigma_f if self.kind == "raw_forecast" else self.sigma_f
            probability = normal_cdf((value - self.mean(features)) / sigma)
        return self.calibration.transform(probability) if calibrated else probability

    def predict_proba(
        self, features: dict[str, float | None], strike: Strike, *, unit: str
    ) -> float:
        return contract_probability(strike, lambda x: self.cdf(features, x), unit=unit)

    def calibrate(
        self,
        examples: list[EventExample],
        *,
        asof: datetime,
        method: str = "platt",
        min_events: int = 20,
    ) -> None:
        ids = {e.event_id for e in examples}
        if len(ids) < min_events:
            raise InsufficientHistoryError("too few independent calibration events")
        if ids.intersection(self.training_events) or len(ids) != len(examples):
            raise ValueError("calibration events overlap training or repeat an event")
        if self.fit_asof is None or any(
            e.decision < self.fit_asof or e.decision >= asof or e.label_available > asof
            for e in examples
        ):
            raise ValueError("calibration leaks across temporal boundaries")
        xs: list[float] = []
        ys: list[int] = []
        for e in examples:
            center = round(self.mean(e.features))
            for offset in (-10, -5, 0, 5, 10):
                threshold = center + offset
                xs.append(self.cdf(e.features, threshold + 0.5, calibrated=False))
                ys.append(int(e.target_f <= threshold))
        if len(set(ys)) < 2:
            raise InsufficientHistoryError("calibration needs both outcome classes")
        if method == "platt":
            values = np.clip(np.array(xs), 1e-9, 1 - 1e-9)
            estimator = LogisticRegression(C=1.0, random_state=self.seed)
            estimator.fit(
                np.log(values / (1 - values)).reshape(-1, 1),
                ys,
                sample_weight=np.full(len(ys), 0.2),
            )
            if estimator.coef_[0, 0] <= 0:
                raise InsufficientHistoryError("CDF calibrator slope must be positive")
        elif method == "isotonic":
            estimator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
            estimator.fit(
                [0.0, *xs, 1.0], [0, *ys, 1], sample_weight=[1000, *([0.2] * len(ys)), 1000]
            )
        else:
            raise ValueError("unsupported calibration method")
        self.calibration = CDFCalibration(method, estimator, tuple(sorted(ids)), asof)

    def save(self, path: Path) -> str:
        joblib.dump(self, path, compress=3)
        return file_hash(path)

    @staticmethod
    def load(path: Path, *, expected_hash: str, trusted: bool = False) -> "WeatherModel":
        if not trusted:
            raise ValueError("joblib artifacts may only be loaded from trusted local runs")
        if file_hash(path) != expected_hash:
            raise ValueError("model artifact hash mismatch")
        model = joblib.load(path)
        if not isinstance(model, WeatherModel):
            raise ValueError("unexpected model artifact")
        return model
