"""Family-neutral experiment inputs, versioned prediction providers and a weather bridge."""

import json
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field, model_validator

from entropytrade.data.sources import file_hash
from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import MarketResult
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.strategy import CalibrationMethod, StrategySpec
from entropytrade.domain.time import UtcDatetime


class ContractSample(DomainModel):
    event_id: str
    ticker: str
    family: str
    target_date: date
    decision_time: UtcDatetime
    close_time: UtcDatetime
    features_available_at: UtcDatetime
    features: dict[str, Decimal | None]
    versions: dict[str, str]
    feature_hash: str
    sources: tuple[str, ...] = ()
    rules_known: bool
    eligible: bool
    # Targets are separate and never passed to a strategy or research agent.
    outcome: MarketResult | None = None
    outcome_available_at: UtcDatetime | None = None
    book: OrderBook | None = None
    fidelity: str = "missing"

    @model_validator(mode="after")
    def book_clock(self) -> "ContractSample":
        if self.features_available_at > self.decision_time:
            raise ValueError("features became available after decision")
        if self.book and (
            self.book.market_ticker != self.ticker or self.book.received_at > self.decision_time
        ):
            raise ValueError("sample book must be for this contract and received by decision")
        if self.outcome is not None and self.outcome_available_at is None:
            raise ValueError("resolved targets need availability timestamps")
        return self


class ExperimentData(DomainModel):
    dataset_version: str
    feature_version: str
    data_kind: Literal["real", "synthetic"]
    samples: tuple[ContractSample, ...]
    protected_events: frozenset[str] = frozenset()
    # No engine-specific weather column. Family adapters define features/outcome semantics.
    feature_definitions: dict[str, Any]
    provenance: dict[str, Any]


class ProbabilityRecord(DomainModel):
    event_id: str
    ticker: str
    decision_time: UtcDatetime
    family: str
    model_hash: str
    feature_hash: str
    feature_version: str
    fitted_before: UtcDatetime
    calibrated_before: UtcDatetime | None = None
    calibration: str
    probability_yes: Decimal = Field(ge=0, le=1)
    partition: str
    prediction_id: str

    def usable(self, sample: ContractSample) -> bool:
        return (
            self.fitted_before <= sample.decision_time
            and (self.calibrated_before is None or self.calibrated_before <= sample.decision_time)
            and self.feature_hash == sample.feature_hash
            and self.ticker == sample.ticker
            and self.event_id == sample.event_id
            and self.decision_time == sample.decision_time
        )


class PredictionBundle(DomainModel):
    records: tuple[ProbabilityRecord, ...]
    source_hash: str
    model_metadata: dict[str, Any]
    refusals: dict[str, str] = Field(default_factory=dict)


class PredictionProvider(Protocol):
    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        """Fit/load through deterministic temporal gates, never on final holdout."""
        ...


class AdapterRegistry:
    """Small explicit registration boundary, not dynamic plugin/code loading."""

    def __init__(self) -> None:
        self.providers: dict[str, PredictionProvider] = {}
        self.data_loaders: dict[str, Callable[[Path], ExperimentData]] = {}

    def register(
        self, family: str, loader: Callable[[Path], ExperimentData], provider: PredictionProvider
    ) -> None:
        if family in self.providers:
            raise ValueError("market family already registered")
        self.providers[family] = provider
        self.data_loaders[family] = loader


class RecordedPredictions:
    """Generic adapter for trusted, versioned precomputed point-in-time probabilities."""

    def __init__(self, bundle: PredictionBundle) -> None:
        self.bundle = bundle

    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        if spec.model_ref and spec.model_ref.family != family:
            raise ValueError("requested model family disagrees with explicit model reference")
        if family not in {r.family for r in self.bundle.records}:
            raise ValueError("requested probability family is unavailable")
        return self.bundle


