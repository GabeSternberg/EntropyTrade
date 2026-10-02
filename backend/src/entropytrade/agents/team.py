"""The four research agents. Tools can list forecasts and books. None can submit an order."""

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from entropytrade.agents.deps import ResearchDeps
from entropytrade.agents.outputs import CriticBatch, HypothesisDraft, QuantBatch, ResearchNote

research_agent: Agent[ResearchDeps, ResearchNote] = Agent(
    TestModel(),
    deps_type=ResearchDeps,
    output_type=ResearchNote,
    name="research",
    instructions=(
        "Describe only sources you were given. Do not invent a settlement value. "
        "Do not propose an order."
    ),
)


@research_agent.tool
def list_forecasts(ctx: RunContext[ResearchDeps]) -> list[dict[str, str]]:
    """Return forecast vintages. Settlement labels are not available here."""
    ctx.deps.tool_log.append("list_forecasts")
    return list(ctx.deps.forecast_rows())


@research_agent.tool
def list_books(ctx: RunContext[ResearchDeps]) -> list[dict[str, str]]:
    """Return displayed bid and ask. This does not place an order."""
    ctx.deps.tool_log.append("list_books")
    return list(ctx.deps.book_rows())


hypothesis_agent: Agent[None, HypothesisDraft] = Agent(
    TestModel(),
    output_type=HypothesisDraft,
    name="hypothesis",
    instructions="Write one falsifiable statement. Do not propose an order.",
)

quant_agent: Agent[None, QuantBatch] = Agent(
    TestModel(),
    output_type=QuantBatch,
    name="quant",
    instructions=("Emit StrategySpec values. Do not emit Python. Do not include an order tool."),
)

critic_agent: Agent[None, CriticBatch] = Agent(
    TestModel(),
    output_type=CriticBatch,
    name="critic",
    instructions=(
        "Accept or reject each spec. Rejection skips the backtest. You cannot approve live capital."
    ),
)
