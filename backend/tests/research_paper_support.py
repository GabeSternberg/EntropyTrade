"""Actual controlled C fitting/replay inputs for paper-lifecycle acceptance only."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.research.model import HypothesisStatus, JobStatus, ResearchRequest
from entropytrade.research.modeling import run_hypothesis
from entropytrade.research.paper import ResearchPaperService
from entropytrade.research.registry import FeatureRegistry
from entropytrade.research.store import ResearchStore
from entropytrade.tracking.store import TrackingStore
from tests.research_execution_support import execution_fixture
from tests.research_modeling_support import MODEL_NOW, modeling_fixture


@dataclass
class PaperFixture:
    jobs: Jobs
    tracking: TrackingStore
    service: ResearchPaperService
    job_id: str
    experiment_id: str
    request: dict[str, Any]
    result: dict[str, Any]


def paper_fixture(workspace: Path) -> PaperFixture:
    jobs = Jobs(workspace)
    tracking = TrackingStore(jobs)
    store = ResearchStore(workspace / "research")
    spec, artifacts = modeling_fixture(store.root)
    spec = spec.revalidated(rules=())
    execution, fees = execution_fixture(store.root, spec, artifacts)
    result = run_hypothesis(
        root=store.root,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
        execution_datasets=(execution,),
        fee_versions=fees,
    )
    request = ResearchRequest(objective=spec.objective, family=spec.family, universe=spec.universe)
    job_id, _ = store.create_job(request, universe=spec.universe, now=MODEL_NOW)
    store.save_hypotheses(job_id, [(spec, HypothesisStatus.PROPOSED, (), "")], now=MODEL_NOW)
    for status in (
        JobStatus.GENERATING,
        JobStatus.PLANNING,
        JobStatus.FEATURIZING,
        JobStatus.MODELING,
    ):
        store.transition(job_id, status, "Controlled paper lifecycle fixture", now=MODEL_NOW)
    store.plan_experiment(job_id, result["experiment_id"], spec.hypothesis_id, {}, now=MODEL_NOW)
    store.start_experiment(job_id, result["experiment_id"], now=MODEL_NOW)
    store.finish_experiment(
        job_id, result["experiment_id"], status="completed", result=result, now=MODEL_NOW
    )
    store.transition(job_id, JobStatus.EVALUATED, "Controlled source fitted", now=MODEL_NOW)
    for version in fees:
        assert version.policy is not None
        # Explicit controlled current fee evidence, never an authentic certification.
        current = version.revalidated(
            policy=version.policy.revalidated(effective_to=MODEL_NOW + timedelta(days=365))
        )
        FeeEvidenceStore(workspace).put(current)
    service = ResearchPaperService(
        workspace, tracking, clock=SimulatedClock(MODEL_NOW), expected_data_kind="synthetic"
    )
    choice = {
        "experiment_id": result["experiment_id"],
        "model_family": "ridge",
        "interval_seconds": 300,
    }
    return PaperFixture(jobs, tracking, service, job_id, result["experiment_id"], choice, result)
