"""Run the four research agents, then backtest the specs both gates allow.

The window is never a holdout. Provider model requests are blocked before the
agents run. TestModel supplies the demo outputs; a live provider is not called.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from entropytrade.agents.deps import ResearchDeps
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
