"""One prompt-to-experiments workflow. Real evidence and synthetic verification stay distinct."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from entropytrade.agents.evidence import (
    EvidenceConfig,
    EvidenceQuery,
    ResearchEvidence,
    previous_research,
)
from entropytrade.agents.pipeline import run_research
from entropytrade.agents.provider import ResearchProviderConfig
from entropytrade.experiments.data import (
    AdapterRegistry,
    PredictionProvider,
    WeatherPredictions,
    weather_data,
)
from entropytrade.experiments.engine import ExperimentConfig, run_experiments
from entropytrade.experiments.synthetic import integration_models, prepare_synthetic, synthetic_fees
from entropytrade.ml.evaluation import temporal_plan


def research_and_test(
    *,
    prompt: str,
    evidence_config: Path | None,
    output: Path,
    registry: Path,
    tracking: Path,
    provider: ResearchProviderConfig | None = None,
    offline: bool = False,
    enable_provider: bool = False,
    synthetic: bool = False,
    days: int = 240,
    experiment_config: ExperimentConfig | None = None,
    research_run: Path | None = None,
    adapters: AdapterRegistry | None = None,
    market_family: str = "weather",
    progress: Callable[[str, str], None] | None = None,
    local_templates: bool = False,
) -> dict[str, Any]:
    def emit(stage: str, detail: str) -> None:
        if progress is not None:
            progress(stage, detail)

    output.mkdir(parents=True, exist_ok=True)
    emit("data", "Preparing versioned inputs and protected event boundaries")
    if not offline and not enable_provider and research_run is None:
        raise ValueError("real research requires explicit provider opt-in; no mock fallback")
    predictor: PredictionProvider
    if adapters is not None:
        if synthetic or evidence_config is None:
            raise ValueError(
                "registered adapters require a configuration and their own data fixture"
            )
        config = EvidenceConfig.model_validate_json(evidence_config.read_text())
        if market_family not in adapters.data_loaders:
            raise ValueError("unregistered market family")
        data = adapters.data_loaders[market_family](config.root / config.features)
        predictor = adapters.providers[market_family]
        config_experiment = experiment_config or ExperimentConfig()
    elif market_family != "weather":
        raise ValueError("non-weather families require an explicitly registered adapter")
    elif synthetic:
        emit("modeling", "Fitting synthetic weather models; software demonstration only")
        features = prepare_synthetic(output / "inputs", days=days)
        data = weather_data(features)
        predictor = WeatherPredictions(
            features, output / "models", registry, tracking / "models", data_kind="synthetic"
        )
        # Fit once for the research tools; candidates can select other calibration regimes later.
        from entropytrade.agents.fixture import demo_specs

        bundle = predictor.prepare(demo_specs()[0], "ridge")
        model_run = (
            output
            / "models"
            / bundle.model_metadata["model_run"].removeprefix("sha256:")
            / "results.json"
        )
        plan = temporal_plan(
            [
                {
                    "event_id": s.event_id,
                    "target_date": s.target_date.isoformat(),
                    "decision_time": s.decision_time.isoformat(),
                }
                for s in data.samples
            ]
        )
        boundary = min(s.target_date for s in data.samples if s.event_id in plan.holdout)
        config = EvidenceConfig(
            root=output.resolve(),
            features=features.resolve().relative_to(output.resolve()).as_posix(),
            model_results=model_run.resolve().relative_to(output.resolve()).as_posix(),
            holdout_start=boundary,
        )
        (output / "research-inputs.json").write_text(config.model_dump_json(indent=2))
        config_experiment = experiment_config or ExperimentConfig(fee_policy=synthetic_fees())
    else:
        if evidence_config is None:
            raise ValueError("real-data experiments require an evidence configuration")
        config = EvidenceConfig.model_validate_json(evidence_config.read_text())
        features = config.root / config.features
        data = weather_data(features)
        predictor = WeatherPredictions(
            features, output / "models", registry, tracking / "models", data_kind=data.data_kind
        )
        config_experiment = experiment_config or ExperimentConfig()
    try:
        proposed = temporal_plan(
            [
                {
                    "event_id": s.event_id,
                    "target_date": s.target_date.isoformat(),
                    "decision_time": s.decision_time.isoformat(),
                }
                for s in data.samples
            ]
        )
    except ValueError:
        proposed = None
    if proposed and adapters is None:
        boundary = min(s.target_date for s in data.samples if s.event_id in proposed.holdout)
        config = config.revalidated(holdout_start=min(config.holdout_start, boundary))
    # The same fixed policy protects both the agent projections and deterministic engine.
    protected = data.protected_events | frozenset(
        s.event_id for s in data.samples if s.target_date >= config.holdout_start
    )
    if config.model_results and adapters is None:
        model_result = json.loads((config.root / config.model_results).read_text())
        protected |= frozenset((model_result.get("split") or {}).get("holdout", []))
    data = data.revalidated(protected_events=protected)
    if isinstance(predictor, WeatherPredictions):
        predictor.protected_events = protected
    evidence = (
        ResearchEvidence(config, history=previous_research(registry))
        if adapters is None
        else ResearchEvidence.from_data(
            data,
            holdout_start=config.holdout_start,
            model_families=config.model_families,
            history=previous_research(registry),
        )
    )
    if research_run:
        research = json.loads(research_run.read_text())
    else:
        models = None
        run_id = None
        if adapters is not None and offline and not local_templates:
            from uuid import uuid4

            from entropytrade.agents.adapter_fixture import adapter_models

            run_id = str(uuid4())
            for topic in ("coverage", "markets", "features", "models", "history"):
                evidence.inspect(EvidenceQuery.model_validate({"topic": topic, "limit": 1}))
            models = adapter_models(evidence, run_id)
        if synthetic and offline and not local_templates:
            from uuid import uuid4

            run_id = str(uuid4())
            for topic in ("coverage", "markets", "features", "models", "history"):
                evidence.inspect(EvidenceQuery.model_validate({"topic": topic, "limit": 1}))
            models = integration_models(prompt, evidence, run_id)
        emit("research", "Formulating typed hypotheses, specifications and independent criticism")
        research = asyncio.run(
            run_research(
                prompt=prompt,
                evidence=evidence,
                provider=provider,
                registry_path=registry,
                output=output / "research",
                offline=offline,
                enable_provider=enable_provider,
                models=models,
                run_id=run_id,
                local_templates=local_templates,
            )
        )
    if research["status"] != "completed":
        return {
            "status": "RESEARCH_FAILED",
            "research_run": research["run_id"],
            "report": research["report"],
        }
    if research["coverage"]["feature_version"] != data.feature_version:
        raise ValueError("research and experiment feature manifests differ")
    emit("experiments", "Running protected model, execution, fee and minimum-evidence gates")
    result = run_experiments(
        research=research,
        data=data,
        provider=predictor,
        config=config_experiment,
        registry_path=registry,
        output=output / "experiments",
        tracking=tracking / "experiments",
    )
    directory = output / "experiments" / result["experiment_id"].removeprefix("sha256:")
    return {
        **result,
        "report_path": str(directory / "report.md"),
        "research_artifact": str(
            research_run or output / "research" / research["run_id"] / "run.json"
        ),
    }
