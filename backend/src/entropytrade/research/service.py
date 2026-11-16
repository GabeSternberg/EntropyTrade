"""Persistent research orchestration.

A deterministic state machine advances each job one durable step at a time. Each step is
idempotent and checkpointed, so a job resumes after a restart. Language models only
propose; deterministic code derives requirements, inspects evidence and sets statuses.
"""

import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.domain.time import Clock, SystemClock
from entropytrade.features.registry import scientific_hash
from entropytrade.research.families import Entity, Family, load_families
from entropytrade.research.hypotheses import (
    HypothesisProposalBatch,
    deduplicate,
    local_hypotheses,
    merge_requirements,
    provider_hypotheses,
    requirements,
)
from entropytrade.research.inventory import assess, inventory, summary
from entropytrade.research.model import (
    RUNNABLE,
    AssessmentStatus,
    DataKind,
    DataRequirement,
    HypothesisSpec,
    HypothesisStatus,
    JobStatus,
    Provenance,
    ResearchRequest,
)
from entropytrade.research.registry import FeatureRegistry
from entropytrade.research.store import ResearchStore, job_identifier

Proposer = Callable[..., dict[str, Any]]
SCOPE = (
    "Research eligibility only. No hypothesis is an established edge; nothing here approves "
    "paper or live trading, and no order path exists."
)


class StepError(Exception):
    """A step failed with a fixed, credential-free reason."""

    def __init__(self, reason: str, *, transient: bool, kind: str = "StepError") -> None:
        super().__init__(reason)
        self.reason, self.transient, self.kind = reason, transient, kind


