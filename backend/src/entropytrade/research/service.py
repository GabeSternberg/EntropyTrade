"""Persistent research orchestration.

A deterministic state machine advances each job one durable step at a time. Each step is
idempotent and checkpointed, so a job resumes after a restart. Language models only
propose; deterministic code derives requirements, inspects evidence and sets statuses.
"""

import threading
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.domain.time import Clock, SystemClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import (
    AcquisitionError,
    BudgetExceededError,
    Fetcher,
    RawStore,
    acquisition_key,
    adapter_params,
    load_records,
    run_acquisition,
)
from entropytrade.research.families import Entity, Family, load_families
from entropytrade.research.forward import CHECK_INTERVAL, CollectorConfig, decorate_forward
from entropytrade.research.hypotheses import (
    HypothesisProposalBatch,
    deduplicate,
    local_hypotheses,
    merge_requirements,
    provider_hypotheses,
    requirements,
)
from entropytrade.research.inventory import assess, inventory, summary
from entropytrade.research.materialize import materialize, publish_feature
from entropytrade.research.model import (
    RUNNABLE,
    Assessment,
    AssessmentStatus,
    DataKind,
    DataRequirement,
    HypothesisSpec,
    HypothesisStatus,
    JobStatus,
    Provenance,
    ResearchRequest,
)
from entropytrade.research.registry import FeatureDefinition, FeatureRegistry
from entropytrade.research.sources import SourceDescriptor, discover, load_catalog
from entropytrade.research.store import ResearchStore, job_identifier

