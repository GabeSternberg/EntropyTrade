"""Freeze server-produced model evidence at monitor creation and score causal forward samples."""

from pathlib import Path
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.domain.market import Market
from entropytrade.domain.strategy import StrategySpec
from entropytrade.experiments.data import ExperimentData, PredictionBundle, ProbabilityRecord
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather
from entropytrade.ml.probability import exact_probability


def freeze_binding(
    job: dict[str, Any], candidate_id: str, spec: StrategySpec, workspace: Path
) -> tuple[StrategySpec, dict[str, Any]]:
    candidate: dict[str, Any] = next(
        (c for c in job["result"].get("candidates", []) if c["candidate_id"] == candidate_id), {}
    )
    executed = candidate.get("executed_spec")
    if executed:
        resolved = StrategySpec.model_validate(executed)
        if resolved.revalidated(model_ref=spec.model_ref) != spec or (
            spec.model_ref is not None and resolved.model_ref != spec.model_ref
        ):
            raise ValueError("executed strategy differs from research proposal")
        spec = resolved
    binding: dict[str, Any] = {
        "status": "blocked",
        "model_ref": spec.model_ref.model_dump() if spec.model_ref else None,
        "reason": "No frozen fitted model for this candidate; collection cannot fit or promote it",
        "snapshot": None,
    }
    if spec.model_ref is not None:
        expected = spec.model_ref
        root = (workspace / "runs" / job["id"] / "workflow").resolve()
        matches = []
        for artifact in job["result"].get("artifacts", []):
            name = Path(artifact["path"])
            if (
                len(name.parts) != 3
                or name.parts[0] != "models"
                or name.name != expected.family + ".forward.json"
            ):
                continue
            path = (root / name).resolve()
            if (
                not path.is_relative_to(root)
                or path.stat().st_size > 1_000_000
                or file_hash(path) != artifact["sha256"]
            ):
                raise ValueError("frozen model artifact checksum/path mismatch")
            model = FrozenWeather.model_validate_json(path.read_text())
            if model.model_hash != expected.version or model.family != expected.family:
                continue
            if model.data_kind != "real":
                raise ValueError("synthetic model cannot score real shadow data")
            matches.append((model, artifact))
        if len(matches) == 1:
            model, artifact = matches[0]
            binding.update(
                status="bound",
                reason=None,
                snapshot=model.model_dump(mode="json"),
                artifact=artifact,
            )
        else:
            binding["reason"] = "No unique compatible data-only export for frozen model reference"
    binding["binding_hash"] = scientific_hash(binding)
    return spec, binding


def score(
    spec: StrategySpec,
    data: ExperimentData,
    binding: dict[str, Any] | None,
    markets: dict[str, Market],
) -> PredictionBundle:
    if binding is not None and binding.get("kind") == "research_weather_v1":
        from entropytrade.research.paper_models import score_research_model

        return score_research_model(spec, data, binding, markets)
    records = []
    refusals: dict[str, str] = {}
    metadata: dict[str, Any] = {"data_kind": "real", "status": "blocked"}
    identity = scientific_hash(binding)
    try:
        if binding is None or binding.get("status") != "bound":
            raise ValueError((binding or {}).get("reason") or "No frozen model binding")
        if scientific_hash(
            {k: v for k, v in binding.items() if k != "binding_hash"}
        ) != binding.get("binding_hash"):
            raise ValueError("Frozen model binding hash mismatch")
        model = FrozenWeather.model_validate(binding["snapshot"])
        metadata["split"] = {"holdout": model.protected_events}
        metadata["data_kind"] = model.data_kind
        if (
            spec.model_ref is None
            or spec.model_ref.version != model.model_hash
            or spec.model_ref.family != model.family
        ):
            raise ValueError("Frozen model reference mismatch")
        if model.data_kind != data.data_kind or model.data_kind != "real":
            raise ValueError("Frozen model/data provenance mismatch")
        if data.provenance.get("adapter") != "public-forward-v1:weather":
            raise ValueError("No compatible forward feature adapter for this model")
        protected = data.protected_events | frozenset(model.protected_events)
        for sample in data.samples:
            if sample.event_id in protected:
                continue
            try:
                if sample.family not in model.series:
                    raise ValueError("Series outside frozen training scope")
                if model.fitted_before > sample.decision_time or (
                    model.calibrated_before is not None
                    and model.calibrated_before > sample.decision_time
                ):
                    raise ValueError("Model unavailable at decision")
                if (
                    model.calibration != spec.calibration.value
                    or not sample.eligible
                    or not sample.rules_known
                    or sample.versions.get("forecast_high_f") != "1"
                    or sample.features.get("forecast_high_f") is None
                ):
                    raise ValueError("Incompatible calibration, features or contract semantics")
                market = markets[sample.ticker]
                if (
                    market.strike is None
                    or market.ticker != sample.ticker
                    or market.event_ticker != sample.event_id
                    or market.series_ticker != sample.family
                    or market.close_time != sample.close_time
                    or market.rules.captured_at > sample.decision_time
                    or not market.open_time <= sample.decision_time < market.close_time
                    or market.rules.settlement_basis != "contract_text"
                    or market.rules.settlement_target_date != sample.target_date
                ):
                    raise ValueError("Missing matching frozen contract strike")
                forecast = sample.features["forecast_high_f"]
                assert forecast is not None  # noqa: S101 - checked in compatibility gate
                probability = exact_probability(model.probability(float(forecast), market.strike))
                records.append(
                    ProbabilityRecord(
                        event_id=sample.event_id,
                        ticker=sample.ticker,
                        decision_time=sample.decision_time,
                        family=model.family,
                        model_hash=model.model_hash,
                        feature_hash=sample.feature_hash,
                        feature_version=data.feature_version,
                        fitted_before=model.fitted_before,
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
