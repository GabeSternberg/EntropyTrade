"""Website worker integration over the existing protected research/experiment engines."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from entropytrade.agents.evidence import ResearchEvidence
from entropytrade.api.jobs import Jobs
from entropytrade.api.worker import execute_job
from entropytrade.domain.time import SimulatedClock
from entropytrade.experiments.data import ExperimentData
from entropytrade.families.public import capture_public
from entropytrade.weather.collection import WeatherConfig
from tests.r4_support import nonweather
from tests.unit.test_public_families import WHEN, listing, spot

REPO = Path(__file__).resolve().parents[3]


def test_registered_source_coverage_uses_sample_provenance_not_configured_adapters() -> None:
    data, _, _, _ = nonweather()
    data = data.revalidated(samples=(data.samples[0].revalidated(sources=()), *data.samples[1:]))
    evidence = ResearchEvidence.from_data(
        data,
        holdout_start=date.max,
        model_families=("provided-frequency",),
    )
    permitted = [s for s in data.samples if s.event_id not in data.protected_events]
    assert evidence.coverage["by_series"]["MENTIONS"]["source_counts"] == {
        "fixture-transcript": len(permitted) - 1,
    }


def test_recorded_idea_gets_saved_insufficiency_and_real_lineage(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    job_id = jobs.create({"idea": "Test revision_f > 1", "family": "weather", "mode": "recorded"})
    jobs.update(job_id, "starting", "Worker starting")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert job["status"] == "completed"
    review = job["result"]
    assert review["data_kind"] == "real"
    assert review["reasoning"] == "local_templates"
    assert review["coverage"]["scalar_label_events"] == 0
    assert not review["probabilities"]
    assert not review["final_holdout_evaluated"]
    assert all(
        not c["tested"] and c["forecast_metrics"] is None and not c["scenarios"]
        for c in review["candidates"]
    )
    assert review["lineage"]["dataset"].startswith("sha256:")
    assert review["artifacts"]
    assert review["proposals"][0]["spec"]["entry_rules"]["all_of"][-1]["threshold"] == "1"
    saved = json.loads((tmp_path / "runs" / job_id / "review.json").read_text())
    assert saved == review


def test_synthetic_worker_exposes_only_permitted_validation_probabilities(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    job_id = jobs.create(
        {"idea": "Software verification", "family": "weather", "mode": "synthetic"}
    )
    jobs.update(job_id, "starting", "Worker starting")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert job["status"] == "completed"
    review = job["result"]
    assert review["data_kind"] == "synthetic"
    assert review["reasoning"] == "offline_mock"
    assert review["probabilities"]
    assert len(review["probabilities"]) <= 100
    assert not review["final_holdout_evaluated"]
    used = {p for c in review["candidates"] for p in c.get("prediction_ids", [])}
    assert all(
        p["split"] == "validation" and p["prediction_id"] in used for p in review["probabilities"]
    )
    assert all("outcome" not in p for p in review["probabilities"])
    control = next(c for c in review["candidates"] if c["candidate_id"] == "negative-control")
    assert len(control["scenarios"]) == 3
    assert not any(s["fill_count"] for s in control["scenarios"])


@pytest.mark.parametrize(
    ("case", "status", "receipts", "successful", "contracts", "observations"),
    [
        ("http", "incomplete", 2, 0, 0, 0),
        ("connect", "incomplete", 0, 0, 0, 0),
        ("partial", "incomplete", 3, 2, 2, 0),
        ("complete", "complete", 3, 3, 2, 1),
        ("empty", "empty", 2, 2, 0, 1),
    ],
)
def test_public_worker_reports_acquisition_separately_from_completed_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    status: str,
    receipts: int,
    successful: int,
    contracts: int,
    observations: int,
) -> None:
    """Controlled wire responses prove failure presentation, never empirical ingestion."""

    def wire(request: httpx.Request) -> httpx.Response:
        if case == "connect":
            raise httpx.ConnectError("controlled outage", request=request)
        market = request.url.host == "api.elections.kalshi.com"
        if case == "http" or (case == "partial" and not market):
            return httpx.Response(503, json={"error": "controlled outage"})
        if market:
            if case == "empty":
                return httpx.Response(200, json={"markets": [], "cursor": ""})
            return listing(request)
        return spot(request)

    async def controlled_capture(
        root: Path, *, family: str, weather: WeatherConfig
    ) -> ExperimentData:
        return await capture_public(
            root,
            family=family,
            weather=weather,
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(wire),
            source_transport=httpx.MockTransport(wire),
        )

    monkeypatch.setattr("entropytrade.api.worker.capture_public", controlled_capture)
    jobs = Jobs(tmp_path)
    job_id = jobs.create({"idea": "Research Bitcoin spot", "family": "bitcoin", "mode": "public"})
    jobs.update(job_id, "starting", "Worker starting")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert job["status"] == "completed", job["detail"]
    assert f"public acquisition {status}" in job["detail"]
    review = job["result"]
    acquisition = review["acquisition"]
    assert acquisition["status"] == status
    assert acquisition["receipt_count"] == receipts
    assert acquisition["successful_response_count"] == successful
    assert acquisition["listed_contracts"] == contracts
    assert acquisition["observations"] == observations
    failures = review["public_evidence"]["capture"]["failures"]
    assert acquisition["failure_count"] == len(failures)
    assert len(acquisition["failure_summaries"]) == len(failures)
    for failure, summary in zip(failures, acquisition["failure_summaries"], strict=True):
        assert all(failure[key] in summary for key in ("source", "failure", "failed_at"))
        assert summary in review["report"]
    report = review["report"]
    assert report.startswith(acquisition["headline"])
    assert acquisition["counts"] in report
    assert acquisition["evaluation_limit"] in report
    assert "rules_known is false" in report
    assert "settlement sources remain unresolved" in report
    assert f"HTTP receipts: {receipts} ({successful} successful)" in report
    assert f"listed contracts: {contracts}; observations: {observations}" in report
    assert "history complete: False" in report
    assert not acquisition["history_complete"]
    assert not review["probabilities"]
    assert review["probability_count"] == 0
    assert all(c["forecast_metrics"] is None and not c["scenarios"] for c in review["candidates"])
    assert not review["final_holdout_evaluated"]
    assert all(
        not c["rules_known"] and c["settlement_sources"] == []
        for c in review["public_evidence"]["contracts"]
    )
    assert json.loads((tmp_path / "runs" / job_id / "review.json").read_text()) == review
