"""Run the four research agents, then backtest the specs both gates allow.

The window is never a holdout. Provider model requests are blocked before the
agents run. TestModel supplies the demo outputs; a live provider is not called.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.test import TestModel

from entropytrade.agents.deps import ResearchDeps
from entropytrade.agents.evidence import ResearchEvidence
from entropytrade.agents.fixture import (
    PROMPT,
    RUN_ID,
    WHEN,
    philadelphia_book,
    philadelphia_deps,
    philadelphia_records,
    philadelphia_settlements,
    philadelphia_window,
    scripted_models,
)
from entropytrade.agents.guard import block_provider_requests
from entropytrade.agents.outputs import CriticBatch, HypothesisDraft, QuantBatch, ResearchNote
from entropytrade.agents.provider import ResearchProviderConfig
from entropytrade.agents.team import critic_agent, hypothesis_agent, quant_agent, research_agent
from entropytrade.backtest.replay import run_replay
from entropytrade.domain.enums import ExecutionFidelity, FeeType, FillScenario, MarketResult
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.ids import content_hash
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.runs import (
    AgentResearchRun,
    BacktestRun,
    Hypothesis,
    ResearchReport,
    ResearchRunStatus,
    SampleSplit,
    SplitWindow,
)
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.strategies.interpret import UnsupportedSpecError, compile_strategy

if TYPE_CHECKING:
    from entropytrade.domain.base import DomainModel


_ZERO = Decimal(0)
Settlement = tuple[datetime, str, MarketResult]


class PipelineError(ValueError):
    """The run asked for something the research pipeline does not do."""


@dataclass(frozen=True)
class RejectedSpec:
    strategy_id: str
    spec_hash: str
    reason: str


@dataclass(frozen=True)
class RankedBacktest:
    strategy_id: str
    ending_equity: Decimal
    digest: str
    fill_ids: tuple[str, ...]


@dataclass(frozen=True)
class PipelineResult:
    prompt: str
    prompts: tuple[str, ...]
    tool_log: tuple[str, ...]
    run: AgentResearchRun
    rejected: tuple[RejectedSpec, ...]
    backtests: tuple[RankedBacktest, ...]

    def ranked_ids(self) -> tuple[str, ...]:
        ordered = sorted(self.backtests, key=lambda item: (-item.ending_equity, item.strategy_id))
        return tuple(item.strategy_id for item in ordered)

    def analyst_summary(self) -> str:
        """Rank from replay equity. The text is computed, not written by a model."""
        ranked = sorted(self.backtests, key=lambda item: (-item.ending_equity, item.strategy_id))
        lines = [f"prompt: {self.prompt}", "ranked by ending equity:"]
        lines.extend(
            f"{row.strategy_id} equity {row.ending_equity} fills {len(row.fill_ids)}"
            for row in ranked
        )
        lines.extend(f"rejected {item.strategy_id}: {item.reason}" for item in self.rejected)
        return "\n".join(lines)


def _output[T](
    agent: Agent[Any, T],
    prompt: str,
    *,
    model: TestModel,
    deps: ResearchDeps | None = None,
) -> T:
    return asyncio.run(agent.run(prompt, deps=deps, model=model)).output


def run_philadelphia_demo() -> PipelineResult:
    """Scripted Philadelphia run. No provider key and no holdout."""
    return run_pipeline(
        prompt=PROMPT,
        deps=philadelphia_deps(),
        records=philadelphia_records(),
        books=(philadelphia_book(),),
        settlements=philadelphia_settlements(),
        window=philadelphia_window(),
        models=scripted_models(),
        now=WHEN,
        run_id=RUN_ID,
    )


def run_pipeline(
    *,
    prompt: str,
    deps: ResearchDeps,
    records: Sequence[FeatureObservation],
    books: Sequence[OrderBook],
    settlements: Sequence[Settlement],
    window: SplitWindow,
    models: tuple[TestModel, TestModel, TestModel, TestModel],
    now: datetime,
    run_id: UUID,
) -> PipelineResult:
    """Research, then backtest. ``window`` must not be the holdout split."""
    block_provider_requests()
    if window.split is SampleSplit.HOLDOUT:
        raise PipelineError("holdout is not available to the research pipeline")
    research_model, hypothesis_model, quant_model, critic_model = models
    note = _output(research_agent, prompt, model=research_model, deps=deps)
    hypothesis_prompt = f"{prompt}\n\nResearch:\n{note.summary}"
    draft = _output(hypothesis_agent, hypothesis_prompt, model=hypothesis_model)
    quant_prompt = f"{hypothesis_prompt}\n\nHypothesis:\n{draft.statement}"
    batch = _output(quant_agent, quant_prompt, model=quant_model)
    spec_ids = "\n".join(spec.strategy_id for spec in batch.specs)
    critic_prompt = f"{quant_prompt}\n\nSpecs:\n{spec_ids}"
    critique = _output(critic_agent, critic_prompt, model=critic_model)
    prompts = (prompt, hypothesis_prompt, quant_prompt, critic_prompt)
    rejected, backtests = _backtest_accepted(
        batch,
        critique,
        records=records,
        books=books,
        settlements=settlements,
        window=window,
        now=ensure_utc(now),
    )
    finished = ensure_utc(now)
    run = AgentResearchRun(
        run_id=run_id,
        user_prompt=prompt,
        model="test",
        status=ResearchRunStatus.COMPLETED,
        started_at=finished,
        finished_at=finished,
        report=_report(note, draft, run_id=run_id, now=finished),
        strategy_spec_hashes=tuple(spec.spec_hash() for spec in batch.specs),
    )
    return PipelineResult(
        prompt=prompt,
        prompts=prompts,
        tool_log=tuple(deps.tool_log),
        run=run,
        rejected=rejected,
        backtests=backtests,
    )


def _report(
    note: ResearchNote,
    draft: HypothesisDraft,
    *,
    run_id: UUID,
    now: datetime,
) -> ResearchReport:
    return ResearchReport(
        run_id=run_id,
        summary=note.summary,
        hypotheses=(Hypothesis(hypothesis_id="phl-1", statement=draft.statement, created_at=now),),
        uncertainties=note.uncertainties,
        suggested_sources=note.suggested_sources,
        created_at=now,
    )


def _backtest_accepted(
    batch: QuantBatch,
    critique: CriticBatch,
    *,
    records: Sequence[FeatureObservation],
    books: Sequence[OrderBook],
    settlements: Sequence[Settlement],
    window: SplitWindow,
    now: datetime,
) -> tuple[tuple[RejectedSpec, ...], tuple[RankedBacktest, ...]]:
    reasons = {item.strategy_id: item for item in critique.judgements}
    rejected: list[RejectedSpec] = []
    ranked: list[RankedBacktest] = []
    for spec in batch.specs:
        judgement = reasons.get(spec.strategy_id)
        if judgement is None or not judgement.accept:
            reason = "critic did not accept this spec" if judgement is None else judgement.reason
            rejected.append(RejectedSpec(spec.strategy_id, spec.spec_hash(), reason))
            continue
        try:
            strategy = compile_strategy(spec)
        except UnsupportedSpecError as exc:
            rejected.append(RejectedSpec(spec.strategy_id, spec.spec_hash(), str(exc)))
            continue
        ledger = Ledger(Decimal("100"), as_of=window.start)
        result = run_replay(
            books=books,
            records=records,
            strategy=strategy,
            ledger=ledger,
            broker=PaperBroker(ledger, _schedule()),
            engine=RiskEngine(_limits()),
            latency=timedelta(0),
            window=window,
            settlements=settlements,
        )
        ranked.append(
            RankedBacktest(
                strategy_id=spec.strategy_id,
                ending_equity=result.ending_equity,
                digest=result.digest(_provenance(spec, window, now)),
                fill_ids=result.fill_ids,
            )
        )
    return tuple(rejected), tuple(ranked)


def _schedule() -> FeeSchedule:
    return FeeSchedule(
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
        maker_pays=False,
        quadratic_coefficient=_ZERO,
    )


def _limits() -> RiskLimits:
    return RiskLimits(
        bankroll=Decimal("100"),
        per_trade=Decimal("100"),
        per_event=Decimal("100"),
        total_deployed=Decimal("100"),
        max_loss=Decimal("50"),
        max_drawdown=Decimal("50"),
        max_book_age_seconds=3600,
        min_liquidity=Decimal("1.00"),
        max_spread=Decimal("0.2000"),
        config_version="v1",
    )


def _provenance(spec: StrategySpec, window: SplitWindow, now: datetime) -> BacktestRun:
    return BacktestRun(
        strategy_id=spec.strategy_id,
        strategy_version=spec.version,
        strategy_spec_hash=spec.spec_hash(),
        config_hash=content_hash({"fee_coefficient": "0", "latency_seconds": "0"}),
        dataset_manifest_hash=content_hash({"dataset": "philadelphia-fixture-v1"}),
        feature_version="fixture-v1",
        fee_model=FeeModelRef(
            version="fixture",
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            effective_from=window.start,
        ),
        execution_model_version="paper-v1",
        fill_scenario=FillScenario.BASE,
        execution_fidelity=ExecutionFidelity.ORDER_BOOK,
        random_seed=0,
        start=window.start,
        end=window.end,
        splits=(window,),
        created_at=now,
    )


# Operational research reuses this package's PydanticAI agents, schemas and registry.
# It deliberately never enters _backtest_accepted or promotes a strategy lifecycle.
async def run_research(
    *,
    prompt: str,
    evidence: ResearchEvidence,
    provider: ResearchProviderConfig | None,
    registry_path: Path,
    output: Path,
    offline: bool = False,
    enable_provider: bool = False,
    models: tuple[Model, ...] | None = None,
    local_templates: bool = False,
    run_id: str | None = None,
    timeout_seconds: float = 180,
    progress: Callable[[str, str], None] | None = None,
    stage_complete: Callable[[dict[str, Any]], None] | None = None,
    redact: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    import json
    from dataclasses import asdict
    from importlib.metadata import version
    from pathlib import Path
    from uuid import uuid4

    from pydantic_ai.exceptions import ModelHTTPError
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.usage import RunUsage, UsageLimits
    from pydantic_core import to_jsonable_python

    from entropytrade.agents.evidence import EvidenceQuery
    from entropytrade.agents.guard import research_requests
    from entropytrade.agents.outputs import (
        CandidateBatch,
        EvidenceNote,
        HypothesisBatch,
        ResearchCritique,
    )
    from entropytrade.agents.pricing import PricedResearchModel, ResearchPricingError
    from entropytrade.agents.provider import (
        ResearchCredentialError,
        gemini_bad_request_reason,
        research_model,
    )
    from entropytrade.agents.team import (
        RESEARCH_INSTRUCTIONS_VERSION,
        operational_agent,
    )
    from entropytrade.agents.validation import analyst_report, validate_candidates
    from entropytrade.data.sources import file_hash
    from entropytrade.domain.time import utc_now
    from entropytrade.features.registry import scientific_hash
    from entropytrade.strategy_registry.store import Registry

    if not prompt.strip() or len(prompt) > 6000:
        raise ValueError("research prompt must have 1-6000 characters")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("research timeout must be in (0,300] seconds")
    if not offline and not enable_provider:
        raise ValueError("real research requires explicit --enable-provider")
    if offline and enable_provider:
        raise ValueError("offline and provider opt-in are mutually exclusive")
    if local_templates and (not offline or models is not None or provider is not None):
        raise ValueError("local templates require offline mode without provider or injected models")
    if models is not None and (
        not offline
        or len(models) != 4
        or any(not isinstance(m, TestModel | FunctionModel) for m in models)
    ):
        raise ValueError(
            "injected models are restricted to four offline TestModel/FunctionModel fixtures"
        )
    registry_path = Path(registry_path)
    output = Path(output)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    identifier = str(UUID(run_id)) if run_id else str(uuid4())
    # IDs are UUIDs, never agent-selected filesystem paths.
    UUID(identifier)
    result: dict[str, Any] = {
        "run_id": identifier,
        "prompt": prompt,
        "started_at": utc_now().isoformat(),
        "mode": "local_templates" if local_templates else "offline_mock" if offline else "provider",
        "status": "started",
        "provider": provider.model_dump(mode="json") if provider else None,
        "instruction_version": RESEARCH_INSTRUCTIONS_VERSION,
        "pydantic_ai_version": version("pydantic-ai-slim"),
        "code": {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")},
        "coverage": evidence.coverage,
        "current_sources": evidence.current_sources,
        "models": evidence.models,
        "hypotheses": [],
        "candidates": [],
        "decisions": [],
        "stages": [],
        "limits": {
            "cost_limit_usd": "2.00" if not offline else None,
            "requests": 16,
            "tool_calls": 24,
            "max_output_tokens_per_request": 3500,
            "input_tokens": 90000,
            "output_tokens": 14000,
            "timeout_seconds": timeout_seconds,
        },
    }
    registry = Registry(registry_path)
    request_hash = scientific_hash(
        {
            "prompt": prompt,
            "mode": result["mode"],
            "provider": result["provider"],
            "coverage": result["coverage"],
            **({"current_sources": evidence.current_sources} if evidence.current_sources else {}),
            "model_diagnostics": result["models"],
            "instruction_version": RESEARCH_INSTRUCTIONS_VERSION,
            "code": result["code"],
            "protection": evidence.config.holdout_start.isoformat(),
            "limits": result["limits"],
        }
    )
    result["request_hash"] = request_hash
    old = registry.agent_run(identifier)
    if old is not None:
        registry.close()
        cached: dict[str, Any] = json.loads(old)
        if cached["request_hash"] != request_hash:
            raise ValueError("research run ID reused for different inputs")
        _write_research_artifacts(output / identifier, cached)
        return cached
    usage = RunUsage()
    priced_model: PricedResearchModel | None = None
    gemini = not offline and provider is not None and provider.provider == "gemini"
    bootstrap_limits = {"history": 1}
    if gemini and evidence.current_sources:
        # Current contracts already provide rules. Limit the repeated historical sample
        # so later stages can fit within the same token budget.
        bootstrap_limits["markets"] = 3
    try:
        initial = [
            evidence.inspect_for_role(
                EvidenceQuery(topic=topic, limit=bootstrap_limits.get(topic, 10)), role="bootstrap"
            )
            for topic in ("coverage", "markets", "features", "models", "history")
        ]
        template_outputs = None
        if local_templates:
            from entropytrade.agents.templates import formulate_templates

            template_outputs = formulate_templates(prompt, evidence, identifier)
        elif offline and models is None:
            from entropytrade.agents.fixture import operational_models

            models = operational_models(prompt, evidence, identifier)
        if not offline:
            if provider is None:
                raise ValueError("explicit provider/model configuration is required")
            actual = research_model(provider)
            priced_model = PricedResearchModel(actual, stage=lambda: str(result["active_stage"]))
            result["responses"] = priced_model.responses
            result["model_request_failures"] = priced_model.request_failures
            models = (priced_model,) * 4
        limits = UsageLimits(
            cost_limit=None if offline else Decimal("2.00"),
            request_limit=16,
            tool_calls_limit=24,
            input_tokens_limit=90000,
            output_tokens_limit=14000,
        )
        context: dict[str, Any] = {
            "user_request": prompt,
            "research_run_id": identifier,
            "research_timestamp": result["started_at"],
            "retrieved_evidence": initial,
        }
        if models is None and template_outputs is None:
            raise ValueError("no research models were configured")
        roles: tuple[tuple[str, type[DomainModel], str], ...] = (
            (
                "research",
                EvidenceNote,
                "Inspect evidence using the tool, then explain markets, mechanisms, "
                "limitations and citations.",
            ),
            (
                "hypothesis",
                HypothesisBatch,
                "Generate 2-6 distinct falsifiable mechanisms responsive to the "
                "request, with required variables, tests and falsification "
                "criteria. Avoid threshold-only variants.",
            ),
            (
                "quant",
                CandidateBatch,
                "Make one candidate per hypothesis. Use complete StrategySpecs only "
                "where faithful. Preserve unsupported research proposals with "
                "missing_capability. Use current feature names and actual "
                "universes. Never invent a model artifact.",
            ),
            (
                "critic",
                ResearchCritique,
                "Evaluate every full candidate and hypothesis against all evidence. "
                "Check clocks, settlement sources, correlated outcomes, repeated "
                "searches, unsupported semantics and fills. Exactly one verdict per "
                "candidate, with reasons.",
            ),
        )
        with research_requests(enabled=not offline):
            async with asyncio.timeout(timeout_seconds):
                for index, (role, schema, instruction) in enumerate(roles):
                    result["active_stage"] = role
                    stage_started = utc_now()
                    stage_timer = time.monotonic()
                    if progress is not None:
                        progress(f"research_{role}", f"Bounded research: {role}")
                    # Gemini can reject the nested StrategySpec as a tool declaration.
                    # Prompt for JSON and retain PydanticAI's local CandidateBatch validation.
                    agent = operational_agent(
                        schema, role=role, prompted_output=gemini and role == "quant"
                    )
                    if role == "research" and evidence.current_sources:
                        instruction += (
                            " Call inspect_evidence for both current_markets and weather before "
                            "returning. Cite both responses, including any source failure. Compare "
                            "forecasts and rules for matching dates. A full-day hourly maximum is "
                            "a proxy. Partial maxima represent only the hours covered."
                        )
                    message = (
                        instruction
                        + "\n\nUntrusted request and evidence:\n"
                        + json.dumps(context, sort_keys=True)
                    )
                    if len(message) > 100_000:
                        raise ValueError("research context exceeds character budget")
                    before = len(evidence.calls)
                    returned_models: list[dict[str, Any]]
                    if template_outputs is not None:
                        if index == 0:
                            evidence.inspect(EvidenceQuery(topic="coverage", limit=1))
                        payload = template_outputs[index].model_dump(mode="json")
                        returned_models = []
                    else:
                        if models is None:
                            raise ValueError("no research models were configured")
                        outcome = await agent.run(
                            message,
                            deps=evidence,
                            model=models[index],
                            usage=usage,
                            usage_limits=limits,
                            model_settings={
                                "max_tokens": 3500,
                                "timeout": 30,
                                "parallel_tool_calls": False,
                            },
                        )
                        from pydantic_ai.messages import ModelResponse

                        returned_models = [
                            {
                                "model_name": m.model_name,
                                "provider_name": m.provider_name,
                                "provider_response_id": m.provider_response_id,
                            }
                            for m in outcome.all_messages()
                            if isinstance(m, ModelResponse)
                        ]
                        payload = outcome.output.model_dump(mode="json")
                    if index == 0 and len(evidence.calls) == before:
                        raise ValueError("research agent must inspect evidence through a tool")
                    seen = {entry["evidence_id"] for entry in evidence.calls}
                    if index == 0 and not set(payload["evidence_ids"]) <= seen:
                        raise ValueError("research note contains an unretrieved citation")
                    if index == 0 and evidence.current_sources:
                        cited_topics = {
                            c["query"]["topic"]
                            for c in evidence.calls[before:]
                            if c["evidence_id"] in payload["evidence_ids"]
                        }
                        if not set(evidence.current_sources) <= cited_topics:
                            raise ValueError("research note must cite both current source results")
                    context[role] = payload
                    context["retrieved_evidence"] = evidence.calls
                    result["stages"].append(
                        {
                            "role": role,
                            "started_at": stage_started.isoformat(),
                            "finished_at": utc_now().isoformat(),
                            "latency_ms": (time.monotonic() - stage_timer) * 1000,
                            "returned_models": returned_models,
                            "prompt_hash": scientific_hash(message),
                            "prompt": message,
                            "output": payload,
                        }
                    )
                    if stage_complete:
                        stage_complete(result["stages"][-1])
                note, hypotheses, candidates, critique = (context[r[0]] for r in roles)
                result["note"] = note
                result["hypotheses"] = hypotheses["hypotheses"]
                result["candidates"] = candidates["candidates"]
                result["active_stage"] = "deterministic_validation"
                result["decisions"] = validate_candidates(
                    CandidateBatch.model_validate(candidates),
                    HypothesisBatch.model_validate(hypotheses),
                    ResearchCritique.model_validate(critique),
                    evidence,
                    run_id=identifier,
                )
                for decision in result["decisions"]:
                    decision["previous_search_count"] = registry.hypothesis_count(
                        decision["hypothesis_signature"]
                    )
                    decision["previously_searched"] |= decision["previous_search_count"] > 0
                result["status"] = "completed"
                result["report"] = analyst_report(result)
    except Exception as exc:  # noqa: BLE001 - durable failure boundary; never retry/fake success
        # Never persist provider exceptions/messages: they may contain request bodies or
        # credentials.
        result["status"] = "failed"
        if isinstance(exc, ResearchPricingError) and priced_model is not None:
            # The refusing wrapper raises before PydanticAI commits the response usage.
            # Preserve every observed request/token and only the known cost subtotal.
            priced_model.observed_usage.tool_calls = usage.tool_calls
            usage = priced_model.observed_usage
        result["failure"] = {
            "type": type(exc).__name__,
            "stage": result.get("active_stage", "setup"),
            "reason": (
                "Dedicated research credential is missing; ambient keys are never used."
                if isinstance(exc, ResearchCredentialError)
                else "Research deadline exceeded; no fallback or experiment was run."
                if isinstance(exc, TimeoutError)
                else "Provider response pricing is unavailable; further research requests "
                "were refused. Reported cost is only a known subtotal. "
                "No fallback or experiment was run."
                if isinstance(exc, ResearchPricingError)
                else "Research provider/configuration/budget/evidence failure; "
                "inspect the failure type and stage. No fallback or experiment was run."
            ),
        }
        if isinstance(exc, ModelHTTPError):
            result["failure"]["http_status"] = exc.status_code
            if gemini and exc.status_code == 400:
                result["failure"]["reason"] = gemini_bad_request_reason(exc.body)
        result["report"] = (
            "Research failed ("
            + type(exc).__name__
            + "). No candidates validated. "
            + result["failure"]["reason"]
        )
    finally:
        if result["status"] == "started":
            result["status"] = "failed"
            result["report"] = "Research interrupted; no candidates validated."
        result["finished_at"] = utc_now().isoformat()
        result["tool_calls"] = evidence.calls
        result["tool_activity"] = evidence.tool_activity
        result["pricing_status"] = (
            "unavailable"
            if priced_model is not None and priced_model.refused
            else "available"
            if priced_model is not None and priced_model.observed_usage.cost is not None
            else "not_observed"
        )
        result["usage"] = to_jsonable_python(asdict(usage))
        if redact:
            result = redact(result)
        payload_text = json.dumps(result, sort_keys=True, allow_nan=False)
        try:
            registry.record_agent_run(identifier, payload_text)
        finally:
            registry.close()
        _write_research_artifacts(output / identifier, result)
    return result


def _write_research_artifacts(destination: Path, result: dict[str, Any]) -> None:
    import json

    from entropytrade.data.sources import file_hash

    destination.mkdir(exist_ok=True)
    for name, text in (
        ("run.json", json.dumps(result, sort_keys=True, allow_nan=False)),
        ("report.md", result["report"]),
    ):
        temporary = destination / (name + ".tmp")
        temporary.write_text(text)
        temporary.replace(destination / name)
    temporary = destination / "checksums.json.tmp"
    temporary.write_text(
        json.dumps(
            {name: file_hash(destination / name) for name in ("run.json", "report.md")},
            sort_keys=True,
        )
    )
    temporary.replace(destination / "checksums.json")
