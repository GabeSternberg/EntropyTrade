"""Actual persistent C-to-paper collection with entirely controlled synthetic wire data."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.tracking.history import verified_inputs
from entropytrade.tracking.prospective import report
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import execute
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
)
from tests.research_paper_support import paper_fixture
from tests.unit.test_tracking import monitor


@pytest.mark.parametrize("source_status", ["legacy", "complete", "failed"])
def test_worker_records_research_source_failure_as_failed_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_status: str,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)

    async def collected(
        _monitor: dict[str, Any],
        _repo: Path,
        _root: Path,
        *,
        fee_versions: tuple[FeeVersion, ...] = (),
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "detail": "CONTROLLED source collection status",
            "capture": {"failures": []},
            "outcome_failures": [],
        }
        if source_status != "legacy":
            result["research_features"] = {
                "failures": ["CONTROLLED PFM source unavailable"]
                if source_status == "failed"
                else []
            }
        return result

    monkeypatch.setattr("entropytrade.tracking.worker.collect", collected)
    claim = store.claim()
    assert claim is not None
    execute(store, Path(__file__).resolve().parents[3], *claim)
    persisted = store.get(monitor_id)
    assert persisted is not None
    assert persisted["cycles"][0]["status"] == (
        "failed" if source_status == "failed" else "completed"
    )
    assert persisted["failures"] == (1 if source_status == "failed" else 0)


def test_real_worker_collects_exact_features_scores_and_accounts_in_synthetic_paper(
    tmp_path: Path,
) -> None:
    fixture = paper_fixture(tmp_path / "workspace")
    # These are explicit simulated operator/receipt clocks. No actual machine timestamp
    # or historical prediction is relabeled as prospective in production.
    deployed = MODEL_NOW + timedelta(minutes=1)
    with patch("entropytrade.tracking.store.timestamp", return_value=deployed.isoformat()):
        created = fixture.service.create(fixture.job_id, fixture.request)
    when = MODEL_NOW.replace(hour=23, minute=0, second=5)
    result = commit_controlled_cycle(fixture, when)
    assert result["data_kind"] == "synthetic"
    assert result["research_features"]["requests"] > 0
    assert not result["research_features"]["failures"]
    assert not result["model_refusals"]
    # Ten active off-horizon contracts are retained in the public receipt, but cannot
    # consume the bounded book budget ahead of the frozen model's target date.
    assert result["execution"]["book_count"] == 1
    assert len(result["contracts"]) == 1
    assert result["decisions"][0]["prediction"] is not None
    assert set(result["decisions"][0]["features"]) == {"nws_pfm_max_f", "nws_cli_bias_f"}
    assert result["paper"]["summary"]["fill_count"] > 0
    assert not result["submission_enabled"]
    monitor = fixture.tracking.get(created["id"], export=True)
    assert monitor is not None
    cycle = monitor["cycles"][0]
    root = fixture.jobs.root / "shadow" / created["id"] / cycle["id"]
    before = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    with controlled_forward_environment(SimulatedClock(when)):
        original = verified_inputs(root)
        prospective = report(fixture.jobs, created["id"], as_of=when + timedelta(minutes=1))
    assert original == json.loads((root / "decision-inputs.json").read_text())
    assert prospective["cycle_failures"] == []
    assert prospective["status"] == "insufficient"
    assert prospective["counts"]["contracts"] == 1
    assert prospective["observations"][0]["data_kind"] == "synthetic"
    assert prospective["observations"][0]["prediction"] is not None
    assert not prospective["historical_validation"]
    assert prospective["performance"] is None
    assert before == {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "field",
    [
        "market_type",
        "series_ticker",
        "settlement_sources",
        "settlement_basis",
        "settlement_target_date",
    ],
)
def test_official_paper_settlement_refuses_changed_payout_source_or_target(
    tmp_path: Path,
    field: str,
) -> None:
    import asyncio

    import httpx

    from entropytrade.tracking.worker import outcomes
    from tests.exchange.test_gateway_http import _market_body
    from tests.unit.test_public_families import WHEN
    from tests.unit.test_tracking import contract

    original = contract()
    original["market"]["market"]["rules"] = dict(original["market"]["market"]["rules"])
    if field == "market_type":
        original["market"]["market"]["market_type"] = "scalar"
    elif field == "series_ticker":
        original["market"]["market"]["series_ticker"] = "WRONG_SERIES"
    else:
        original["market"]["market"]["rules"][field] = {
            "settlement_sources": [{"name": "NWS"}],
            "settlement_basis": "unresolved",
            "settlement_target_date": "2026-10-04",
        }[field]
    body = _market_body() | {
        "status": "finalized",
        "result": "yes",
        "settlement_value_dollars": "1.0000",
        "settlement_ts": "2026-10-03T06:00:00Z",
    }
    result = asyncio.run(
        outcomes(
            tmp_path / "outcomes",
            [original],
            clock=SimulatedClock(WHEN),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"market": body})),
        )
    )
    assert not result["outcomes"]
    assert result["outcome_failures"][0]["failure"] == "FrozenContractTermsChanged"