class ResearchService:
    def __init__(
        self,
        workspace: Path,
        repo: Path,
        *,
        clock: Clock | None = None,
        proposer: Proposer | None = None,
        lease_fd: int | None = None,
        poll_seconds: float = 0.5,
    ) -> None:
        from entropytrade.research.worker import SubprocessProposer

        self.workspace, self.repo = workspace, repo
        self.clock = clock or SystemClock()
        self._store: ResearchStore | None = None
        self.families = load_families(repo)
        self.registry = FeatureRegistry()
        self.proposer = proposer or SubprocessProposer(repo, workspace, lease_fd=lease_fd)
        self.poll_seconds = poll_seconds
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.cancelled: set[str] = set()
        self.thread = threading.Thread(target=self.loop, name="research-jobs", daemon=True)

    # ------------------------------------------------------------ lifecycle
    @property
    def store(self) -> ResearchStore:
        """Created on first use, so a workspace that never runs research is unchanged."""
        if self._store is None:
            self._store = ResearchStore(self.workspace / "research")
        return self._store

    def started(self) -> bool:
        return self._store is not None or (self.workspace / "research/research.sqlite").is_file()

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.store.list_jobs() if self.started() else []

    def now(self) -> datetime:
        return self.clock.now()

    def start(self) -> None:
        self.recover()
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        self.wake.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=10)

    def recover(self) -> None:
        """Jobs mid-step simply re-run their idempotent step; record that it happened."""
        if not self.started():
            return
        for job in self.store.list_jobs(limit=500):
            if JobStatus(job["status"]) in RUNNABLE - {JobStatus.QUEUED}:
                self.store.event(
                    job["id"], "recovered", "Resumed from the last checkpoint", now=self.now()
                )

    def loop(self) -> None:
        while not self.stop.is_set():
            try:
                ran = self.step()
            except Exception:  # noqa: BLE001 - the worker thread must outlive one bad job
                ran = False
            if not ran:
                self.wake.wait(self.poll_seconds)
                self.wake.clear()

    def step(self) -> bool:
        if not self.started():
            return False
        job_id = self.store.runnable(self.now())
        if job_id is None:
            return False
        self.advance(job_id)
        return True

    def run_until_idle(self, limit: int = 200) -> int:
        """Advance synchronously until no job is due (tests and CLI use this)."""
        for count in range(limit):
            if not self.step():
                return count
        raise RuntimeError("research jobs did not become idle")

    # ------------------------------------------------------------- requests
    def submit(self, value: object) -> dict[str, Any]:
        request = ResearchRequest.model_validate(value)
        family = self.family(request.family)
        if request.provider.provider != "local_templates" and request.budget.ai_usd <= 0:
            raise ValueError("provider research needs a positive AI budget")
        universe = family.resolve_universe(request.objective, request.universe)
        job_id, created = self.store.create_job(
            request, universe=tuple(e.series for e in universe), now=self.now()
        )
        self.wake.set()
        return {"id": job_id, "created": created}

    def family(self, name: str) -> Family:
        if name not in self.families:
            raise ValueError("unknown research family")
        return self.families[name]

    def cancel(self, job_id: str) -> bool:
        self.cancelled.add(job_identifier(job_id))
        if not self.started():
            raise KeyError("research job not found")
        return self.store.transition(
            job_id, JobStatus.CANCELLED, "Cancelled by user", now=self.now()
        )

    def resume(self, job_id: str) -> bool:
        job = self.store.get_job(job_id) if self.started() else None
        if job is None:
            raise KeyError("research job not found")
        status = JobStatus(job["status"])
        if status in {
            JobStatus.EVALUATED,
            JobStatus.AWAITING_OBSERVATIONS,
            JobStatus.AWAITING_AUTHORIZATION,
        }:
            changed = self.store.transition(
                job_id, JobStatus.PLANNING, "Reevaluation requested by user", now=self.now()
            )
        elif status is JobStatus.RECOVERABLE_ERROR:
            changed = self.store.transition(
                job_id, status, "Retry requested by user", now=self.now()
            )
        else:
            raise ValueError("only waiting, evaluated or recoverable jobs can be resumed")
        self.wake.set()
        return changed

    # ------------------------------------------------------------- stepping
    def advance(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            return
        status = JobStatus(job["status"])
        request = ResearchRequest.model_validate(job["request"])
        started = time.monotonic()
        stage = status
        try:
            if job["usage"]["runtime_seconds"] >= request.budget.max_runtime_seconds:
                raise StepError("The job's runtime budget is exhausted.", transient=False)
            if status is JobStatus.RECOVERABLE_ERROR:
                stage = JobStatus(job["checkpoint"].get("stage", JobStatus.PLANNING.value))
                self.store.transition(
                    job_id, stage, "Retrying after a recoverable error", now=self.now()
                )
                return
            if status is JobStatus.QUEUED:
                self.store.transition(
                    job_id, JobStatus.GENERATING, "Formulating hypotheses", now=self.now()
                )
            elif status is JobStatus.GENERATING:
                self._generate(job, request)
            elif status in {JobStatus.PLANNING, JobStatus.AWAITING_OBSERVATIONS}:
                if status is JobStatus.AWAITING_OBSERVATIONS:
                    self.store.transition(
                        job_id,
                        JobStatus.PLANNING,
                        "Scheduled reevaluation of awaited evidence",
                        now=self.now(),
                    )
                self._plan(job, request)
            else:
                self.extra_step(job, request, status)
        except StepError as failure:
            self._fail(job, request, stage, failure)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            self._fail(
                job,
                request,
                stage,
                StepError(
                    f"{stage.value} step error ({type(exc).__name__})",
                    transient=True,
                    kind=type(exc).__name__,
                ),
            )
        finally:
            self.store.add_usage(job_id, runtime_seconds=time.monotonic() - started)

    def extra_step(self, job: dict[str, Any], request: ResearchRequest, status: JobStatus) -> None:
        """Later milestones add acquisition and feature steps here."""
        del job, request
        raise StepError(f"no handler for {status.value}", transient=False)

    def _fail(
        self, job: dict[str, Any], request: ResearchRequest, stage: JobStatus, failure: StepError
    ) -> None:
        attempts = int(job["attempts"]) + 1
        self.store.set_attempts(job["id"], attempts)
        # Resume where the work happens: waiting and evaluated jobs re-plan; queued generates.
        stage = {
            JobStatus.QUEUED: JobStatus.GENERATING,
            JobStatus.AWAITING_OBSERVATIONS: JobStatus.PLANNING,
            JobStatus.AWAITING_AUTHORIZATION: JobStatus.PLANNING,
            JobStatus.EVALUATED: JobStatus.PLANNING,
        }.get(stage, stage)
        error = {"type": failure.kind, "stage": stage.value, "reason": failure.reason}
        if failure.transient and attempts <= request.budget.max_retries:
            delay = timedelta(seconds=min(3600, 30 * 2 ** (attempts - 1)))
            self.store.transition(
                job["id"],
                JobStatus.RECOVERABLE_ERROR,
                f"{failure.reason} Retry {attempts} of {request.budget.max_retries} scheduled.",
                now=self.now(),
                next_run_at=self.now() + delay,
                checkpoint={**job["checkpoint"], "stage": stage.value},
                error=error,
            )
        else:
            self.store.transition(
                job["id"], JobStatus.FAILED, failure.reason, now=self.now(), error=error
            )

    def entities(self, job: dict[str, Any], family: Family) -> list[Entity]:
        wanted = set(job["universe"])
        return [e for e in family.entities if e.series in wanted]

    def window(self, request: ResearchRequest) -> tuple[date, date]:
        """Completed target dates only: labels for the last two days may still be revised."""
        end = self.now().date() - timedelta(days=2)
        return end - timedelta(days=request.lookback_days - 1), end

    # ----------------------------------------------------------- hypotheses
    def context(self, family: Family, universe: list[Entity]) -> dict[str, Any]:
        return {
            "family": family.describe(),
            "universe": [e.series for e in universe],
            "registered_features": [
                {
                    "name": d.feature_id,
                    "role": d.role,
                    "unit": d.unit,
                    "description": d.description,
                    "evidence": sorted({i.kind.value for i in d.inputs}),
                }
                for d in self.registry.definitions.values()
                if d.family in {family.family, "market", "calendar"}
            ],
            "allowed_evidence_kinds": [k.value for k in DataKind],
            "candidate_models": list(family.models),
            "example_mechanisms": [t.title for t in family.templates],
        }

    def _generate(self, job: dict[str, Any], request: ResearchRequest) -> None:
        job_id = job["id"]
        family = self.family(request.family)
        universe = self.entities(job, family)
        now = self.now()
        if request.provider.provider == "local_templates":
            specs = local_hypotheses(request, family, universe, now)
            source = "local templates (deterministic, not language-model reasoning)"
        else:
            usage = job["usage"]
            if Decimal(usage["ai_usd"]) >= request.budget.ai_usd:
                raise StepError("The per-job AI budget is exhausted.", transient=False)
            attempt = int(job["checkpoint"].get("generation_attempt", 0)) + 1
            self.store.transition(
                job_id,
                JobStatus.GENERATING,
                f"Calling {request.provider.provider} ({request.provider.model_name})",
                now=now,
                checkpoint={**job["checkpoint"], "generation_attempt": attempt},
            )
            result = self.proposer(
                job_id,
                attempt,
                request.provider.provider,
                self.context(family, universe),
                timeout=float(min(300, request.budget.max_runtime_seconds)),
                cancelled=lambda: job_id in self.cancelled,
            )
            self._record_ai_usage(job_id, result)
            if result.get("status") != "completed":
                failure = result.get("failure") or {}
                raise StepError(
                    str(failure.get("reason", "Hypothesis generation failed.")),
                    transient=bool(failure.get("transient")),
                    kind=str(failure.get("type", "ProviderFailure")),
                )
            try:
                batch = HypothesisProposalBatch.model_validate(result["proposals"])
            except ValueError as exc:
                raise StepError(
                    "Provider output failed deterministic schema validation.", transient=False
                ) from exc
            specs = provider_hypotheses(
                batch,
                request,
                family,
                universe,
                Provenance(
                    generator="provider",
                    provider=request.provider.provider,
                    model_name=request.provider.model_name,
                    prompt_hash=str(result.get("prompt_hash", "")),
                    created_at=now,
                ),
            )
            source = f"{request.provider.provider} ({request.provider.model_name})"
        prior = self.store.prior_signatures()
        items: list[tuple[HypothesisSpec, HypothesisStatus, tuple[str, ...], str]] = []
        for spec, note in deduplicate(specs, prior):
            if note == "duplicate":
                items.append(
                    (
                        spec,
                        HypothesisStatus.DUPLICATE,
                        ("Same mechanism and features as an earlier hypothesis in this job.",),
                        note,
                    )
                )
            else:
                reasons = (
                    (f"Previously searched in research job {prior[spec.signature]}.",)
                    if note == "previously_searched"
                    else ()
                )
                items.append((spec, HypothesisStatus.PROPOSED, reasons, note))
        self.store.save_hypotheses(job_id, items, now=now)
        kept = sum(item[1] is HypothesisStatus.PROPOSED for item in items)
        self.store.transition(
            job_id,
            JobStatus.PLANNING,
            f"{kept} hypotheses recorded from {source}; deriving data requirements",
            now=self.now(),
        )

    def _record_ai_usage(self, job_id: str, result: dict[str, Any]) -> None:
        usage = result.get("usage") or {}
        cost = result.get("cost_usd")
        self.store.add_usage(
            job_id,
            ai_usd=Decimal(str(cost)) if cost not in (None, "None") else Decimal(0),
            ai_requests=int(usage.get("requests", 0) or 0),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
        )

    # -------------------------------------------------------------- planning
    def _plan(self, job: dict[str, Any], request: ResearchRequest) -> None:
        job_id = job["id"]
        family = self.family(request.family)
        universe = self.entities(job, family)
        window = self.window(request)
        groups = []
        resolutions = {}
        for row in self.store.hypotheses(job_id):
            if row["status"] == HypothesisStatus.DUPLICATE.value:
                continue
            spec = HypothesisSpec.model_validate(row["spec"])
            found, resolved = requirements(
                spec,
                family,
                universe,
                self.registry,
                window=window,
                depth=request.validation_depth,
            )
            groups.append(found)
            resolutions[spec.hypothesis_id] = resolved
        merged = merge_requirements(groups)
        self.store.save_requirements(job_id, merged, resolutions)
        records, problems = inventory(self.workspace, self.repo)
        now = self.now()
        assessments = [assess(item, records, now) for item in merged]
        self.store.save_assessments(job_id, assessments)
        satisfied = sum(a.status is AssessmentStatus.SATISFIED for a in assessments)
        detail = (
            f"Inventory checked {len(records)} evidence slices; {satisfied} of {len(merged)} "
            "requirements satisfied"
        )
        if problems:
            detail += f"; {len(problems)} stores failed verification and were not used"
        self.store.event(job_id, "inventory", detail, now=now)
        self.after_inventory(job, request, merged, records)

    def after_inventory(
        self,
        job: dict[str, Any],
        request: ResearchRequest,
        merged: list[DataRequirement],
        records: list[Any],
    ) -> None:
        """Milestone A evaluates immediately. Acquisition planning extends this hook."""
        del request, merged, records
        self.evaluate(job["id"])
        self.store.transition(
            job["id"], JobStatus.EVALUATED, self.outcome_detail(job["id"]), now=self.now()
        )

    # ------------------------------------------------------------ evaluation
    def evaluate(self, job_id: str) -> None:
        """Deterministic hypothesis statuses from requirements and assessments."""
        requirements_by_id = {r.requirement_id: r for r in self.store.requirements(job_id)}
        assessments = self.store.assessments(job_id)
        resolutions = self.store.resolutions(job_id)
        now = self.now()
        for row in self.store.hypotheses(job_id):
            if row["status"] == HypothesisStatus.DUPLICATE.value:
                continue
            hypothesis_id = row["hypothesis_id"]
            mine = [r for r in requirements_by_id.values() if hypothesis_id in r.hypotheses]
            status, reasons, facets = self.classify(
                hypothesis_id, mine, assessments, resolutions.get(hypothesis_id, [])
            )
            self.store.set_hypothesis_status(
                job_id, hypothesis_id, status, reasons, facets, now=now
            )

    def classify(
        self,
        hypothesis_id: str,
        mine: list[DataRequirement],
        assessments: dict[str, Any],
        resolutions: list[Any],
    ) -> tuple[HypothesisStatus, list[str], dict[str, Any]]:
        facets: dict[str, Any] = {}
        for blocking in ("predictive", "execution"):
            scoped = [r for r in mine if r.blocking_for(hypothesis_id) == blocking]
            done = [
                r
                for r in scoped
                if r.requirement_id in assessments
                and assessments[r.requirement_id].status is AssessmentStatus.SATISFIED
            ]
            facets[blocking] = {
                "satisfied": len(done),
                "total": len(scoped),
                "ready": len(done) == len(scoped),
            }
        reasons = [
            f"{r.purpose}: {assessments[r.requirement_id].reasons[0]}"
            for r in mine
            if r.requirement_id in assessments
            and assessments[r.requirement_id].status is not AssessmentStatus.SATISFIED
        ]
        unregistered = [r.requested for r in resolutions if r.via == "unregistered"]
        unimplemented = sorted(
            {
                r.feature_id
                for r in resolutions
                if r.feature_id
                and self.registry.get(r.feature_id).materializer == "not_implemented"
            }
        )
        facets["unregistered_features"] = unregistered
        facets["unimplemented_features"] = unimplemented
        if unregistered:
            reasons.insert(
                0,
                "Unregistered features need a reviewed definition before a strategy can use "
                "them: " + ", ".join(unregistered) + ". Their declared data needs were recorded.",
            )
            return HypothesisStatus.UNSUPPORTED, reasons, facets
        if facets["predictive"]["ready"] and facets["execution"]["ready"] and not unimplemented:
            return HypothesisStatus.BACKTEST_ELIGIBLE, reasons, facets
        if unimplemented:
            reasons.append(
                "Features without an implemented materializer: " + ", ".join(unimplemented)
            )
        return HypothesisStatus.NEEDS_DATA, reasons, facets

    def outcome_detail(self, job_id: str) -> str:
        counts: dict[str, int] = {}
        for row in self.store.hypotheses(job_id):
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        parts = [f"{n} {s.replace('_', ' ')}" for s, n in sorted(counts.items())]
        return "Evaluated: " + ", ".join(parts)

    # -------------------------------------------------------------- reading
    def catalog(self) -> dict[str, Any]:
        from entropytrade.research.providers import provider_catalog

        return {
            "families": [f.describe() for f in self.families.values()],
            "providers": provider_catalog(),
            "features": self.registry.catalog(),
            "data_kinds": [k.value for k in DataKind],
            "defaults": ResearchRequest(
                objective="placeholder objective", family="weather"
            ).model_dump(mode="json", exclude={"objective", "family"}),
            "scope": SCOPE,
            "submission_enabled": False,
        }

    def detail(self, job_id: str) -> dict[str, Any] | None:
        if not self.started():
            return None
        job = self.store.get_job(job_id)
        if job is None:
            return None
        assessments = self.store.assessments(job_id)
        job["hypotheses"] = self.store.hypotheses(job_id)
        job["requirements"] = [
            {
                **r.model_dump(mode="json"),
                "assessment": assessments[r.requirement_id].model_dump(mode="json")
                if r.requirement_id in assessments
                else None,
            }
            for r in self.store.requirements(job_id)
        ]
        job["resolutions"] = {
            h: [r.model_dump(mode="json") for r in items]
            for h, items in self.store.resolutions(job_id).items()
        }
        job["events"] = self.store.events(job_id)
        job["scope"] = SCOPE
        job["submission_enabled"] = False
        self.extend_detail(job)
        return job

    def extend_detail(self, job: dict[str, Any]) -> None:
        """Later milestones attach acquisitions, sources, features and forward requests."""

    def report(self, job_id: str) -> dict[str, Any] | None:
        detail = self.detail(job_id)
        if detail is None:
            return None
        used = {
            r.feature_id
            for items in self.store.resolutions(job_id).values()
            for r in items
            if r.feature_id
        }
        report = {
            "schema": "entropytrade-research-report-v1",
            "generated_at": self.now().isoformat(),
            "job": detail,
            "feature_definitions": {
                f: self.registry.get(f).model_dump(mode="json")
                | {"definition_hash": self.registry.get(f).definition_hash}
                for f in sorted(used)
            },
            "scope": SCOPE,
        }
        report["report_hash"] = scientific_hash(report)
        return report

    def inventory_summary(self) -> dict[str, Any]:
        records, problems = inventory(self.workspace, self.repo)
        return {"records": summary(records), "problems": problems}
