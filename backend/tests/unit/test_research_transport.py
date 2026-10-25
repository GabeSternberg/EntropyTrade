"""Genuine OpenAI/PydanticAI serialization through an HTTP mock, with no external call."""

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2 as httpx
import pytest
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: TID251
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: TID251

from entropytrade.agents import provider as provider_module
from entropytrade.agents.evidence import EvidenceConfig, EvidenceQuery, ResearchEvidence
from entropytrade.agents.fixture import operational_models
from entropytrade.agents.guard import provider_requests_blocked
from entropytrade.agents.pipeline import run_research
from entropytrade.agents.provider import ResearchProviderConfig


@pytest.mark.parametrize("fail", [False, True])
def test_provider_adapter_consumes_evidence_and_handles_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    data = ResearchEvidence(
        EvidenceConfig.model_validate_json(Path("configs/research/weather.json").read_text())
    )
    for topic in ("coverage", "markets", "features", "models", "history"):
        data.inspect(EvidenceQuery.model_validate({"topic": topic}))
    identifier = str(uuid4())
    models = operational_models("disagreement", data, identifier)
    outputs = [m.custom_output_args for m in models]
    calls: list[dict[str, Any]] = []

    def response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.host == "api.openai.com"
        if fail:
            return httpx.Response(503, json={"error": {"message": "fixture provider unavailable"}})
        args: Any
        index = len(calls) - 1
        if index == 0:
            name = "inspect_evidence"
            args = {"query": {"topic": "coverage"}}
        else:
            name = next(
                t["function"]["name"]
                for t in body["tools"]
                if t["function"]["name"] != "inspect_evidence"
            )
            args = outputs[index - 1]
        return httpx.Response(
            200,
            json={
                "id": "mock-provider-response",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-4.1-mini",
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

    async def execute() -> dict[str, Any]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            provider = OpenAIProvider(api_key="fixture-not-a-real-key", http_client=client)
            provider.client.max_retries = 0
            model = OpenAIChatModel("gpt-4.1-mini", provider=provider)
            monkeypatch.setattr(provider_module, "research_model", lambda _: model)
            return await run_research(
                prompt="Investigate Philadelphia model disagreement and missing evidence",
                evidence=data,
                provider=ResearchProviderConfig(provider="openai", model_name="gpt-4.1-mini"),
                registry_path=tmp_path / "registry.sqlite",
                output=tmp_path / "runs",
                enable_provider=True,
                run_id=identifier,
            )

    result = asyncio.run(execute())
    assert provider_requests_blocked()
    assert "fixture-not-a-real-key" not in json.dumps(result)
    if fail:
        assert result["status"] == "failed"
        assert len(calls) == 1
        assert result["decisions"] == []
    else:
        assert result["status"] == "completed"
        assert result["mode"] == "provider"
        assert len(calls) == 5
        # The real provider adapter serialized actual tool results and the arbitrary prompt.
        assert "eligible_events" in json.dumps(calls[1]["messages"])
        assert any(m.get("role") == "tool" for m in calls[1]["messages"])
        assert "model disagreement" in json.dumps(calls[-1]["messages"])
        assert "minimum_edge" in json.dumps(calls[-1]["messages"])
        assert [d["status"] for d in result["decisions"]][:2] == ["INSUFFICIENT_DATA"] * 2