def weather_data(features: Path) -> ExperimentData:
    """Bridge R2 matrices into generic contract samples without interpreting candles as books."""
    manifest = json.loads((features / "manifest.json").read_text())
    if (
        file_hash(features / "features.parquet")
        != (features / "features.sha256").read_text().strip()
    ):
        raise ValueError("feature checksum mismatch")
    samples = []
    for row in pq.read_table(features / "features.parquet").to_pylist():
        provenance = json.loads(row["provenance_json"])
        market = provenance["metadata"]["market"]
        sources = {"kalshi" if manifest["data_kind"] == "real" else "synthetic-kalshi"}
        sources.update(
            value["source_id"]
            for value in provenance["features"].values()
            if isinstance(value, dict) and "source_id" in value
        )
        book = None
        state = json.loads(row["market_state_json"]) if row["market_state_json"] else None
        if (
            state
            and state["fidelity"] == "order_book"
            and state["available_at"]
            and datetime.fromisoformat(state["available_at"])
            <= datetime.fromisoformat(row["decision_time"])
        ):
            raw = dict(state["payload"])
            raw["received_at"] = state["available_at"]
            book = OrderBook.model_validate(raw)
        samples.append(
            ContractSample(
                event_id=row["event_id"],
                ticker=row["market_ticker"],
                family=market["series_ticker"],
                target_date=row["target_date"],
                decision_time=row["decision_time"],
                close_time=market["close_time"],
                features_available_at=row["decision_time"],
                features={
                    k: None if v is None else Decimal(str(v))
                    for k, v in json.loads(row["feature_values_json"]).items()
                },
                versions={f["name"]: f["version"] for f in manifest["schema"]["features"]},
                feature_hash=row["feature_hash"],
                sources=tuple(sorted(sources)),
                rules_known=row["rules_known_at_decision"],
                eligible=row["feature_eligible"],
                outcome=row["outcome"],
                outcome_available_at=row["outcome_available_at"],
                book=book,
                fidelity="order_book" if book else row["execution_fidelity"],
            )
        )
    return ExperimentData(
        dataset_version=manifest["source_dataset"],
        feature_version=manifest["feature_version"],
        data_kind=manifest["data_kind"],
        samples=tuple(samples),
        protected_events=frozenset(manifest.get("protected_events", [])),
        feature_definitions=manifest["schema"],
        provenance={
            "feature_file_hash": file_hash(features / "features.parquet"),
            "adapter": "daily-high-r2-v1",
        },
    )


class WeatherPredictions:
    """Reuse R2 fitting/calibration/evaluation; engine code never fits a weather-specific model."""

    def __init__(
        self, features: Path, output: Path, registry: Path, tracking: Path, *, data_kind: str
    ) -> None:
        self.features, self.output, self.registry, self.tracking = (
            features,
            output,
            registry,
            tracking,
        )
        self.data_kind = data_kind
        self.protected_events: frozenset[str] = frozenset()
        self.cache: dict[str, PredictionBundle] = {}

    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        from entropytrade.ml.experiment import ModelingConfig, run_modeling

        calibration: Literal["none", "platt", "isotonic"] = (
            "none"
            if spec.calibration is CalibrationMethod.NONE
            else "platt"
            if spec.calibration is CalibrationMethod.PLATT
            else "isotonic"
        )
        if family not in {"climatology", "raw_forecast", "forecast_error", "ridge", "boosting"}:
            raise ValueError("unregistered weather probability model")
        key = family + ":" + calibration
        if key in self.cache:
            return self.cache[key]
        from entropytrade.ml.evaluation import temporal_plan

        metadata_rows = pq.read_table(
            self.features / "features.parquet", columns=["event_id", "target_date", "decision_time"]
        ).to_pylist()
        manifest = json.loads((self.features / "manifest.json").read_text())
        boundaries = (
            tuple(date.fromisoformat(d) for d in manifest["temporal_boundaries"])
            if "temporal_boundaries" in manifest
            else None
        )
        if boundaries is not None and len(boundaries) != 3:
            raise ValueError("retained weather needs exactly three frozen boundaries")
        fixed = None if boundaries is None else (boundaries[0], boundaries[1], boundaries[2])
        try:
            plan = temporal_plan(metadata_rows, fixed)
        except ValueError:
            plan = None
        if (
            plan is not None
            and set(plan.fit + plan.calibration + plan.validation) & self.protected_events
        ):
            raise ValueError(
                "protected boundary overlaps fitting/evaluation; use an earlier partition"
            )
        config = ModelingConfig(calibration=calibration, evaluate_holdout=False, boundaries=fixed)
        result = run_modeling(
            features=self.features,
            output=self.output,
            registry_path=self.registry,
            tracking=self.tracking,
            config=config,
            data_kind=self.data_kind,
        )
        directory = self.output / result["run_id"].removeprefix("sha256:")
        predictions = [
            json.loads(line) for line in (directory / "predictions.jsonl").read_text().splitlines()
        ]
        records = tuple(
            ProbabilityRecord(
                event_id=p["event_id"],
                ticker=p["market_ticker"],
                decision_time=p["decision_time"],
                family=p["model"],
                model_hash=p["model_hash"],
                feature_hash=p["feature_hash"],
                feature_version=p["feature_version"],
                fitted_before=p["fit_asof"],
                calibrated_before=p["calibration_asof"],
                calibration=p["calibration"],
                probability_yes=Decimal(str(p["probability_yes"])),
                partition=p["split"],
                prediction_id=p["prediction_id"],
            )
            for p in predictions
        )
        bundle = PredictionBundle(
            records=records,
            source_hash=file_hash(directory / "results.json"),
            model_metadata={
                "model_run": result["run_id"],
                "split": result.get("split"),
                "walk_forward": result.get("walk_forward", []),
                "data_kind": self.data_kind,
            },
            refusals=result["refusals"],
        )
        # Multiple requests sharing a calibration regime reuse the same deterministic run.
        for name in ("climatology", "raw_forecast", "forecast_error", "ridge", "boosting"):
            self.cache[name + ":" + calibration] = bundle
        return bundle
