"""Fixed, event-weighted Bitcoin binary models with receipt-time target cutoffs.

This estimates finalized contract-result probabilities, not a scalar BRTI distribution.
No weather model, price-source substitution, calibration fit or holdout evaluation is used.
"""

import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult
from entropytrade.domain.strategy import CalibrationMethod, StrategySpec
from entropytrade.experiments.data import (
    ExperimentData,
    PredictionBundle,
    ProbabilityRecord,
)
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import TemporalPlan

MODELS = ("bitcoin_logistic", "bitcoin_frequency")


class BitcoinPredictions:
    def __init__(self, data: ExperimentData, output: Path) -> None:
        self.data, self.output = data, output
        self.cache: PredictionBundle | None = None

    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        if family not in MODELS or (spec.model_ref and spec.model_ref.family != family):
            raise ValueError("unregistered Bitcoin binary model")
        if spec.calibration is not CalibrationMethod.NONE:
            raise ValueError("Bitcoin models currently support uncalibrated probabilities only")
        if self.cache is not None:
            return self.cache
        data = self.data
        metadata: dict[str, Any] = {
            "data_kind": data.data_kind,
            "status": "INSUFFICIENT_DATA",
            "target": "finalized Kalshi binary result; no reconstructed scalar price",
            "calibration": "none",
            "baseline_family": "bitcoin_frequency",
            "final_holdout_evaluated": False,
        }
        records: list[ProbabilityRecord] = []
        refusals: dict[str, str] = {}
        try:
            event_dates: dict[str, date] = {}
            for sample in data.samples:
                if (
                    event_dates.setdefault(sample.event_id, sample.target_date)
                    != sample.target_date
                ):
                    raise ValueError("one Bitcoin event cannot span multiple target dates")
            partition = data.provenance["partition"]
            anchor = date.fromisoformat(partition["anchor"])
            fit_end = date.fromisoformat(partition["fit_before"])
            holdout_start = date.fromisoformat(partition["holdout_start"])
            if not anchor < fit_end < holdout_start:
                raise ValueError("invalid fixed Bitcoin calendar partitions")
            fit_asof = datetime(fit_end.year, fit_end.month, fit_end.day, tzinfo=UTC)
            plan = TemporalPlan(
                fit=tuple(
                    sorted({s.event_id for s in data.samples if anchor <= s.target_date < fit_end})
                ),
                calibration=(),
                validation=tuple(
                    sorted(
                        {
                            s.event_id
                            for s in data.samples
                            if fit_end <= s.target_date < holdout_start
                        }
                    )
                ),
                holdout=tuple(
                    sorted({s.event_id for s in data.samples if s.target_date >= holdout_start})
                ),
                fit_asof=fit_asof,
                calibration_asof=fit_asof,
            )
            if set(plan.fit + plan.calibration + plan.validation) & data.protected_events:
                raise ValueError("protected events overlap model fitting/evaluation partitions")
            metadata["split"] = {
                "fit": plan.fit,
                "calibration": plan.calibration,
                "validation": plan.validation,
                "holdout": plan.holdout,
            }
            # Outcome clocks, not close or settlement clocks, determine training usability.
            train = [
                s
                for s in data.samples
                if s.event_id in plan.fit
                and s.eligible
                and s.outcome in {MarketResult.YES, MarketResult.NO}
                and s.outcome_available_at is not None
                and s.close_time <= s.outcome_available_at <= plan.fit_asof
                and s.decision_time < plan.fit_asof
                and s.features.get("scaled_moneyness") is not None
            ]
            validation = [
                s
                for s in data.samples
                if s.event_id in plan.validation
                and s.decision_time >= plan.fit_asof
                and s.eligible
                and s.features.get("scaled_moneyness") is not None
            ]
            metadata["fit_events"] = len({s.event_id for s in train})
            metadata["fit_date_blocks"] = len({s.target_date for s in train})
            if metadata["fit_events"] < 40 or metadata["fit_date_blocks"] < 20:
                raise ValueError(
                    "need 40 fit events on 20 dates with finalized labels "
                    "received before fit cutoff"
                )
            if (
                len({s.event_id for s in validation}) < 20
                or len({s.target_date for s in validation}) < 10
            ):
                raise ValueError("need 20 independent validation events on ten dates")
            counts = Counter(s.event_id for s in train)
            weights = np.asarray([1 / counts[s.event_id] for s in train])
            x = np.asarray([float(s.features["scaled_moneyness"]) for s in train]).reshape(-1, 1)  # type: ignore[arg-type]
            y = np.asarray([s.outcome is MarketResult.YES for s in train], dtype=int)
            if len(set(y)) != 2:
                raise ValueError("both binary outcomes are required in fitting history")
            # Fixed regularization and feature map: no tuning/search over validation results.
            estimator = LogisticRegression(C=1, solver="lbfgs", max_iter=1000, random_state=17)
            estimator.fit(x, y, sample_weight=weights)
            if estimator.coef_[0, 0] <= 0:
                refusals["bitcoin_logistic"] = (
                    "nonpositive moneyness slope; monotonic contract probability gate failed"
                )
            baseline = float(np.average(y, weights=weights))
            parameters = {
                "coefficient": float(estimator.coef_[0, 0]),
                "intercept": float(estimator.intercept_[0]),
                "frequency": baseline,
                "C": 1,
                "seed": 17,
                "training": scientific_hash([s.model_dump(mode="json") for s in train]),
                "feature_version": data.feature_version,
                "fit_asof": plan.fit_asof.isoformat(),
                "implementation": file_hash(Path(__file__)),
                "scope": "one frozen decision per event; each event has total weight one",
            }
            metadata["parameters"] = parameters
            horizons = [float(s.features["hours_to_close"]) for s in train]  # type: ignore[arg-type]
            lower, upper = float(x.min()), float(x.max())
            for sample in validation:
                value = float(sample.features["scaled_moneyness"])  # type: ignore[arg-type]
                horizon = float(sample.features["hours_to_close"])  # type: ignore[arg-type]
                # No extrapolation to unobserved horizons or moneyness ranges.
                if not lower <= value <= upper or not min(horizons) <= horizon <= max(horizons):
                    continue
                for model in MODELS:
                    if model in refusals:
                        continue
                    probability = (
                        baseline
                        if model == "bitcoin_frequency"
                        else float(estimator.predict_proba([[value]])[0, 1])
                    )
                    identity = {
                        "sample": sample.feature_hash,
                        "model": model,
                        "parameters": parameters,
                    }
                    records.append(
                        ProbabilityRecord(
                            event_id=sample.event_id,
                            ticker=sample.ticker,
                            decision_time=sample.decision_time,
                            family=model,
                            model_hash=scientific_hash({"model": model, "parameters": parameters}),
                            feature_hash=sample.feature_hash,
                            feature_version=data.feature_version,
                            fitted_before=plan.fit_asof,
                            calibration="none",
                            probability_yes=Decimal(str(probability)),
                            partition="validation",
                            prediction_id=scientific_hash(identity),
                        )
                    )
            metadata["status"] = "PREDICTED" if records else "INSUFFICIENT_DATA"
            if not records:
                raise ValueError("validation covariates fall outside the observed training domain")
        except ValueError as exc:
            refusals.update({name: str(exc) for name in MODELS})
        payload = {
            "metadata": metadata,
            "refusals": refusals,
            "records": [r.model_dump(mode="json") for r in records],
        }
        bundle_identity = scientific_hash(payload)
        directory = self.output / bundle_identity.removeprefix("sha256:")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "results.json").write_text(json.dumps(payload, sort_keys=True, indent=2))
        # Existing protected browser projection consumes the same prediction artifact format.
        (directory / "predictions.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "prediction_id": r.prediction_id,
                        "market_ticker": r.ticker,
                        "decision_time": r.decision_time.isoformat(),
                        "model": r.family,
                        "model_hash": r.model_hash,
                        "probability_yes": str(r.probability_yes),
                        "feature_hash": r.feature_hash,
                        "fit_asof": r.fitted_before.isoformat(),
                        "calibration_asof": None,
                        "split": r.partition,
                    },
                    sort_keys=True,
                )
                + "\n"
                for r in records
            )
        )
        self.cache = PredictionBundle(
            records=tuple(records),
            source_hash=bundle_identity,
            model_metadata=metadata,
            refusals=refusals,
        )
        return self.cache
