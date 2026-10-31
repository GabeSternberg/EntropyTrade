"""Controlled OpenAI HTTP wire seam; never an external provider or empirical proof."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx2 as httpx
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: TID251
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: TID251

from entropytrade.agents import provider as provider_module
from entropytrade.agents.evidence import EvidenceQuery
from entropytrade.agents.fixture import operational_models


async def wire_research(
    original: Callable[..., Awaitable[dict[str, Any]]],
    *,
    case: str,
    calls: list[dict[str, Any]],
    timeout_seconds: float = 180,
    **kwargs: Any,
) -> dict[str, Any]:
    data, run_id = kwargs["evidence"], str(uuid4())
    kwargs.pop("run_id", None)
    for topic in ("coverage", "markets", "features", "models", "history"):
        data.inspect(EvidenceQuery.model_validate({"topic": topic}))
    outputs = [m.custom_output_args for m in operational_models(kwargs["prompt"], data, run_id)]
    original_timeout = asyncio.timeout
    research_deadline: asyncio.Timeout | None = None

    def capture_timeout(delay: float | None) -> asyncio.Timeout:
        nonlocal research_deadline
        deadline = original_timeout(delay)
        if research_deadline is None:
            assert delay == timeout_seconds
            research_deadline = deadline
        return deadline

    async def response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == "Bearer fixture-dedicated-key"
        if case == "deadline":
            # Expire the pipeline's actual timeout only once HTTP is in flight. A tiny
            # startup budget races schema construction and may never reach this seam.
            assert research_deadline is not None
            research_deadline.reschedule(asyncio.get_running_loop().time())
            try:
                await asyncio.Future[None]()
            finally:
                assert research_deadline.expired()
        if case == "slow":
            await asyncio.sleep(120)
        if case == "outage":
            return httpx.Response(503, json={"error": {"message": "fixture-dedicated-key"}})
        index = len(calls) - 1
        name = (
            "inspect_evidence"
            if index == 0
            else next(
                t["function"]["name"]
                for t in body["tools"]
                if t["function"]["name"] != "inspect_evidence"
            )
        )
        args = {"query": {"topic": "coverage"}} if index == 0 else outputs[index - 1]
        if case == "malformed" and index > 0:
            args = {"nonsense": "bad"}
        unpriced_index = (
            2
            if case == "unpriced_later_stage"
            else (1 if case.startswith("unpriced_second_") else 0)
        )
        unpriced = case.startswith("unpriced_") and index == unpriced_index
        if unpriced and case.endswith("retry"):
            name = next(
                t["function"]["name"]
                for t in body["tools"]
                if t["function"]["name"] != "inspect_evidence"
            )
            args = {"nonsense": "bad"}
        elif unpriced and case.endswith("tool"):
            name, args = "inspect_evidence", {"query": {"topic": "coverage"}}
        elif unpriced and case == "unpriced_output":
            name = next(
                t["function"]["name"]
                for t in body["tools"]
                if t["function"]["name"] != "inspect_evidence"
            )
            args = outputs[0]
        return httpx.Response(
            200,
            json={
                "id": f"controlled-{index}",
                "object": "chat.completion",
                "created": 1,
                "model": "CONTROLLED-model-without-pricing" if unpriced else "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"call-{index}",
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args)},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        selected = OpenAIProvider(api_key="fixture-dedicated-key", http_client=client)
        selected.client.max_retries = 0
        model = OpenAIChatModel("gpt-4.1-mini", provider=selected)
        with ExitStack() as stack:
            stack.enter_context(patch.object(provider_module, "research_model", return_value=model))
            if case == "deadline":
                stack.enter_context(
                    patch(
                        "entropytrade.agents.pipeline.asyncio.timeout", side_effect=capture_timeout
                    )
                )
            return await original(
                **kwargs,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
            )
