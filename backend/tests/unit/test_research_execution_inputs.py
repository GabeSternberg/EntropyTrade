"""Verified acquired execution records reach the existing replay through causal gates."""

import copy
import json
import shutil
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from entropytrade.data.sources import file_hash
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import temporal_plan
from entropytrade.ml.models import WeatherModel
from entropytrade.research.execution_inputs import acquired_backtest
from entropytrade.research.modeling import _rows, run_hypothesis
from entropytrade.research.registry import FeatureRegistry
from tests.research_execution_support import execution_fixture
from tests.research_modeling_support import MODEL_NOW, modeling_fixture


@pytest.fixture(scope="module")
def executed(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    root = tmp_path_factory.mktemp("acquired-execution")
    spec, artifacts = modeling_fixture(root)
    # Explicit probability candidate: the controlled bias feature is identically zero,
    # so it cannot establish a fitted positive-bias threshold strategy.
    spec = spec.revalidated(rules=())
    identifier, fees = execution_fixture(root, spec, artifacts)
    result = run_hypothesis(
        root=root,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
        execution_datasets=(identifier,),
        fee_versions=fees,
    )
    directory = root / "experiments" / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
    model = WeatherModel.load(
        directory / "forecast_error.joblib",
        expected_hash=result["models"]["forecast_error"]["artifact_hash"],
        trusted=True,
    )
    boundaries = tuple(date.fromisoformat(day) for day in result["boundaries"])
    rows, _ = _rows(root, FeatureRegistry(), spec, artifacts, "synthetic", boundaries[2])
    plan = temporal_plan(rows, (boundaries[0], boundaries[1], boundaries[2]))
    return (
        root,
        result,
        {
            "root": root,
            "registry": FeatureRegistry(),
            "spec": spec,
            "rows": rows,
            "model": model,
            "model_hash": result["models"]["forecast_error"]["artifact_hash"],
            "plan": plan,
            "execution_datasets": (identifier,),
            "fee_versions": fees,
            "data_kind": "synthetic",
            "asof": MODEL_NOW,
        },
    )


def rewrite_dataset(
    root: Path, identifier: str, change: Callable[[list[dict[str, Any]]], None]
) -> str:
    source = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
    staging = root / ".changed-execution"
    shutil.copytree(source, staging)
    rows = [json.loads(line) for line in (staging / "records.jsonl").read_text().splitlines()]
    change(rows)
    (staging / "records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )
    manifest = json.loads((staging / "manifest.json").read_text())
    manifest["checksums"] = {
        name: file_hash(staging / name)
        for name in ("records.jsonl", "receipts.jsonl", "parameters.json")
    }
    identifier = scientific_hash(manifest["checksums"])
    manifest["dataset_id"] = identifier
    (staging / "manifest.json").write_text(json.dumps(manifest))
    target = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
    staging.rename(target)
    return identifier


def test_acquired_features_and_typed_evidence_run_existing_engine(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    _, result, _ = executed
    assert result["status"] == "evaluated"
    backtest = result["backtest"]
    assert backtest["eligible"]
    assert backtest["execution_fidelity"] == "order_book_simulation"
    assert backtest["performance"]["tested"]
    scenarios = {s["scenario"]: s for s in backtest["performance"]["scenarios"]}
    assert scenarios["base"]["fill_count"] == 43
    assert scenarios["conservative"]["fill_count"] == 0
    assert backtest["performance"]["forecast_metrics"]["independent_events"] == 43
    assert not backtest["submission_enabled"]
    assert not backtest["paper_eligible"]
    assert backtest["prospective_validation"] == "pending_genuine_forward_observations"
    assert not result["validation"]["holdout_evaluated"]
    assert not result["validation"]["prospective"]


@pytest.mark.parametrize(
    "fault", ["final_target", "final_basis", "final_outcome", "receipt_clock", "future_final"]
)
def test_invalid_semantics_or_clock_never_produces_execution(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    root, _, kwargs = executed

    def change(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            market = row.get("market")
            if not market or market["status"] != "finalized":
                continue
            if fault == "final_target":
                market["rules"]["settlement_target_date"] = "2026-12-31"
            elif fault == "final_basis":
                market["rules"]["settlement_basis"] = "unresolved"
            elif fault == "final_outcome":
                market["result"] = "no" if market["result"] == "yes" else "yes"
            elif fault == "future_final":
                market["rules"]["captured_at"] = (MODEL_NOW + timedelta(days=1)).isoformat()
            else:
                market["rules"]["captured_at"] = "2020-01-01T00:00:00+00:00"

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    with pytest.raises(ValueError, match=r"mismatch|disagree|availability|future"):
        acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))


@pytest.mark.parametrize(
    "fault", ["missing_book", "outer_late", "payload_late", "missing_fees", "scalar"]
)
def test_missing_or_late_evidence_stays_predictive_only(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    root, _, kwargs = executed

    def change(rows: list[dict[str, Any]]) -> None:
        if fault == "missing_book":
            rows[:] = [row for row in rows if row["record_type"] != "market_state"]
        for row in rows:
            if fault == "scalar" and row["record_type"] == "market_evidence":
                row["market"]["market_type"] = "scalar"
            if row["record_type"] != "market_state":
                continue
            if fault == "outer_late":
                from datetime import datetime

                later = (
                    datetime.fromisoformat(row["available_at"]) + timedelta(seconds=1)
                ).isoformat()
                row.update(available_at=later, received_at=later)
            elif fault == "payload_late":
                from datetime import datetime

                row["payload"]["received_at"] = (
                    datetime.fromisoformat(row["available_at"]) + timedelta(seconds=1)
                ).isoformat()

    inputs = (
        kwargs | {"fee_versions": ()}
        if fault == "missing_fees"
        else kwargs
        | {"execution_datasets": (rewrite_dataset(root, kwargs["execution_datasets"][0], change),)}
    )
    result = acquired_backtest(**inputs)
    assert not result["eligible"]
    assert result["execution_fidelity"] == "predictive_only"
    assert result["reasons"]
    assert result["performance"] is None or not result["performance"]["scenarios"]


def test_protected_outcomes_are_not_deserialized_or_scored(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, result, kwargs = executed
    protected = {event.rsplit(":", 1)[-1] for event in kwargs["plan"].holdout}

    def change(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            market = row.get("market")
            if not market or market["rules"]["settlement_target_date"] not in protected:
                continue
            if market["status"] == "finalized":
                market["result"] = "INTENTIONALLY_UNREAD_PROTECTED_OUTCOME"

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    changed = acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))
    assert (
        changed["performance"]["forecast_metrics"]
        == result["models"]["forecast_error"]["backtest"]["performance"]["forecast_metrics"]
    )
    assert (
        changed["performance"]["prediction_ids"]
        == result["models"]["forecast_error"]["backtest"]["performance"]["prediction_ids"]
    )


@pytest.mark.parametrize("fault", ["final", "initial", "book"])
def test_conflicting_snapshots_at_one_clock_fail_closed(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
    fault: str,
) -> None:
    root, _, kwargs = executed

    def change(rows: list[dict[str, Any]]) -> None:
        extra = []
        for row in rows:
            copied = copy.deepcopy(row)
            if fault == "book" and row["record_type"] == "market_state":
                copied["payload"]["asks"][0]["quantity"] = "4"
                extra.append(copied)
            elif row["record_type"] == "market_evidence":
                if fault == "final" and row["market"]["status"] == "finalized":
                    copied["market"]["result"] = "no" if row["market"]["result"] == "yes" else "yes"
                    extra.append(copied)
                elif fault == "initial" and row["market"]["status"] == "active":
                    copied["market"]["strike"]["floor"] = "99"
                    extra.append(copied)
        rows.extend(extra)

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    with pytest.raises(ValueError, match="conflicting"):
        acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))


def test_missing_actual_protected_identity_refuses_temporal_cutoff(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, _, kwargs = executed
    protected_dates = {event.rsplit(":", 1)[-1] for event in kwargs["plan"].holdout}

    def change(rows: list[dict[str, Any]]) -> None:
        rows[:] = [
            row
            for row in rows
            if not (
                row["record_type"] == "market_evidence"
                and row["market"]["rules"]["settlement_target_date"] in protected_dates
            )
        ]

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    result = acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))
    assert not result["eligible"]
    assert "protected contract identity" in result["reasons"][0]
    assert result["performance"] is None


def test_minimal_source_protected_identities_preserve_cutoff_without_outcomes(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, original, kwargs = executed
    protected_dates = {event.rsplit(":", 1)[-1] for event in kwargs["plan"].holdout}

    def change(rows: list[dict[str, Any]]) -> None:
        changed = []
        for row in rows:
            market = row.get("market")
            if not market or market["rules"]["settlement_target_date"] not in protected_dates:
                changed.append(row)
            elif market["status"] == "active":
                changed.append(
                    {
                        "record_type": "protected_identity",
                        "ticker": market["ticker"],
                        "series": market["series_ticker"],
                        "target_date": market["rules"]["settlement_target_date"],
                        "close_time": market["close_time"],
                        "raw_hash": row["raw_hash"],
                        "raw_ref": row["raw_ref"],
                    }
                )
        rows[:] = changed

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    result = acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))
    assert result["execution_input_provenance"]["protected_identity_shells"] == len(
        kwargs["plan"].holdout
    )
    assert (
        result["performance"]["forecast_metrics"]
        == original["backtest"]["performance"]["forecast_metrics"]
    )
    assert result["performance"]["scenarios"][1]["fill_count"] == 43


