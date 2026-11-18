"""Objective-to-paper decision with CONTROLLED SYNTHETIC evidence throughout.

Only the provider and reviewed-source boundaries are controlled. No feature/model files,
job transitions, approvals, experiments or eligibility decisions are seeded or rewritten.
Synthetic selection is injected in this test; production defaults reject these datasets.
"""

import asyncio
import json
import shutil
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from pydantic_ai.messages import ModelResponse, TextPart  # noqa: TID251
from pydantic_ai.models.function import FunctionModel  # noqa: TID251
from pydantic_ai.usage import RequestUsage  # noqa: TID251

from entropytrade.agents.hypotheses import propose
from entropytrade.agents.pricing import PricedResearchModel
from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.data.schema import Observation
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.research import acquire, modeling, service
from entropytrade.research.inventory import assess, inventory
from entropytrade.research.model import AssessmentStatus, DataKind, HypothesisSpec, JobStatus
from entropytrade.research.paper import ResearchPaperService
from entropytrade.research.readiness import ResearchReadinessService
from entropytrade.research.service import ResearchService
from entropytrade.research.sources import HostRule, Provides
from entropytrade.tracking.store import TrackingStore
from tests.research_execution_support import execution_fixture
from tests.research_modeling_support import MODEL_NOW, REPO
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
)
from tests.research_paper_support import PaperFixture


class ControlledArchive(acquire.Adapter):
    adapter_id = "controlled_synthetic_archive"

    def requests(self, params: dict[str, str]) -> list[str]:
        return ["https://controlled.invalid/archive"]

    def parse(
        self, fetched: list[acquire.Fetched], params: dict[str, str], now: datetime
    ) -> acquire.Parsed:
        item = fetched[0]
        payload = json.loads(item.body)
        assert payload["evidence_kind"] == "CONTROLLED SYNTHETIC"
        records = [
            Observation.model_validate(
                row
                | {
                    "raw_ref": "raw:" + item.receipt.sha256,
                    "raw_hash": item.receipt.sha256,
                    "ingested_at": now,
                }
            ).model_dump(mode="json")
            for row in payload["observations"]
        ]
        days = {row["valid_on"] for row in records}
        return acquire.Parsed(
            records=records,
            slices={
                (kind, variable, self.adapter_id, clock): {"CLIPHL": days}
                for kind, variable, clock in (
                    (DataKind.FORECAST_VINTAGES, "daytime_max_f", "issuance"),
                    (DataKind.FORECAST_REVISIONS, "daytime_max_f", "issuance"),
                    (DataKind.REFERENCE_OBSERVATIONS, "daily_high_f", "issuance"),
                    (DataKind.SETTLEMENT_LABELS, "daily_high_f", "receipt"),
                )
            },
        )


def archive_body() -> dict[str, Any]:
    rows = []
    end = MODEL_NOW.date() - timedelta(days=2)
    for index in range(270):
        target = end - timedelta(days=269 - index)
        at = datetime.combine(target, datetime.min.time(), UTC)
        forecast = 65 + index % 21 - 10
        for variable, value, issued, source, role in (
            ("daytime_max_f", forecast - 1, at - timedelta(days=1), "controlled-pfm", "feature"),
            ("daytime_max_f", forecast, at - timedelta(hours=12), "controlled-pfm", "feature"),
            (
                "daily_high_f",
                forecast + index % 5 - 2,
                at + timedelta(days=1, hours=13),
                "controlled-cli",
                "observation",
            ),
            (
                "settlement_high_f",
                forecast + index % 5 - 2,
                at + timedelta(days=1, hours=15),
                "controlled-label",
                "observation",
            ),
        ):
            # These are invented original archive clocks, explicitly synthetic. The
            # actual fetched receipt and ingestion clock remain MODEL_NOW.
            rows.append(
                {
                    "source_id": source,
                    "entity_id": "CLIPHL",
                    "variable": variable,
                    "valid_on": target.isoformat(),
                    "value": str(value),
                    "unit": "degF",
                    "revision_id": source + issued.isoformat(),
                    "published_at": issued.isoformat(),
                    "available_at": issued.isoformat(),
                    "received_at": MODEL_NOW.isoformat(),
                    "timing_basis": "provider_publication",
                    "role": role,
                    "evidence": "CONTROLLED SYNTHETIC archived publication",
                }
            )
    return {"evidence_kind": "CONTROLLED SYNTHETIC", "observations": rows}


