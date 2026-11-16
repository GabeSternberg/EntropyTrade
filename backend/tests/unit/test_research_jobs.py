"""Milestone A: durable research jobs, hypotheses, requirements and inventory.

No socket is opened. Provider calls are replaced by an injected proposer, exactly where the
isolated worker process would return its result document.
"""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.research.hypotheses import HypothesisProposalBatch
from entropytrade.research.inventory import assess
from entropytrade.research.model import (
    AssessmentStatus,
    DataKind,
    DataRequirement,
    DatasetRecord,
    HypothesisStatus,
    JobStatus,
    ResearchRequest,
    check_transition,
)
from entropytrade.research.registry import FeatureRegistry
from entropytrade.research.service import ResearchService
from tests.unit.test_workbench_http import exchange

if TYPE_CHECKING:
    from entropytrade.api.server import WorkbenchServer

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 15, 15, 0, tzinfo=UTC)
OBJECTIVE = (
    "Find profitable strategies for Kalshi daily temperature markets using weather forecasts."
)
BASE: dict[str, Any] = {"objective": OBJECTIVE, "family": "weather", "acquisition": "none"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never reach a real source; acquisition uses replayed responses."""

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("unit test attempted a real network request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


def service(tmp_path: Path, proposer: Any = None) -> ResearchService:
    return ResearchService(
        tmp_path / "workspace", REPO, clock=SimulatedClock(NOW), proposer=proposer
    )


def submit(svc: ResearchService, **extra: Any) -> str:
    # Milestone A behavior is inventory only; acquisition is tested with replayed responses.
    return str(svc.submit(BASE | extra)["id"])


def test_request_creates_persistent_hypotheses_and_machine_readable_requirements(
    tmp_path: Path,
) -> None:
    svc = service(tmp_path)
    job_id = submit(svc)
    assert svc.store.get_job(job_id)["status"] == JobStatus.QUEUED  # type: ignore[index]
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    # Inventory only: collector-covered evidence is awaited, nothing is downloaded.
    assert job["status"] == JobStatus.AWAITING_OBSERVATIONS
    assert job["acquisitions"] == []
    assert job["universe"] == ["KXHIGHPHIL"]  # defaulted, and recorded
    hypotheses = job["hypotheses"]
    assert len(hypotheses) == 5
    assert all(h["spec"]["claims_edge"] is False for h in hypotheses)
    assert {h["spec"]["provenance"]["generator"] for h in hypotheses} == {"local_templates"}
    # The forecast objective ranks the forecast-bias template first.
    assert hypotheses[0]["spec"]["provenance"]["template_id"] == "weather-forecast-bias"
    requirements = job["requirements"]
    kinds = {(r["kind"], r["entity"], r["variable"], r["clock"]) for r in requirements}
    assert ("forecast_vintages", "CLIPHL", "daytime_max_f", "issuance") in kinds
    assert ("settlement_labels", "CLIPHL", "daily_high_f", "receipt") in kinds
    assert ("decision_quotes", "KXHIGHPHIL", "yes_quotes", "receipt") in kinds
    assert all(r["assessment"] is not None for r in requirements)
    # Requirements are typed and reload as models.
    reloaded = svc.store.requirements(job_id)
    assert all(isinstance(r, DataRequirement) for r in reloaded)
    window_end = NOW.date() - timedelta(days=2)
    assert {r.end for r in reloaded} == {window_end}
    # Forecast bias needs quotes only to execute; revision momentum needs them to test.
    quotes = next(r for r in reloaded if r.kind is DataKind.DECISION_QUOTES)
    bias, momentum = (
        hypotheses[0]["hypothesis_id"],
        next(
            h["hypothesis_id"]
            for h in hypotheses
            if h["spec"]["provenance"]["template_id"] == "weather-revision-momentum"
        ),
    )
    assert quotes.blocking_for(bias) == "execution"
    assert quotes.blocking_for(momentum) == "predictive"
    for row in hypotheses:
        assert row["status"] in {
            HypothesisStatus.NEEDS_DATA,
            HypothesisStatus.AWAITING_AUTHORIZATION,
        }
        assert row["reasons"]
    states = {(r["kind"], r["variable"]): r["assessment"]["status"] for r in requirements}
    assert states[("forecast_vintages", "daytime_max_f")] == AssessmentStatus.MISSING
    assert states[("decision_quotes", "yes_quotes")] == AssessmentStatus.AWAITING_OBSERVATIONS
    assert states[("fee_schedule", "fee_schedule")] == AssessmentStatus.AWAITING_AUTHORIZATION
    # A fresh service on the same workspace sees the same durable state.
    again = service(tmp_path).detail(job_id)
    assert again is not None
    assert [h["hypothesis_id"] for h in again["hypotheses"]] == [
        h["hypothesis_id"] for h in hypotheses
    ]
    report = svc.report(job_id)
    assert report is not None
    assert report["report_hash"].startswith("sha256:")
    assert "nws_pfm_max_f" in report["feature_definitions"]


def test_equivalent_unfinished_request_is_idempotent_and_search_history_is_kept(
    tmp_path: Path,
) -> None:
    svc = service(tmp_path)
    first = svc.submit(BASE)
    second = svc.submit(BASE)
    assert first["id"] == second["id"]
    assert second["created"] is False
    svc.run_until_idle()
    other = submit(svc, validation_depth="quick")
    svc.run_until_idle()
    rows = svc.store.hypotheses(other)
    assert all(r["searches"] == 2 for r in rows)
    assert all("Previously searched" in r["reasons"][0] or r["reasons"] for r in rows)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ({"objective": OBJECTIVE, "family": "astrology"}, "unknown research family"),
        ({"objective": OBJECTIVE, "family": "weather", "universe": ["kxhigh"]}, "series"),
        (
            {"objective": OBJECTIVE, "family": "weather", "universe": ["KXHIGHMIA"]},
            "unsupported series",
        ),
        (
            {
                "objective": OBJECTIVE,
                "family": "weather",
                "provider": {"provider": "anthropic", "model_name": ""},
            },
            "model name",
        ),
        (
            {
                "objective": OBJECTIVE,
                "family": "weather",
                "provider": {"provider": "local_templates", "model_name": "x"},
            },
            "do not use a model",
        ),
        ({"objective": "short", "family": "weather"}, "at least 10"),
        ({"objective": OBJECTIVE, "family": "weather", "api_key": "x"}, "Extra inputs"),
    ],
)
def test_requests_are_validated(tmp_path: Path, value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        service(tmp_path).submit(value)


def test_named_cities_select_the_universe(tmp_path: Path) -> None:
    svc = service(tmp_path)
    job_id = str(
        svc.submit(BASE | {"objective": "Temperature markets in Chicago and Dallas please"})["id"]
    )
    assert svc.store.get_job(job_id)["universe"] == ["KXHIGHCHI", "KXHIGHTDAL"]  # type: ignore[index]


def test_state_machine_and_deployment_statuses_are_enforced(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot move"):
        check_transition(JobStatus.QUEUED, JobStatus.EVALUATED)
    with pytest.raises(ValueError, match="cannot move"):
        check_transition(JobStatus.EVALUATED, JobStatus.ACQUIRING)
    svc = service(tmp_path)
    job_id = submit(svc)
    svc.run_until_idle()
    hypothesis = svc.store.hypotheses(job_id)[0]["hypothesis_id"]
    for forbidden in (
        HypothesisStatus.PAPER_ACTIVE,
        HypothesisStatus.LIVE_ACTIVE,
        HypothesisStatus.LIVE_REQUESTED,
        HypothesisStatus.HISTORICALLY_PROMISING,
    ):
        with pytest.raises(ValueError, match="cannot set"):
            svc.store.set_hypothesis_status(job_id, hypothesis, forbidden, [], {}, now=NOW)
    assert svc.cancel(job_id)
    assert not svc.cancel(job_id)  # terminal: no further transitions
    with pytest.raises(ValueError, match="resumed"):
        svc.resume(job_id)


def test_reevaluation_and_restart_resume_from_checkpoint(tmp_path: Path) -> None:
    svc = service(tmp_path)
    job_id = submit(svc)
    svc.step()  # queued -> generating
    assert svc.store.get_job(job_id)["status"] == JobStatus.GENERATING  # type: ignore[index]
    # Simulated restart: a new service resumes the idempotent generating step.
    restarted = service(tmp_path)
    restarted.recover()
    restarted.run_until_idle()
    job = restarted.detail(job_id)
    assert job is not None
    assert job["status"] == JobStatus.AWAITING_OBSERVATIONS
    assert any(e["stage"] == "recovered" for e in job["events"])
    assert restarted.resume(job_id)
    restarted.run_until_idle()
    stages = [e["stage"] for e in restarted.store.events(job_id)]
    assert stages.count("awaiting_observations") == 2
    assert len(restarted.store.hypotheses(job_id)) == 5  # never duplicated by reevaluation


def requirement(**changes: Any) -> DataRequirement:
    base: dict[str, Any] = {
        "requirement_id": "r-test",
        "kind": DataKind.FORECAST_VINTAGES,
        "family": "weather",
        "entity": "CLIPHL",
        "series": "KXHIGHPHIL",
        "variable": "daytime_max_f",
        "start": date(2026, 10, 1),
        "end": date(2026, 10, 10),
        "clock": "issuance",
        "min_events": 3,
        "blocking": "predictive",
        "purpose": "test requirement purpose",
    }
    return DataRequirement.model_validate({**base, **changes})


def record(**changes: Any) -> DatasetRecord:
    base: dict[str, Any] = {
        "record_id": "d#1",
        "dataset_id": "d",
        "origin": "research_acquisition",
        "data_kind": "authentic",
        "kind": DataKind.FORECAST_VINTAGES,
        "variable": "daytime_max_f",
        "family": "weather",
        "source_id": "iem-nws-pfm",
        "clock": "issuance",
        "coverage": {"CLIPHL": ("2026-10-01", "2026-10-02", "2026-10-03", "2026-12-01")},
    }
    return DatasetRecord.model_validate({**base, **changes})


def test_historical_values_without_the_required_clock_do_not_count() -> None:
    need = requirement()
    assert assess(need, [record()], NOW).status is AssessmentStatus.SATISFIED
    receipt_only = assess(need, [record(clock="receipt")], NOW)
    assert receipt_only.status is AssessmentStatus.MISSING
    assert any("only receipt clocks" in r for r in receipt_only.reasons)
    unknown = assess(requirement(clock="receipt"), [record(clock="unknown")], NOW)
    assert unknown.status is AssessmentStatus.MISSING
    synthetic = assess(need, [record(data_kind="synthetic")], NOW)
    assert synthetic.status is AssessmentStatus.MISSING
    assert any("cannot support real research" in r for r in synthetic.reasons)
    remote = assess(need, [record(origin="collector_status")], NOW)
    assert remote.status is AssessmentStatus.MISSING
    assert any("collector host" in r for r in remote.reasons)
    partial = assess(requirement(min_events=10), [record()], NOW)
    assert partial.status is AssessmentStatus.PARTIAL
    assert partial.events_available == 3
    assert any("outside the window" in r for r in partial.reasons)
    two = requirement(min_sources=2, min_events=1)
    assert assess(two, [record()], NOW).status is AssessmentStatus.MISSING
    both = assess(two, [record(), record(record_id="e#1", dataset_id="e", source_id="b")], NOW)
    assert both.status is AssessmentStatus.SATISFIED


def test_registry_resolution_never_maps_unknown_names() -> None:
    registry = FeatureRegistry()
    assert registry.resolve("nws_pfm_max_f").via == "exact"
    alias = registry.resolve("forecast_revision_f")
    assert (alias.via, alias.feature_id) == ("alias", "revision_f")
    unknown = registry.resolve("secret_model_probability")
    assert (unknown.via, unknown.feature_id) == ("unregistered", None)
    hashes = {d.definition_hash for d in registry.definitions.values()}
    assert len(hashes) == len(registry.definitions)


def proposal(name: str, *, title: str, kinds: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "title": title,
        "rationale": f"Testable mechanism about {title.lower()} for daily highs.",
        "features": [{"name": name, "data_kinds": list(kinds)}],
        "label": "settlement_high_f",
        "rules": [{"feature": name, "op": ">", "threshold": None, "side": "yes"}],
        "candidate_models": ["logistic", "invented_superlearner"],
        "validation_plan": "Time-ordered partitions with an embargo.",
        "leakage_risks": ["Same-day reports"],
        "invalidation": ["No Brier improvement"],
        "proposed_sources": ["https://example.invalid/secret-archive"],
    }


def test_provider_proposals_are_typed_validated_and_metered(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def proposer(
        job_id: str, attempt: int, provider: str, context: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        calls.append({"job": job_id, "attempt": attempt, "provider": provider, "context": context})
        batch = {
            "hypotheses": [
                proposal("nws_pfm_max_f", title="Registered forecast signal"),
                proposal("nws_pfm_max_f", title="Registered forecast signal"),
                proposal(
                    "dew_point_spread_f",
                    title="Unregistered dew point signal",
                    kinds=("forecast_vintages",),
                ),
            ]
        }
        HypothesisProposalBatch.model_validate(batch)
        return {
            "status": "completed",
            "proposals": batch,
            "prompt_hash": "sha256:" + "0" * 64,
            "usage": {"requests": 2, "input_tokens": 1200, "output_tokens": 800},
            "cost_usd": "0.0123",
        }

    svc = service(tmp_path, proposer)
    job_id = submit(svc, provider={"provider": "anthropic", "model_name": "claude-haiku-5-5"})
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    assert calls[0]["provider"] == "anthropic"
    assert "registered_features" in calls[0]["context"]
    assert "api_key" not in json.dumps(calls[0]["context"]).casefold()
    assert job["usage"]["ai_usd"] == "0.0123"
    assert job["usage"]["input_tokens"] == 1200
    statuses = {h["spec"]["title"]: h["status"] for h in job["hypotheses"]}
    assert list(statuses.values()).count(HypothesisStatus.DUPLICATE) == 1
    unsupported = next(h for h in job["hypotheses"] if "dew point" in h["spec"]["title"])
    assert unsupported["status"] == HypothesisStatus.UNSUPPORTED
    assert unsupported["facets"]["unregistered_features"] == ["dew_point_spread_f"]
    # Its declared data need was still recorded, keyed to its own variable name.
    assert any(
        r["variable"] == "dew_point_spread_f" and r["kind"] == "forecast_vintages"
        for r in job["requirements"]
    )
    registered = next(
        h for h in job["hypotheses"] if h["status"] != "duplicate" and h is not unsupported
    )
    assert registered["spec"]["candidate_models"] == ["logistic"]  # invented model dropped
    assert registered["spec"]["provenance"]["model_name"] == "claude-haiku-5-5"


def test_provider_failures_retry_only_when_transient(tmp_path: Path) -> None:
    outcomes = iter(
        [
            {
                "status": "failed",
                "failure": {"type": "ModelHTTPError", "transient": True, "reason": "rate limited"},
            },
            {
                "status": "failed",
                "failure": {"type": "ModelHTTPError", "transient": False, "reason": "rejected key"},
            },
        ]
    )
    clock = SimulatedClock(NOW)
    svc = ResearchService(
        tmp_path / "workspace", REPO, clock=clock, proposer=lambda *_, **__: next(outcomes)
    )
    job_id = submit(svc, provider={"provider": "gemini", "model_name": "gemini-3.5-flash-lite"})
    svc.run_until_idle()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.RECOVERABLE_ERROR
    assert job["error"]["reason"] == "rate limited"
    assert svc.store.runnable(NOW) is None  # backoff scheduled, not hot-looping
    clock.advance(timedelta(minutes=5))
    svc.run_until_idle()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.FAILED
    assert job["error"]["reason"] == "rejected key"
    assert svc.store.hypotheses(job_id) == []  # nothing fabricated


def test_provider_jobs_require_a_budget(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive AI budget"):
        service(tmp_path).submit(
            {
                "objective": OBJECTIVE,
                "family": "weather",
                "provider": {"provider": "gemini", "model_name": "gemini-3.5-flash-lite"},
                "budget": {"ai_usd": "0"},
            }
        )


def test_request_schema_rejects_credentials_and_bad_budgets() -> None:
    with pytest.raises(ValueError, match="less than or equal"):
        ResearchRequest.model_validate(
            {"objective": OBJECTIVE, "family": "weather", "budget": {"ai_usd": "50"}}
        )


def test_research_http_boundary(tmp_path: Path) -> None:
    server = cast(
        "WorkbenchServer",
        SimpleNamespace(
            repo=REPO,
            server_port=43128,
            token=str(uuid4()),
            research=service(tmp_path),
        ),
    )
    status, _, body = exchange(server, "/api/research")
    catalog = json.loads(body)
    assert status == 200
    assert catalog["submission_enabled"] is False
    assert {p["provider"] for p in catalog["providers"]} >= {"local_templates", "gemini"}
    assert all("key" not in json.dumps(p).casefold() or p["requires"] for p in catalog["providers"])
    request = BASE
    status, _, _ = exchange(server, "/api/research/jobs", method="POST", body=request)
    assert status == 403  # missing CSRF token
    headers = {"X-EntropyTrade-CSRF": server.token}
    status, _, body = exchange(
        server, "/api/research/jobs", method="POST", body=request, headers=headers
    )
    assert status == 202
    job_id = json.loads(body)["id"]
    server.research.run_until_idle()
    status, _, body = exchange(server, f"/api/research/jobs/{job_id}")
    assert status == 200
    assert json.loads(body)["status"] == "awaiting_observations"
    status, _, body = exchange(server, f"/api/research/jobs/{job_id}/report")
    assert status == 200
    assert json.loads(body)["schema"] == "entropytrade-research-report-v1"
    status, _, body = exchange(server, "/api/research/jobs")
    assert sum(json.loads(body)["jobs"][0]["hypothesis_counts"].values()) == 5
    status, _, _ = exchange(server, "/api/research/jobs/not-a-uuid")
    assert status == 404
    status, _, body = exchange(
        server, f"/api/research/jobs/{job_id}/resume", method="POST", body={}, headers=headers
    )
    assert (status, json.loads(body)["changed"]) == (200, True)
    status, _, body = exchange(
        server, f"/api/research/jobs/{job_id}/cancel", method="POST", body={}, headers=headers
    )
    assert (status, json.loads(body)["changed"]) == (200, True)
    status, _, body = exchange(
        server,
        "/api/research/jobs",
        method="POST",
        body={**request, "family": "unknown"},
        headers=headers,
    )
    assert status == 400
    status, _, body = exchange(server, "/api/research/inventory")
    assert status == 200
    assert "records" in json.loads(body)


def test_research_state_survives_snapshot_and_restore_and_is_lazy(tmp_path: Path) -> None:
    from entropytrade.api.jobs import Jobs
    from entropytrade.api.recovery import restore, snapshot
    from entropytrade.tracking.store import TrackingStore

    cache = REPO / "data/cache"
    base = cache / f"pytest-research-{uuid4().hex}"
    try:
        TrackingStore(Jobs(base))  # an ordinary workspace database
        svc = ResearchService(base, REPO, clock=SimulatedClock(NOW))
        assert not svc.started()
        assert svc.list_jobs() == []
        assert not (base / "research").exists()  # untouched until research is used
        job_id = submit(svc)
        svc.run_until_idle()
        archive = cache / f"pytest-research-{uuid4().hex}.zip"
        snapshot(REPO, base, archive)
        restored = cache / f"pytest-research-{uuid4().hex}"
        restore(REPO, archive, restored)
        again = ResearchService(restored, REPO, clock=SimulatedClock(NOW)).detail(job_id)
        assert again is not None
        assert again["status"] == JobStatus.AWAITING_OBSERVATIONS
        assert len(again["hypotheses"]) == 5
    finally:
        import shutil

        for path in cache.glob("pytest-research-*"):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