if TYPE_CHECKING:
    import httpx

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
        transport: "httpx.BaseTransport | None" = None,
        transport_label: str = "live",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        from entropytrade.research.worker import SubprocessProposer

        self.workspace, self.repo = workspace, repo
        self.clock = clock or SystemClock()
        self._store: ResearchStore | None = None
        self._store_lock = threading.Lock()
        self.families = load_families(repo)
        self.registry = FeatureRegistry()
        self.sources = load_catalog(repo)
        self.collector = CollectorConfig(repo)
        # Tests and the controlled browser server replay recorded responses; live otherwise.
        self.transport, self.transport_label, self.sleep = transport, transport_label, sleep
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
        with self._store_lock:
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
        requeued = self.store.recover_acquisitions(now=self.now())
        self.store.recover_experiments(now=self.now())
        for job in self.store.list_jobs(limit=500):
            if JobStatus(job["status"]) in RUNNABLE - {JobStatus.QUEUED}:
                self.store.event(
                    job["id"],
                    "recovered",
                    "Resumed from the last checkpoint"
                    + (f"; {requeued} interrupted acquisitions queued again" if requeued else ""),
                    now=self.now(),
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
            spent = job["usage"]["runtime_seconds"] - job["checkpoint"].get("runtime_base", 0)
            if spent >= request.budget.max_runtime_seconds:
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
                    # Each reevaluation gets its own runtime allowance; waiting is not work.
                    self.store.transition(
                        job_id,
                        JobStatus.PLANNING,
                        "Scheduled reevaluation of awaited evidence",
                        now=self.now(),
                        checkpoint={
                            **job["checkpoint"],
                            "runtime_base": job["usage"]["runtime_seconds"],
                        },
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

    # ------------------------------------------------- discovery and acquisition
    def after_inventory(
        self,
        job: dict[str, Any],
        request: ResearchRequest,
        merged: list[DataRequirement],
        records: list[Any],
    ) -> None:
        """Discover sources for unmet requirements, plan acquisitions and forward requests."""
        del records
        job_id = job["id"]
        now = self.now()
        assessments = self.store.assessments(job_id)
        decisions = []
        for requirement in merged:
            assessment = assessments.get(requirement.requirement_id)
            if assessment is None:
                continue
            if assessment.status is AssessmentStatus.SATISFIED:
                # Awaited evidence arrived: record it on the shared forward request.
                forward = self.store.requirement_forward(job_id, requirement.requirement_id)
                if forward is not None:
                    self.store.plan_forward(
                        requirement,
                        source_id=forward["source_id"],
                        collector=forward["collector"],
                        collector_status=forward["collector_status"],
                        events_observed=assessment.events_available,
                        detail=forward["detail"],
                        now=now,
                        next_check_at=now + CHECK_INTERVAL,
                    )
                continue
            found = discover(self.sources, requirement, today=now.date())
            decisions.extend(found)
            self.store.save_source_decisions(job_id, requirement.requirement_id, found)
            for decision in found:
                source = self.sources[decision.source_id]
                if decision.decision == "acquire":
                    self._plan_acquisition(job_id, request, requirement, source)
                elif decision.decision == "forward_collect":
                    self._plan_forward(job_id, requirement, source, assessment.events_available)
        self.store.event(
            job_id,
            "discovery",
            f"Evaluated {len(decisions)} source options: "
            + ", ".join(
                f"{n} {d}" for d, n in sorted(Counter(x.decision for x in decisions).items())
            ),
            now=now,
        )
        queued = self.store.job_acquisitions(job_id, statuses=("queued", "running"))
        if queued and min(self.budget_left(job, request)) > 0:
            self.store.transition(
                job_id,
                JobStatus.ACQUIRING,
                f"{len(queued)} read-only acquisitions queued",
                now=self.now(),
            )
        else:
            self.store.transition(
                job_id, JobStatus.FEATURIZING, "Registering point-in-time features", now=self.now()
            )

    def _missing_span(
        self, source_id: str, entity: str, requirement: DataRequirement
    ) -> tuple[date, date] | None:
        """Dates not yet attempted from this source, so nothing identical is fetched twice."""
        attempted: set[date] = set()
        for row in self.store.acquisitions_for(source_id, entity):
            if row["status"] in {"completed", "failed", "queued", "running", "awaiting_approval"}:
                start = date.fromisoformat(row["params"]["start"])
                end = date.fromisoformat(row["params"]["end"])
                attempted.update(start + timedelta(days=i) for i in range((end - start).days + 1))
        days = [
            requirement.start + timedelta(days=i)
            for i in range((requirement.end - requirement.start).days + 1)
        ]
        missing = [d for d in days if d not in attempted]
        return (missing[0], missing[-1]) if missing else None

    def _plan_acquisition(
        self,
        job_id: str,
        request: ResearchRequest,
        requirement: DataRequirement,
        source: SourceDescriptor,
    ) -> None:
        if request.acquisition == "none":
            return
        entity = (
            requirement.series
            if source.source_id == "kalshi-settled-markets"
            else requirement.entity
        )
        span = self._missing_span(source.source_id, entity, requirement)
        if span is None:
            existing = self.store.acquisitions_for(source.source_id, entity)
            for row in existing:
                self.store.link_acquisition(
                    job_id, row["id"], requirement.requirement_id, "inherited"
                )
                if request.acquisition == "approved_sources":
                    # Pre-approved here; another job's pending ask cannot block this job.
                    self.store.decide_acquisition(job_id, row["id"], approve=True, now=self.now())
            return
        params = adapter_params(
            source, entity=entity, series=requirement.series, start=span[0], end=span[1]
        )
        key = acquisition_key(source, params)
        approval = "automatic" if request.acquisition == "approved_sources" else "pending"
        acquisition_id = self.store.plan_acquisition(
            key,
            source.source_id,
            params,
            status="queued" if approval == "automatic" else "awaiting_approval",
            now=self.now(),
        )
        self.store.link_acquisition(job_id, acquisition_id, requirement.requirement_id, approval)
        if approval == "automatic":
            # This job's user pre-approved the source; another job's pending ask can't block it.
            self.store.decide_acquisition(job_id, acquisition_id, approve=True, now=self.now())

    def _plan_forward(
        self,
        job_id: str,
        requirement: DataRequirement,
        source: SourceDescriptor,
        observed: int,
    ) -> None:
        status, detail = self.collector.coverage(source, requirement)
        self.store.plan_forward(
            requirement,
            source_id=source.source_id,
            collector="canonical_local_chain"
            if status == "covered"
            else "requires_collector_change",
            collector_status=status,
            events_observed=observed,
            detail=detail,
            now=self.now(),
            next_check_at=self.now() + CHECK_INTERVAL,
        )
        forward_id = self.store.forward_id(requirement.coverage_key)
        self.store.link_forward(job_id, forward_id, requirement.requirement_id)

    def extra_step(self, job: dict[str, Any], request: ResearchRequest, status: JobStatus) -> None:
        if status is JobStatus.ACQUIRING:
            self._acquire(job, request)
        elif status is JobStatus.FEATURIZING:
            self._featurize(job, request)
        elif status is JobStatus.MODELING:
            self._model(job, request)
        else:
            raise StepError(f"no handler for {status.value}", transient=False)

    def budget_left(self, job: dict[str, Any], request: ResearchRequest) -> tuple[int, int]:
        usage = self.store.get_job(job["id"])["usage"]  # type: ignore[index]
        return (
            request.budget.max_http_requests - int(usage["http_requests"]),
            request.budget.max_bytes - int(usage["bytes"]),
        )

    def _acquire(self, job: dict[str, Any], request: ResearchRequest) -> None:
        """Run one queued acquisition, then continue or return to planning."""
        job_id = job["id"]
        queued = self.store.job_acquisitions(job_id, statuses=("queued", "running"))
        if not queued:
            self.store.transition(
                job_id,
                JobStatus.PLANNING,
                "Acquisitions finished; reassessing evidence",
                now=self.now(),
            )
            return
        row = queued[0]
        due = datetime.fromisoformat(row["next_attempt_at"])
        if due > self.now():
            self.store.transition(
                job_id,
                JobStatus.ACQUIRING,
                "Waiting to retry a transient source failure",
                now=self.now(),
                next_run_at=due,
            )
            return
        source = self.sources[row["source_id"]]
        remaining_requests, remaining_bytes = self.budget_left(job, request)
        if remaining_requests <= 0 or remaining_bytes <= 0:
            self.store.transition(
                job_id,
                JobStatus.PLANNING,
                "The job's HTTP or byte budget is exhausted; remaining acquisitions skipped",
                now=self.now(),
            )
            return
        self.store.start_acquisition(row["id"], now=self.now())
        self.store.event(
            job_id,
            "acquisition",
            f"Fetching {source.name} for {row['params']['entity']} "
            f"{row['params']['start']}..{row['params']['end']}",
            now=self.now(),
        )
        fetcher = Fetcher(
            source=source,
            raw=RawStore(self.store.root),
            clock=self.now,
            budget_requests=remaining_requests,
            budget_bytes=remaining_bytes,
            cancelled=lambda: job_id in self.cancelled,
            transport=self.transport,
            sleep=self.sleep,
        )
        try:
            manifest = run_acquisition(
                self.store.root, source, row["params"], fetcher, now=self.now
            )
        except (OSError, ValueError, TypeError, KeyError):
            # Never leave a shared acquisition stuck in "running"; the job step retries.
            self.store.finish_acquisition(
                row["id"], "queued", "Interrupted by an internal error", now=self.now()
            )
            raise
        except AcquisitionError as exc:
            self.store.add_usage(job_id, http_requests=fetcher.requests, bytes=fetcher.bytes)
            if exc.reason == "cancelled" or isinstance(exc, BudgetExceededError):
                # Shared acquisitions stay available to other jobs; preserved bytes are reused.
                self.store.finish_acquisition(
                    row["id"],
                    "queued",
                    "Stopped: " + exc.reason,
                    now=self.now(),
                    requests=fetcher.requests,
                    size=fetcher.bytes,
                )
                self.store.event(job_id, "acquisition", "Stopped: " + exc.reason, now=self.now())
                return
            attempts = int(row["attempts"]) + 1
            retry = exc.transient and attempts < 3 and exc.reason != "cancelled"
            self.store.finish_acquisition(
                row["id"],
                "queued" if retry else "failed",
                exc.reason,
                now=self.now(),
                requests=fetcher.requests,
                size=fetcher.bytes,
                next_attempt_at=self.now() + timedelta(minutes=5 * attempts) if retry else None,
            )
            self.store.event(
                job_id,
                "acquisition",
                f"{source.source_id}: {exc.reason}" + (" (will retry)" if retry else ""),
                now=self.now(),
            )
            return
        self.store.add_usage(job_id, http_requests=fetcher.requests, bytes=fetcher.bytes)
        detail = (
            f"{manifest['record_count']} records from {manifest['responses']} responses; "
            f"{manifest['refused']} refused"
        )
        self.store.finish_acquisition(
            row["id"],
            "completed",
            detail,
            now=self.now(),
            requests=fetcher.requests,
            size=fetcher.bytes,
            dataset_id=manifest["dataset_id"],
        )
        self.store.event(job_id, "acquisition", f"{source.source_id}: {detail}", now=self.now())

    # ----------------------------------------------------------- features
    def _featurize(self, job: dict[str, Any], request: ResearchRequest) -> None:
        """Materialize research features whose inputs are satisfied, then evaluate."""
        job_id = job["id"]
        family = self.family(request.family)
        entities = {e.entity: e for e in self.entities(job, family)}
        requirements = self.store.requirements(job_id)
        assessments = self.store.assessments(job_id)
        resolutions = self.store.resolutions(job_id)
        wanted: dict[str, set[str]] = defaultdict(set)
        for hypothesis_id, items in resolutions.items():
            for resolution in items:
                if resolution.feature_id:
                    wanted[resolution.feature_id].add(hypothesis_id)
        built = 0
        for feature_id, hypotheses in sorted(wanted.items()):
            definition = self.registry.get(feature_id)
            if definition.materializer != "research":
                continue
            for entity, info in entities.items():
                inputs = self._feature_inputs(definition, entity, requirements, assessments)
                if inputs is None:
                    continue
                datasets, records = inputs
                window = (requirements[0].start, requirements[0].end)
                rows = materialize(
                    definition,
                    entity=entity,
                    timezone=info.timezone,
                    schedule=family.schedule,
                    window=window,
                    inputs=records,
                )
                manifest = publish_feature(
                    self.store.root,
                    definition,
                    entity=entity,
                    schedule=family.schedule,
                    window=window,
                    input_datasets=datasets,
                    rows=rows,
                    created_at=self.now(),
                )
                self.store.register_feature(job_id, manifest, sorted(hypotheses), now=self.now())
                built += 1
        self.store.event(
            job_id, "features", f"{built} feature artifacts registered", now=self.now()
        )
        self.evaluate(job_id)
        self.store.transition(
            job_id,
            JobStatus.MODELING,
            "Assessing and fitting frozen hypothesis experiments",
            now=self.now(),
        )

    def _model(self, job: dict[str, Any], request: ResearchRequest) -> None:
        """One durable, bounded hypothesis experiment per worker step; never an order."""
        from entropytrade.research.modeling import (
            plan_hypothesis,
            run_hypothesis,
            verify_hypothesis,
        )

        job_id = job["id"]
        self._local_execution_inputs(job, request)
        artifacts = self.store.job_features(job_id)
        execution_datasets = tuple(
            sorted(
                {
                    row["dataset_id"]
                    for row in self.store.job_acquisitions(job_id, statuses=("completed",))
                    if row["dataset_id"]
                }
            )
        )
        fee_versions = FeeEvidenceStore(self.workspace).snapshot()
        prior = {row["id"]: row for row in self.store.experiments(job_id)}
        for hypothesis in self.store.hypotheses(job_id):
            if hypothesis["status"] == HypothesisStatus.DUPLICATE.value:
                continue
            spec = HypothesisSpec.model_validate(hypothesis["spec"])
            # One underlying market outcome cannot become training evidence by submitting
            # a new job, widening the window or renaming the mechanism/features.
            scope = scientific_hash({"family": spec.family})
            frozen = self.store.freeze_boundaries(scope, [], now=self.now())
            options: dict[str, Any] = {
                "root": self.store.root,
                "registry": self.registry,
                "spec": spec,
                "artifacts": artifacts,
                "validation_depth": request.validation_depth,
                "boundaries": tuple(date.fromisoformat(d) for d in frozen) if frozen else None,
                "execution_datasets": execution_datasets,
                "fee_versions": fee_versions,
            }
            plan = plan_hypothesis(**options)
            if not frozen and plan.get("boundaries") and plan.get("freeze_ready"):
                frozen = self.store.freeze_boundaries(
                    scope, list(plan["boundaries"]), now=self.now()
                )
                options["boundaries"] = tuple(date.fromisoformat(d) for d in frozen)
                plan = plan_hypothesis(**options)
            experiment_id = str(plan["experiment_id"])
            if experiment_id in prior and prior[experiment_id]["status"] in {
                "completed",
                "refused",
                "cancelled",
            }:
                cached_result = prior[experiment_id]["result"]
                if cached_result is not None:
                    try:
                        verified = verify_hypothesis(**options, expected_id=experiment_id)
                    except (OSError, ValueError, TypeError, KeyError) as exc:
                        self.store.invalidate_experiment(job_id, experiment_id, now=self.now())
                        raise StepError(
                            "Frozen experiment evidence or artifacts failed verification",
                            transient=False,
                            kind="ArtifactIntegrityError",
                        ) from exc
                    self._experiment_facets(job_id, hypothesis, experiment_id, verified)
                continue
            self.store.plan_experiment(
                job_id,
                experiment_id,
                spec.hypothesis_id,
                plan,
                now=self.now(),
            )
            if not self.store.start_experiment(job_id, experiment_id, now=self.now()):
                return
            self.store.event(job_id, "experiment", f"Fitting {experiment_id}", now=self.now())
            started = time.monotonic()
            spent = job["usage"]["runtime_seconds"] - job["checkpoint"].get("runtime_base", 0)

            def interrupted(started: float = started, spent: float = spent) -> bool:
                return (
                    self.stop.is_set()
                    or job_id in self.cancelled
                    or spent + time.monotonic() - started >= request.budget.max_runtime_seconds
                )

            try:
                result = run_hypothesis(**options, now=self.now(), cancelled=interrupted)
            except InterruptedError as exc:
                if self.stop.is_set():
                    # Leave the running checkpoint for startup recovery.
                    return
                if job_id in self.cancelled:
                    return
                self.store.finish_experiment(
                    job_id,
                    experiment_id,
                    status="failed",
                    error={"type": "BudgetExceeded", "reason": "Modeling runtime budget exhausted"},
                    now=self.now(),
                )
                raise StepError("Modeling runtime budget exhausted", transient=False) from exc
            except Exception as exc:
                # Persist a credential-free error, then use the existing retry budget.
                self.store.finish_experiment(
                    job_id,
                    experiment_id,
                    status="failed",
                    error={"type": type(exc).__name__, "reason": "Model fitting failed"},
                    now=self.now(),
                )
                raise StepError(
                    f"Model fitting failed ({type(exc).__name__})",
                    transient=True,
                    kind=type(exc).__name__,
                ) from exc
            finished = self.store.finish_experiment(
                job_id,
                experiment_id,
                status="completed"
                if result.get("status") in {"completed", "evaluated"}
                else "refused",
                result=result,
                now=self.now(),
            )
            if finished:
                self._experiment_facets(job_id, hypothesis, experiment_id, result)
                self.store.event(
                    job_id,
                    "experiment",
                    f"{experiment_id}: {result.get('status')}",
                    now=self.now(),
                )
            return
        self._settle(job, request)

    def _local_execution_inputs(self, job: dict[str, Any], request: ResearchRequest) -> None:
        """Consume verified immutable snapshots in this workspace, preserving source protection."""
        from entropytrade.research.local_evidence import local_execution_evidence

        copied = local_execution_evidence(
            self.workspace, now=self.now(), max_bytes=max(0, self.budget_left(job, request)[1])
        )
        if copied["imported_bytes"]:
            self.store.add_usage(job["id"], bytes=copied["imported_bytes"])
        for problem in copied["problems"]:
            self.store.event(job["id"], "local_evidence", problem["reason"], now=self.now())
            if problem["type"] == "SourceProtectionConflict":
                raise StepError(problem["reason"], transient=False, kind=problem["type"])
        if copied.get("block_modeling"):
            raise StepError(
                "Local execution evidence or inherited source protection could not be verified; "
                "inspect the local evidence events",
                transient=False,
                kind="LocalEvidenceRefused",
            )
        for family, boundaries in copied["inherited_boundaries"].items():
            retained = self.store.freeze_boundaries(
                scientific_hash({"family": family}), list(boundaries), now=self.now()
            )
            if any(
                existing > incoming for existing, incoming in zip(retained, boundaries, strict=True)
            ):
                raise StepError(
                    "Restored source protection predates existing research partitions; "
                    "a reviewed evidence epoch is required",
                    transient=False,
                    kind="SourceProtectionConflict",
                )
        for dataset_id in copied["dataset_ids"]:
            acquisition = self.store.plan_acquisition(
                dataset_id,
                "local-restored-execution",
                {"entity": "verified-local-snapshot"},
                status="queued",
                now=self.now(),
            )
            self.store.link_acquisition(
                job["id"], acquisition, "local-execution-evidence", "inherited"
            )
            self.store.finish_acquisition(
                acquisition,
                "completed",
                "Verified local snapshot; original receipt clocks retained",
                dataset_id=dataset_id,
                now=self.now(),
            )

    def _experiment_facets(
        self,
        job_id: str,
        hypothesis: dict[str, Any],
        experiment_id: str,
        result: dict[str, Any],
    ) -> None:
        facets = dict(hypothesis["facets"])
        facets["modeling"] = {
            "experiment_id": experiment_id,
            "status": result.get("status"),
            **result.get("eligibility", {}),
        }
        facets["backtest"] = result.get("backtest", {})
        hypothesis_status = HypothesisStatus(hypothesis["status"])
        reasons = list(hypothesis["reasons"])
        if hypothesis_status is HypothesisStatus.BACKTEST_ELIGIBLE and not result.get(
            "backtest", {}
        ).get("eligible", False):
            hypothesis_status = HypothesisStatus.INSUFFICIENT_EVIDENCE
            reasons.extend(result.get("eligibility", {}).get("reasons", []))
            reasons.extend(result.get("backtest", {}).get("reasons", []))
        self.store.set_hypothesis_status(
            job_id,
            hypothesis["hypothesis_id"],
            hypothesis_status,
            reasons,
            facets,
            now=self.now(),
        )

    def _settle(self, job: dict[str, Any], request: ResearchRequest) -> None:
        """Evidence waits stay durable after predictive modeling; no eligibility promotion."""
        job_id = job["id"]
        approved = self.store.job_acquisitions(job_id, statuses=("queued",))
        if approved and min(self.budget_left(job, request)) > 0:
            # Approved while features were being built: acquire before settling.
            self.store.transition(
                job_id, JobStatus.PLANNING, "Approved acquisitions are queued", now=self.now()
            )
            return
        pending = self.store.job_acquisitions(job_id, statuses=("awaiting_approval",))
        waiting = [f for f in self.store.job_forward(job_id) if f["status"] != "satisfied"]
        covered = [f for f in waiting if f["collector_status"] == "covered"]
        if pending:
            target, detail = (
                JobStatus.AWAITING_AUTHORIZATION,
                (f"{len(pending)} acquisitions await your approval; other work continued"),
            )
            next_run = None
        elif covered:
            target = JobStatus.AWAITING_OBSERVATIONS
            # Never schedule into the past: that would re-plan in a hot loop.
            next_run = max(
                min(datetime.fromisoformat(f["next_check_at"]) for f in covered),
                self.now() + timedelta(minutes=1),
            )
            detail = (
                f"Awaiting prospective evidence for {len(covered)} requirements; next "
                f"reevaluation {next_run.isoformat(timespec='minutes')}"
            )
        else:
            target, detail, next_run = JobStatus.EVALUATED, self.outcome_detail(job_id), None
        self.store.transition(job_id, target, detail, now=self.now(), next_run_at=next_run)

    def _feature_inputs(
        self,
        definition: FeatureDefinition,
        entity: str,
        requirements: list[DataRequirement],
        assessments: dict[str, Assessment],
    ) -> tuple[list[str], dict[str, list[dict[str, Any]]]] | None:
        """Records from verified research datasets for each input, or None if unmet."""
        names = (
            ["label"]
            if definition.transform == "label_value"
            else ["forecast", "observation"][: len(definition.inputs)]
        )
        datasets: list[str] = []
        records: dict[str, list[dict[str, Any]]] = {}
        for name, item in zip(names, definition.inputs, strict=True):
            match = next(
                (
                    r
                    for r in requirements
                    if r.kind is item.kind and r.variable == item.variable and r.entity == entity
                ),
                None,
            )
            assessment = assessments.get(match.requirement_id) if match else None
            if assessment is None or assessment.status is not AssessmentStatus.SATISFIED:
                return None
            ids = [d for d in assessment.datasets if d.startswith("sha256:")]
            loaded = []
            for dataset_id in ids:
                try:
                    loaded.extend(load_records(self.store.root, dataset_id))
                except FileNotFoundError:
                    continue
            if not loaded:
                return None
            datasets.extend(ids)
            records[name] = loaded
        return sorted(set(datasets)), records

    def requirement_state(
        self, job_id: str, requirement: DataRequirement, assessment: Assessment | None
    ) -> tuple[AssessmentStatus, str]:
        """Assessment status refined by discovery: acquiring, awaiting, or unobtainable."""
        if assessment is None:
            return AssessmentStatus.MISSING, "not yet assessed"
        if assessment.status is AssessmentStatus.SATISFIED:
            return assessment.status, assessment.reasons[0]
        links = self.store.requirement_acquisitions(job_id, requirement.requirement_id)
        if any(a["status"] in {"queued", "running"} for a in links):
            job = self.store.get_job(job_id)
            if (
                job
                and min(self.budget_left(job, ResearchRequest.model_validate(job["request"]))) <= 0
            ):
                return (
                    AssessmentStatus.MISSING,
                    "the job's acquisition budget ran out; resubmit with a larger budget",
                )
            return AssessmentStatus.ACQUIRING, "acquisition in progress"
        if any(a["status"] == "awaiting_approval" for a in links):
            return AssessmentStatus.AWAITING_AUTHORIZATION, "acquisition awaits your approval"
        forward = self.store.requirement_forward(job_id, requirement.requirement_id)
        if forward is not None:
            if forward["collector_status"] == "covered":
                return (
                    AssessmentStatus.AWAITING_OBSERVATIONS,
                    f"awaiting prospective collection ({forward['events_observed']} of "
                    f"{forward['events_required']} events); {forward['detail']}",
                )
            return AssessmentStatus.AWAITING_AUTHORIZATION, forward["detail"]
        decisions = self.store.source_decisions(job_id, requirement.requirement_id)
        if not links and any(d.decision == "acquire" for d in decisions):
            job = self.store.get_job(job_id)
            if job and job["request"].get("acquisition") == "none":
                return (
                    AssessmentStatus.MISSING,
                    "acquirable, but acquisition is disabled for this job",
                )
        if any(d.decision == "authorization_required" for d in decisions):
            reason = next(d for d in decisions if d.decision == "authorization_required").reasons
            return AssessmentStatus.AWAITING_AUTHORIZATION, "; ".join(reason)
        if any(a["status"] == "completed" for a in links):
            return assessment.status, assessment.reasons[0] + " after acquisition"
        failed = [a for a in links if a["status"] == "failed"]
        if failed:
            return AssessmentStatus.UNOBTAINABLE, "acquisition failed: " + failed[0]["detail"]
        if not decisions:
            return AssessmentStatus.UNOBTAINABLE, "no approved source provides this evidence"
        rejected = "; ".join(f"{d.source_id}: {', '.join(d.reasons)}" for d in decisions)
        return AssessmentStatus.UNOBTAINABLE, "no eligible source: " + rejected

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
                job_id, hypothesis_id, mine, assessments, resolutions.get(hypothesis_id, [])
            )
            self.store.set_hypothesis_status(
                job_id, hypothesis_id, status, reasons, facets, now=now
            )

    def classify(
        self,
        job_id: str,
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
        states = {
            r.requirement_id: self.requirement_state(job_id, r, assessments.get(r.requirement_id))
            for r in mine
        }
        reasons = [
            f"{r.purpose}: {states[r.requirement_id][1]}"
            for r in mine
            if states[r.requirement_id][0] is not AssessmentStatus.SATISFIED
        ]
        features = self.store.job_features(job_id)
        built = {
            f["feature_id"] for f in features if hypothesis_id in f["hypotheses"] and f["non_null"]
        }
        research_features = [
            r.feature_id
            for r in resolutions
            if r.feature_id and self.registry.get(r.feature_id).materializer == "research"
        ]
        facets["features_registered"] = sorted(built)
        facets["features_expected"] = sorted(research_features)
        kinds = {s for s, _ in states.values()}
        if AssessmentStatus.UNOBTAINABLE in kinds:
            result = HypothesisStatus.INSUFFICIENT_EVIDENCE
        elif AssessmentStatus.AWAITING_AUTHORIZATION in kinds:
            result = HypothesisStatus.AWAITING_AUTHORIZATION
        elif kinds & {AssessmentStatus.ACQUIRING, AssessmentStatus.MISSING}:
            result = HypothesisStatus.NEEDS_DATA
        elif AssessmentStatus.AWAITING_OBSERVATIONS in kinds:
            result = HypothesisStatus.AWAITING_OBSERVATIONS
        elif AssessmentStatus.PARTIAL in kinds:
            result = HypothesisStatus.INSUFFICIENT_EVIDENCE
            reasons.append("Extend the lookback or wait for more completed days, then reevaluate.")
        elif facets["unimplemented_features"] or set(research_features) - built:
            result = HypothesisStatus.NEEDS_DATA
        else:
            result = HypothesisStatus.BACKTEST_ELIGIBLE
        if facets["unimplemented_features"]:
            reasons.append(
                "Features without an implemented materializer: "
                + ", ".join(facets["unimplemented_features"])
            )
        return result, reasons, facets

    # ----------------------------------------------------------- approvals
    def approve(self, job_id: str, value: object) -> bool:
        if (
            not isinstance(value, dict)
            or set(value) != {"acquisition_id", "decision"}
            or value["decision"] not in {"approve", "deny"}
            or not isinstance(value["acquisition_id"], str)
        ):
            raise ValueError("provide acquisition_id and decision approve or deny")
        if not self.started():
            raise KeyError("research job not found")
        changed = self.store.decide_acquisition(
            job_id, value["acquisition_id"], approve=value["decision"] == "approve", now=self.now()
        )
        job = self.store.get_job(job_id)
        if changed and job and JobStatus(job["status"]) is JobStatus.AWAITING_AUTHORIZATION:
            self.store.transition(
                job_id,
                JobStatus.PLANNING,
                f"Acquisition {value['decision']}d by user",
                now=self.now(),
            )
        self.wake.set()
        return changed

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
            "sources": [
                {
                    "source_id": s.source_id,
                    "name": s.name,
                    "historical": s.historical,
                    "clock": s.clock,
                    "adapter": s.adapter is not None,
                    "point_in_time": s.point_in_time,
                }
                for s in self.sources.values()
            ],
            "transport": self.transport_label,
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
        """Sources, acquisitions, features and forward requests, with refined states."""
        job_id = job["id"]
        assessments = self.store.assessments(job_id)
        for row in job["requirements"]:
            requirement = DataRequirement.model_validate(
                {k: v for k, v in row.items() if k != "assessment"}
            )
            state, reason = self.requirement_state(
                job_id, requirement, assessments.get(requirement.requirement_id)
            )
            if row["assessment"] is not None:
                row["assessment"]["status"] = state.value
                if reason not in row["assessment"]["reasons"]:
                    row["assessment"]["reasons"] = [reason, *row["assessment"]["reasons"]]
        job["sources"] = [d.model_dump(mode="json") for d in self.store.source_decisions(job_id)]
        job["acquisitions"] = [
            {k: v for k, v in a.items() if k != "acquisition_key"}
            for a in self.store.job_acquisitions(job_id)
        ]
        job["features"] = self.store.job_features(job_id)
        job["experiments"] = self.store.experiments(job_id)
        job["forward_requests"] = decorate_forward(
            self.store.job_forward(job_id),
            self.store.requirements(job_id),
            assessments,
            self.now(),
        )
        job["transport"] = self.transport_label

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