def test_delayed_publication_keeps_trade_exposure_and_unresolved_status(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, original, kwargs = executed
    selected_day = kwargs["plan"].validation[0].rsplit(":", 1)[-1]
    heldout_day = kwargs["plan"].holdout[0].rsplit(":", 1)[-1]

    def change(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            market = row.get("market")
            if (
                market
                and market["status"] == "finalized"
                and market["rules"]["settlement_target_date"] == selected_day
            ):
                market["rules"]["captured_at"] = heldout_day + "T15:00:00+00:00"

    identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
    delayed = acquired_backtest(**(kwargs | {"execution_datasets": (identifier,)}))
    assert delayed["performance"]["status"] == "INSUFFICIENT_DATA"
    assert not delayed["eligible"]
    assert delayed["executed"]
    assert delayed["execution_fidelity"] == "order_book_simulation"
    assert "unresolved" in delayed["reasons"][0]
    base = delayed["performance"]["scenarios"][1]
    assert base["fill_count"] == original["backtest"]["performance"]["scenarios"][1]["fill_count"]
    assert base["unsettled_positions"] == 1


@pytest.mark.parametrize("missing", ["official_final", "scalar_label"])
def test_missing_outcome_never_selects_profitable_subset(
    executed: tuple[Path, dict[str, Any], dict[str, Any]],
    missing: str,
) -> None:
    root, _, kwargs = executed
    selected_day = kwargs["plan"].validation[0].rsplit(":", 1)[-1]

    def change(rows: list[dict[str, Any]]) -> None:
        rows[:] = [
            row
            for row in rows
            if not (
                row["record_type"] == "market_evidence"
                and row["market"]["status"] == "finalized"
                and row["market"]["rules"]["settlement_target_date"] == selected_day
            )
        ]

    if missing == "official_final":
        identifier = rewrite_dataset(root, kwargs["execution_datasets"][0], change)
        inputs = kwargs | {"execution_datasets": (identifier,)}
    else:
        rows = copy.deepcopy(kwargs["rows"])
        row = next(row for row in rows if row["target_date"] == selected_day)
        row.update(target=None, label_available_at=None, complete=False)
        inputs = kwargs | {"rows": rows}
    result = acquired_backtest(**inputs)
    assert not result["eligible"]
    assert result["performance"] is None
    assert "entire decision-eligible universe" in result["reasons"][0]
