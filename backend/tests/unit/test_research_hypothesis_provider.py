"""Provider hypothesis generation: typed output, budgets, loopback-only local endpoints."""

import asyncio
import json
from decimal import Decimal
from typing import Any

import pytest
from pydantic_ai.exceptions import ModelHTTPError  # noqa: TID251
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart  # noqa: TID251
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: TID251
from pydantic_ai.usage import RequestUsage  # noqa: TID251

from entropytrade.agents.hypotheses import classify, propose
from entropytrade.agents.pricing import PricedResearchModel
from entropytrade.agents.provider import (
    LOCAL_URL_VARIABLE,
    ResearchCredentialError,
    local_endpoint,
)
from entropytrade.research.providers import provider_catalog

BATCH = {
    "hypotheses": [
        {
            "title": "Forecast bias at Philadelphia",
            "rationale": "Official forecasts may run warm against the settlement high.",
            "features": [{"name": "nws_pfm_max_f", "data_kinds": []}],
            "label": "settlement_high_f",
            "rules": [],
            "candidate_models": ["logistic"],
            "validation_plan": "Time-ordered partitions with an embargo.",
            "leakage_risks": ["Same-day reports"],
            "invalidation": ["No Brier improvement"],
            "proposed_sources": [],
        },
        {
            "title": "Revision momentum at Philadelphia",
            "rationale": "Prices may adjust slowly after a forecast revision is issued.",
            "features": [{"name": "nws_pfm_revision_f", "data_kinds": []}],
            "label": "settlement_high_f",
            "rules": [],
            "candidate_models": ["logistic"],
            "validation_plan": "Time-ordered partitions with an embargo.",
            "leakage_risks": ["Quotes after issuance"],
            "invalidation": ["Revision does not predict outcomes"],
            "proposed_sources": [],
        },
    ]
}


def test_prompted_provider_output_is_validated_and_hashed() -> None:
    seen: list[str] = []

    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        seen.append(str(messages[-1]))
        return ModelResponse(
            parts=[TextPart(json.dumps(BATCH))],
            usage=RequestUsage(cost=Decimal("0.0021"), input_tokens=900, output_tokens=400),
        )

    model = PricedResearchModel(FunctionModel(reply), stage=lambda: "hypotheses")
    result = asyncio.run(
        propose(
            objective="Find temperature strategies",
            context={"registered_features": ["nws_pfm_max_f"]},
            model=model,
            provider="gemini",
            budget_usd=Decimal("0.25"),
        )
    )
    assert result["status"] == "completed"
    assert len(result["proposals"]["hypotheses"]) == 2
    assert result["prompt_hash"].startswith("sha256:")
    assert result["cost_usd"] == "0.0021"
    assert result["usage"]["input_tokens"] == 900
    assert "Untrusted request and context" in seen[0]


def test_invalid_provider_output_is_not_repaired() -> None:
    def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart('{"hypotheses": [{"title": "too thin"}]}')])

    with pytest.raises(Exception) as caught:  # noqa: PT011 - classified below
        asyncio.run(
            propose(
                objective="Find temperature strategies",
                context={},
                model=PricedResearchModel(FunctionModel(reply), stage=lambda: "h", free=True),
                provider="openai_compatible",
                budget_usd=Decimal(0),
            )
        )
    failure = classify(caught.value)
    assert failure["transient"] is False
    assert "schema validation" in failure["reason"]


@pytest.mark.parametrize(
    ("exc", "transient"),
    [
        (ModelHTTPError(429, "model", body={"error": "secret-body"}), True),
        (ModelHTTPError(503, "model"), True),
        (ModelHTTPError(401, "model", body="sk-should-not-leak"), False),
        (TimeoutError(), True),
        (ResearchCredentialError("set KEY"), False),
        (RuntimeError("raw provider text with sk-123"), False),
    ],
)
def test_failures_are_classified_without_provider_text(exc: Exception, transient: bool) -> None:
    failure: dict[str, Any] = classify(exc)
    assert failure["transient"] is transient
    assert "sk-" not in json.dumps(failure)
    assert "secret-body" not in json.dumps(failure)


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("http://127.0.0.1:11434/v1", True),
        ("http://localhost:8000/v1/", True),
        ("https://api.example.com/v1", False),
        ("http://192.168.1.4:11434/v1", False),
        ("http://user:pass@127.0.0.1:11434/v1", False),
        ("", False),
    ],
)
def test_local_endpoint_must_be_loopback(
    monkeypatch: pytest.MonkeyPatch, url: str, ok: bool
) -> None:
    monkeypatch.setenv(LOCAL_URL_VARIABLE, url)
    if ok:
        assert local_endpoint() == url.rstrip("/")
    else:
        with pytest.raises(ResearchCredentialError):
            local_endpoint()


def test_catalog_reports_configuration_without_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-secret-value")
    monkeypatch.delenv("ENTROPYTRADE_RESEARCH_API_KEY", raising=False)
    catalog = {p["provider"]: p for p in provider_catalog()}
    assert catalog["gemini"]["configured"] is True
    assert catalog["anthropic"]["configured"] is False
    assert catalog["local_templates"]["configured"] is True
    assert "AIza-secret-value" not in json.dumps(catalog)
