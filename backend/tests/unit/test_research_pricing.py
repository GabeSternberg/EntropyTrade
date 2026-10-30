"""Raw response boundaries refuse unknown pricing even inside provider continuations."""

import asyncio
from decimal import Decimal

import pytest
from pydantic_ai import Agent  # noqa: TID251
from pydantic_ai.messages import ModelResponse, TextPart  # noqa: TID251
from pydantic_ai.models import ModelRequestParameters  # noqa: TID251
from pydantic_ai.models.function import FunctionModel  # noqa: TID251
from pydantic_ai.usage import RequestUsage  # noqa: TID251

from entropytrade.agents.pricing import PricedResearchModel, ResearchPricingError


@pytest.mark.parametrize("priced_first", [False, True])
def test_unpriced_continuation_segment_cannot_be_merged_or_followed_by_a_request(
    priced_first: bool,
) -> None:
    replies = [
        ModelResponse(
            parts=[TextPart("CONTROLLED suspended response")],
            state="suspended",
            model_name="CONTROLLED-unpriced-model",
            usage=RequestUsage(input_tokens=100, output_tokens=100),
        )
    ]
    if priced_first:
        replies.insert(
            0,
            ModelResponse(
                parts=[TextPart("CONTROLLED priced suspended response")],
                state="suspended",
                model_name="CONTROLLED-priced-model",
                usage=RequestUsage(cost=Decimal("0.01"), input_tokens=100, output_tokens=100),
            ),
        )
    requests = 0

    def response(*_: object) -> ModelResponse:
        nonlocal requests
        requests += 1
        return replies[requests - 1]

    model = PricedResearchModel(FunctionModel(response), stage=lambda: "research")

    async def execute() -> None:
        with pytest.raises(ResearchPricingError):
            await Agent(model).run("CONTROLLED continuation pricing")
        # Refusal is sticky even if a caller tries again outside the agent loop.
        with pytest.raises(ResearchPricingError):
            await model.request([], None, ModelRequestParameters())

    asyncio.run(execute())
    assert requests == 1 + int(priced_first)
    assert model.observed_usage.requests == requests
    assert model.observed_usage.input_tokens == 100 * requests
    assert model.observed_usage.cost == (Decimal("0.01") if priced_first else None)
    assert model.responses[-1]["usage"]["cost"] is None
    assert model.refused


@pytest.mark.parametrize("cost", ["0", "0.01", "-0.01", "NaN", "Infinity"])
def test_explicit_response_cost_must_be_finite_and_nonnegative(cost: str) -> None:
    response = ModelResponse(
        parts=[TextPart("CONTROLLED explicitly priced response")],
        model_name="CONTROLLED-model-with-explicit-cost",
        usage=RequestUsage(cost=Decimal(cost), input_tokens=1, output_tokens=1),
    )
    model = PricedResearchModel(FunctionModel(lambda *_: response), stage=lambda: "research")
    if cost in {"0", "0.01"}:
        assert asyncio.run(model.request([], None, ModelRequestParameters())) is response
        assert not model.refused
        assert model.observed_usage.cost == Decimal(cost)
    else:
        with pytest.raises(ResearchPricingError):
            asyncio.run(model.request([], None, ModelRequestParameters()))
        assert model.refused
        assert model.observed_usage.cost is None
