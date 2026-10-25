"""Generic engine, future-model refusal, integrity, search accounting and integrated CLI."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence
from entropytrade.domain.enums import FillScenario
from entropytrade.domain.orders import Fill
from entropytrade.domain.portfolio import Settlement
from entropytrade.experiments.data import AdapterRegistry, RecordedPredictions
from entropytrade.experiments.engine import evaluate_candidate, run_experiments
from entropytrade.experiments.workflow import research_and_test
from entropytrade.portfolio.ledger import Ledger
from entropytrade.strategy_registry.store import Registry
from tests.r4_support import START, nonweather


def test_nonweather_family_uses_shared_engine_and_research_projections(tmp_path: Path) -> None:
    data, provider, research, config = nonweather()
    adapters = AdapterRegistry()
    adapters.register("mentions", lambda _: data, provider)
    with pytest.raises(ValueError, match="already registered"):
        adapters.register("mentions", lambda _: data, provider)
    evidence = ResearchEvidence.from_data(
        data, holdout_start=data.samples[70].target_date, model_families=("provided-frequency",)
    )
    assert "mention_count" in evidence.registered_names
    assert "forecast_high_f" not in evidence.registered_names
    result = run_experiments(
        research=research,
        data=data,
        provider=adapters.providers["mentions"],
        config=config,
        registry_path=tmp_path / "registry.sqlite",
        output=tmp_path / "runs",
        tracking=tmp_path / "mlflow",
    )
    first, second = result["candidates"]
    assert first["status"] == "BACKTESTED"
    assert first["forecast_metrics"]["independent_events"] == 20
    assert first["scenarios"][0]["fill_count"] == 20
    assert second["status"] == "UNSUPPORTED"
    assert not result["final_holdout_evaluated"]
    assert all("prediction-7" not in p for p in first["prediction_ids"])
    # Every variant counts, including unsupported proposals; replay is idempotent.
    again = run_experiments(
        research=research,
        data=data,
        provider=provider,
        config=config,
        registry_path=tmp_path / "registry.sqlite",
        output=tmp_path / "runs",
        tracking=tmp_path / "mlflow",
    )
    assert result == again
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        assert registry.experiment_trials("synthetic") == 2
        assert registry.experiment_trials("real") == 0
    finally:
        registry.close()


@pytest.mark.parametrize(
    "fault",
    [
        "future_model",
        "future_calibration",
        "feature_hash",
        "model_version",
        "real_synthetic",
        "unknown_feature",
        "unknown_exit",
        "unlisted_market",
    ],
)
def test_model_and_feature_faults_never_reach_backtesting(fault: str) -> None:
    data, provider, research, config = nonweather()
    candidate = research["candidates"][0]
    if fault == "future_model":
        provider = RecordedPredictions(
            provider.bundle.revalidated(
                records=tuple(
                    p.revalidated(fitted_before=START + timedelta(days=500))
                    for p in provider.bundle.records
                )
            )
        )
    elif fault == "feature_hash":
        provider = RecordedPredictions(
            provider.bundle.revalidated(
                records=tuple(p.revalidated(feature_hash="wrong") for p in provider.bundle.records)
            )
        )
    elif fault == "future_calibration":
        provider = RecordedPredictions(
            provider.bundle.revalidated(
                records=tuple(
                    p.revalidated(calibrated_before=START + timedelta(days=500))
                    for p in provider.bundle.records
                )
            )
        )
    elif fault == "model_version":
        candidate["spec"]["model_ref"] = {
            "family": "provided-frequency",
            "version": "sha256:" + "f" * 64,
        }
    elif fault == "real_synthetic":
        data = data.revalidated(data_kind="real")
    elif fault == "unknown_feature":
        candidate["required_features"] = ["invented_profit_signal"]
    elif fault == "unknown_exit":
        candidate["spec"]["exit_mode"] = "predicate"
        candidate["spec"]["exit_rules"]["all_of"][0]["feature"] = "invented_exit"
    elif fault == "unlisted_market":
        candidate["spec"]["market_universe"]["market_tickers"] = ["invented-contract"]
    result = evaluate_candidate(candidate, research, data, provider, config)
    assert result["status"] == "INVALID"
    assert not result["scenarios"]


def test_missing_required_source_provenance_refuses_execution() -> None:
    data, provider, research, config = nonweather()
    changed = data.revalidated(samples=tuple(s.revalidated(sources=()) for s in data.samples))
    result = evaluate_candidate(research["candidates"][0], research, changed, provider, config)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "source provenance" in result["reasons"][0]
    assert not result["scenarios"]


def test_deterministic_research_rejection_cannot_be_overridden_by_critic() -> None:
    data, provider, research, config = nonweather()
    research["decisions"][0]["status"] = "REJECTED"
    result = evaluate_candidate(research["candidates"][0], research, data, provider, config)
    assert result["status"] == "INVALID"
    assert not result["scenarios"]


def test_registered_nonweather_adapter_runs_through_the_same_workflow(tmp_path: Path) -> None:
    data, provider, research, config = nonweather()
    adapters = AdapterRegistry()
    adapters.register("mentions", lambda _: data, provider)
    evidence_config = tmp_path / "inputs.json"
    evidence_config.write_text(
        EvidenceConfig(
            root=tmp_path,
            features="registered-adapter",
            holdout_start=data.samples[70].target_date,
            model_families=("provided-frequency",),
        ).model_dump_json()
    )
    saved_research = tmp_path / "prior-research.json"
    saved_research.write_text(json.dumps(research))
    result = research_and_test(
        prompt=research["prompt"],
        evidence_config=evidence_config,
        output=tmp_path / "output",
        registry=tmp_path / "registry.sqlite",
        tracking=tmp_path / "mlflow",
        research_run=saved_research,
        adapters=adapters,
        market_family="mentions",
        experiment_config=config,
    )
    assert result["candidates"][0]["status"] == "BACKTESTED"
    assert result["research_artifact"] == str(saved_research)
    assert result["candidates"][0]["forecast_metrics"]["independent_events"] == 20


def test_candles_and_missing_fees_do_not_establish_execution_returns() -> None:
    data, provider, research, config = nonweather()
    thin = data.revalidated(
        samples=tuple(s.revalidated(book=None, fidelity="candle") for s in data.samples)
    )
    result = evaluate_candidate(research["candidates"][0], research, thin, provider, config)
    assert result["forecast_metrics"] is not None
    assert result["status"] == "INSUFFICIENT_DATA"
    assert not result["scenarios"]
    missing = evaluate_candidate(
        research["candidates"][0], research, data, provider, config.revalidated(fee_policy=None)
    )
    assert missing["status"] == "INSUFFICIENT_DATA"
    assert not missing["scenarios"]


def test_future_feature_and_fee_publication_cannot_be_backdated() -> None:
    data, provider, research, config = nonweather()
    with pytest.raises(ValidationError, match="after decision"):
        data.samples[0].revalidated(
            features_available_at=data.samples[0].decision_time + timedelta(seconds=1)
        )
    assert config.fee_policy is not None
    late = config.revalidated(
        fee_policy=config.fee_policy.revalidated(available_at=START + timedelta(days=500))
    )
    assert (
        evaluate_candidate(research["candidates"][0], research, data, provider, late)["status"]
        == "INSUFFICIENT_DATA"
    )


def test_no_request_can_expose_held_out_prediction_outcomes() -> None:
    data, provider, research, config = nonweather()
    changed = RecordedPredictions(
        provider.bundle.revalidated(
            records=tuple(p.revalidated(partition="validation") for p in provider.bundle.records)
        )
    )
    result = evaluate_candidate(research["candidates"][0], research, data, changed, config)
    assert result["forecast_metrics"]["independent_events"] == 20
    assert not any(p.startswith("prediction-7") for p in result["prediction_ids"])


def test_real_workflow_has_only_insufficient_or_unsupported_results(tmp_path: Path) -> None:
    result = research_and_test(
        prompt="Research Philadelphia forecast revisions and data limitations",
        evidence_config=Path("configs/research/weather.json"),
        output=tmp_path / "output",
        registry=tmp_path / "registry.sqlite",
        tracking=tmp_path / "mlflow",
        offline=True,
    )
    assert [r["status"] for r in result["candidates"]] == [
        "INSUFFICIENT_DATA",
        "INSUFFICIENT_DATA",
        "UNSUPPORTED",
    ]
    assert all(r["rank"] is None and not r["scenarios"] for r in result["candidates"])


@pytest.fixture(scope="module")
def synthetic_workflow(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("r4-integration")
    result = research_and_test(
        prompt="Research Philadelphia revisions and model disagreement",
        evidence_config=None,
        output=root / "output",
        registry=root / "registry.sqlite",
        tracking=root / "mlflow",
        synthetic=True,
        offline=True,
        days=240,
    )
    return root, result


def test_synthetic_end_to_end_has_models_fills_rejections_and_artifacts(
    synthetic_workflow: tuple[Path, dict[str, Any]],
) -> None:
    root, result = synthetic_workflow
    assert result["data_kind"] == "synthetic"
    assert len(result["candidates"]) == 4
    assert any(r["tested"] and r["scenarios"] for r in result["candidates"])
    assert result["candidates"][-1]["status"] == "REJECTED"
    assert result["candidates"][2]["status"] == "UNSUPPORTED"
    assert all(r["status"] != "PROMISING_FOR_FURTHER_VALIDATION" for r in result["candidates"])
    assert result["requested_trial_count"] == 12
    assert not result["final_holdout_evaluated"]
    for row in result["candidates"]:
        if row["scenarios"]:
            assert {s["scenario"] for s in row["scenarios"]} == {s.value for s in FillScenario}
            for scenario in row["scenarios"]:
                assert not scenario["unsettled_positions"]
                saved = scenario["ledger"]
                events = [(Fill.model_validate(f).executed_at, 0, f) for f in saved["fills"]]
                events += [
                    (Settlement.model_validate(s).settled_at, 1, s) for s in saved["settlements"]
                ]
                rebuilt = Ledger(
                    Decimal(saved["starting_cash"]), as_of=datetime.fromisoformat(saved["as_of"])
                )
                for _, kind, payload in sorted(events, key=lambda event: (event[0], event[1])):
                    if kind == 0:
                        rebuilt.apply_fill(Fill.model_validate(payload))
                    else:
                        settlement = Settlement.model_validate(payload)
                        rebuilt.settle(
                            settlement.market_ticker, settlement.result, at=settlement.settled_at
                        )
                assert str(rebuilt.cash) == saved["cash"]
                assert str(rebuilt.fees_paid) == scenario["fees_paid"]
                assert rebuilt.equity() - rebuilt.starting_cash == Decimal(scenario["net_pnl"])
    artifact = Path(result["report_path"]).parent
    assert (artifact / "trades.parquet").exists()
    assert pq.read_table(artifact / "trades.parquet").num_rows == sum(
        scenario["fill_count"] for row in result["candidates"] for scenario in row["scenarios"]
    )
    assert list((root / "mlflow").rglob("meta.yaml"))
    original = json.loads(Path(result["research_artifact"]).read_text())
    assert len(original["hypotheses"]) == 4


def test_same_research_replays_reproducibly(
    synthetic_workflow: tuple[Path, dict[str, Any]],
) -> None:
    root, first = synthetic_workflow
    repeated = research_and_test(
        prompt=first["research_run"],
        evidence_config=None,
        output=root / "output",
        registry=root / "registry.sqlite",
        tracking=root / "mlflow",
        synthetic=True,
        offline=True,
        days=240,
        research_run=Path(first["research_artifact"]),
    )
    assert repeated["experiment_id"] == first["experiment_id"]
    assert repeated["candidates"] == first["candidates"]