def controlled_service(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, clock: SimulatedClock
) -> tuple[ResearchService, list[str], list[str]]:
    calls: list[str] = []
    prompts: list[str] = []
    batch = {
        "hypotheses": [
            {
                "title": title,
                "rationale": "CONTROLLED archived forecast errors may vary systematically.",
                "features": [{"name": name, "data_kinds": []} for name in names],
                "label": "settlement_high_f",
                "rules": [],
                "candidate_models": ["ridge"],
                "validation_plan": "Time ordered training, embargo, validation; untouched holdout.",
                "leakage_risks": ["Reports published after decision; overlapping outcomes"],
                "invalidation": ["No independent predictive or execution robustness"],
                "proposed_sources": [],
            }
            for title, names in (
                ("Controlled forecast bias", ("nws_pfm_max_f", "nws_cli_bias_f")),
                ("Controlled revision hypothesis", ("nws_pfm_max_f", "nws_pfm_revision_f")),
            )
        ]
    }

    def reply(*args: Any) -> ModelResponse:
        prompts.append(str(args[0]))
        return ModelResponse(
            parts=[TextPart(json.dumps(batch))],
            usage=RequestUsage(cost=Decimal("0.0021"), input_tokens=900, output_tokens=400),
        )

    def proposer(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert not kwargs["cancelled"]()
        return asyncio.run(
            propose(
                objective="Study Philadelphia NWS forecast bias for paper research",
                context=args[3],
                model=PricedResearchModel(FunctionModel(reply), stage=lambda: "hypotheses"),
                provider="gemini",
                budget_usd=Decimal("0.25"),
            )
        )

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "controlled.invalid"
        calls.append(str(request.url))
        return httpx.Response(200, json=archive_body())

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("controlled lifecycle attempted genuine network access")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    monkeypatch.setattr(acquire, "publish", partial(acquire.publish, data_kind="synthetic"))
    monkeypatch.setattr(service, "assess", partial(assess, expected_data_kind="synthetic"))
    for name in ("plan_hypothesis", "run_hypothesis", "verify_hypothesis"):
        monkeypatch.setattr(modeling, name, partial(getattr(modeling, name), data_kind="synthetic"))
    svc = ResearchService(
        workspace,
        REPO,
        clock=clock,
        proposer=proposer,
        transport=httpx.MockTransport(respond),
        transport_label="CONTROLLED SYNTHETIC",
        sleep=lambda _: None,
    )
    adapter = ControlledArchive()
    monkeypatch.setitem(acquire.ADAPTERS, adapter.adapter_id, adapter)
    source = svc.sources["iem-nws-pfm"].revalidated(
        source_id="controlled-archive",
        name="CONTROLLED SYNTHETIC archive",
        adapter=adapter.adapter_id,
        rate_limit_seconds=0,
        hosts=(HostRule(host="controlled.invalid", paths=("/archive",)),),
        provides=tuple(
            Provides(kind=kind, variable=variable)
            for kind, variable in (
                (DataKind.FORECAST_VINTAGES, "daytime_max_f"),
                (DataKind.FORECAST_REVISIONS, "daytime_max_f"),
                (DataKind.REFERENCE_OBSERVATIONS, "daily_high_f"),
                (DataKind.SETTLEMENT_LABELS, "daily_high_f"),
            )
        ),
        settlement_authority=("KXHIGHPHIL",),
    )
    svc.sources = {source.source_id: source}
    return svc, calls, prompts


def test_objective_acquisition_modeling_automatic_resume_and_paper_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    specimen = tmp_path / "repo"
    specimen.mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copy2(REPO / name, specimen / name)
    workspace = specimen / "data/cache/workspace"
    clock = SimulatedClock(MODEL_NOW)
    svc, calls, prompts = controlled_service(workspace, monkeypatch, clock)
    job_id = svc.submit(
        {
            "objective": "Study Philadelphia NWS forecast bias for paper research",
            "family": "weather",
            "universe": ["KXHIGHPHIL"],
            "lookback_days": 240,
            "provider": {"provider": "gemini", "model_name": "controlled-function-model"},
            "acquisition": "ask",
            "validation_depth": "standard",
        }
    )["id"]
    svc.run_until_idle()
    assert calls == []  # Discovery and language-model suggestions cannot authorize HTTP.
    assert len(prompts) == 1
    assert "registered_features" in prompts[0]
    assert svc.store.get_job(job_id)["status"] == JobStatus.AWAITING_AUTHORIZATION  # type: ignore[index]
    for row in svc.store.job_acquisitions(job_id):
        assert svc.approve(job_id, {"acquisition_id": row["id"], "decision": "approve"})
    svc.run_until_idle()
    assert len(calls) == 1  # Shared source/parameters are downloaded once.
    results = svc.store.experiments(job_id)
    fitted = [r for r in results if r["result"].get("models")]
    assert len(fitted) == 2
    assert all(r["result"]["data_kind"] == "synthetic" for r in fitted)
    assert all(r["result"]["validation"]["holdout_evaluated"] is False for r in fitted)
    assert all(not r["result"]["backtest"]["eligible"] for r in fitted)
    assert "order" in str(fitted[0]["result"]["backtest"]).lower()
    assert svc.store.get_job(job_id)["status"] == JobStatus.EVALUATED  # type: ignore[index]
    assert not svc.step()  # No hot loop before the scheduled inventory check.

    spec = HypothesisSpec.model_validate(svc.store.hypotheses(job_id)[0]["spec"])
    artifacts = svc.store.job_features(job_id)
    execution_id, fees = execution_fixture(
        svc.store.root, spec, artifacts, execution_delay_seconds=1
    )
    # An independent producer publishes an explicitly synthetic typed execution
    # archive; no acquisition link or job state is edited.
    for fee in fees:
        FeeEvidenceStore(workspace).put(fee)
    previous_ids = {r["id"] for r in results}
    hashes = {p: p.read_bytes() for p in (svc.store.root / "features").rglob("*") if p.is_file()}
    # Actual service reconstruction and recovery; no resume() or forced state change.
    restarted = ResearchService(
        workspace,
        REPO,
        clock=clock,
        proposer=svc.proposer,
        transport=svc.transport,
        sleep=lambda _: None,
    )
    restarted.sources = svc.sources
    restarted.recover()
    clock.advance(timedelta(hours=7))
    restarted.run_until_idle()
    changed = [r for r in restarted.store.experiments(job_id) if r["id"] not in previous_ids]
    assert len(changed) == 2
    assert all(
        execution_id in r["result"]["provenance"]["identity"]["execution_datasets"] for r in changed
    )
    assert all(r["result"]["backtest"]["eligible"] for r in changed)
    assert all(p.read_bytes() == content for p, content in hashes.items())
    assert calls == ["https://controlled.invalid/archive"]
    assert len(prompts) == 1
    jobs = Jobs(workspace)
    tracking = TrackingStore(jobs)
    paper = ResearchPaperService(workspace, tracking, clock=clock, expected_data_kind="synthetic")
    decisions = paper.proposals(job_id)
    assert decisions["submission_enabled"] is False
    assert decisions["proposals"]
    # The production policy must still reject every controlled source.
    genuine = ResearchPaperService(workspace, tracking, clock=clock).proposals(job_id)
    assert all(not p["eligible"] for p in genuine["proposals"])
    datasets, problems = inventory(workspace, REPO)
    assert not problems
    for req in restarted.store.requirements(job_id):
        if req.blocking == "predictive":
            assert assess(req, datasets, clock.now()).status is not AssessmentStatus.SATISFIED
    assert tracking.history() == []  # An eligibility decision does not authorize deployment.
    eligible = next(
        p for p in decisions["proposals"] if p["eligible"] and p["model_family"] == "ridge"
    )
    choice = {
        "experiment_id": eligible["experiment_id"],
        "model_family": "ridge",
        "interval_seconds": 300,
    }
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        created = paper.create(job_id, choice)
    monitor_id = created["deployment"]["id"]
    source = next(r["result"] for r in changed if r["id"] == choice["experiment_id"])
    fixture = PaperFixture(jobs, tracking, paper, job_id, choice["experiment_id"], choice, source)
    cycle = commit_controlled_cycle(
        fixture, clock.now().replace(hour=23, minute=0, second=5), clock=clock
    )
    assert cycle["data_kind"] == "synthetic"
    with controlled_forward_environment(clock):
        monitoring = ResearchReadinessService(
            workspace, tracking, restarted, clock=clock, expected_data_kind="synthetic"
        ).monitoring(monitor_id)
    assert monitoring["evaluation"]["status"] == "pending"
    assert monitoring["submission_enabled"] is False
    # Recovery hashes models and protected data; it must not regenerate or rescore them.
    frozen = {
        p.relative_to(workspace): p.read_bytes()
        for folder in ("research/features", "research/datasets", "research/experiments")
        for p in (workspace / folder).rglob("*")
        if p.is_file()
    }
    archive = specimen / "data/recovery/controlled.zip"
    snapshot(specimen, workspace, archive)
    restored = specimen / "data/cache/restored"
    restore(specimen, archive, restored)
    assert all((restored / path).read_bytes() == body for path, body in frozen.items())
    restored_paper = ResearchPaperService(
        restored, TrackingStore(Jobs(restored)), clock=clock, expected_data_kind="synthetic"
    )
    assert restored_paper.proposals(job_id) == paper.proposals(job_id)


def test_shutdown_refuses_to_release_a_live_research_writer(tmp_path: Path) -> None:
    release = threading.Event()
    svc = ResearchService(tmp_path, REPO)
    svc.thread = threading.Thread(target=release.wait, daemon=True)
    svc.thread.start()
    try:
        with pytest.raises(RuntimeError, match="lease retained"):
            svc.close(timeout=0.01)
        assert svc.thread.is_alive()
        assert svc.stop.is_set()
    finally:
        release.set()
        svc.close(timeout=5)
    assert not svc.thread.is_alive()


def test_publication_separates_controlled_identity_and_default_assessment(tmp_path: Path) -> None:
    from entropytrade.research.sources import load_catalog
    from tests.unit.test_research_acquisition import requirement

    source = load_catalog(REPO)["iem-nws-pfm"]
    adapter = acquire.ADAPTERS["iem_afos_pfm"]
    parsed = acquire.Parsed(
        records=[],
        slices={
            (DataKind.FORECAST_VINTAGES, "daytime_max_f", "controlled-identity-test", "issuance"): {
                "CLIPHL": {"2026-10-01"}
            },
        },
    )
    root = tmp_path / "research"
    controlled = acquire.publish(
        root, source, adapter, {}, [], parsed, [], created_at=MODEL_NOW, data_kind="synthetic"
    )
    # The identical payload cannot alias a dataset declared authentic. This is an
    # identity test only: neither empty fixture is genuine scientific evidence.
    declared = acquire.publish(root, source, adapter, {}, [], parsed, [], created_at=MODEL_NOW)
    assert declared["dataset_id"] != controlled["dataset_id"]
    records, problems = inventory(tmp_path, REPO)
    assert not problems
    synthetic = [r for r in records if r.dataset_id == controlled["dataset_id"]]
    req = requirement(min_events=1)
    assert assess(req, synthetic, MODEL_NOW).status is AssessmentStatus.MISSING
    assert (
        assess(req, synthetic, MODEL_NOW, expected_data_kind="synthetic").status
        is AssessmentStatus.SATISFIED
    )
