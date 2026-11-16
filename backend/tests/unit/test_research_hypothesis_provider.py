"""Provider hypothesis generation: typed output, budgets, loopback-only local endpoints."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
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
    PROVIDER_KEY_VARIABLES,
    ResearchCredentialError,
    local_endpoint,
    local_model,
)
from entropytrade.research.providers import provider_catalog
from entropytrade.research.service import ResearchService
from entropytrade.research.worker import provider_environment

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
    monkeypatch.delenv("ENTROPYTRADE_RESEARCH_ANTHROPIC_API_KEY", raising=False)
    catalog = {p["provider"]: p for p in provider_catalog()}
    assert catalog["gemini"]["configured"] is True
    assert catalog["anthropic"]["configured"] is False
    assert catalog["local_templates"]["configured"] is True
    assert "AIza-secret-value" not in json.dumps(catalog)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_specific_provider_key_configures_catalog_and_worker_only_for_that_provider(
    provider: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for names in PROVIDER_KEY_VARIABLES.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    other = "anthropic" if provider == "openai" else "openai"
    key = PROVIDER_KEY_VARIABLES[provider][0]
    monkeypatch.setenv(key, "specific-secret")
    monkeypatch.setenv("KALSHI_PRIVATE_KEY_PATH", "/private/never-forward")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-secret")
    catalog = {p["provider"]: p for p in provider_catalog()}
    assert catalog[provider]["configured"] is True
    assert catalog[other]["configured"] is False
    assert catalog[provider]["live_verified"] is False
    assert "specific-secret" not in json.dumps(catalog)
    selected = provider_environment(tmp_path, tmp_path, provider)
    assert selected[key] == "specific-secret"
    unselected = provider_environment(tmp_path, tmp_path, other)
    assert key not in unselected
    assert "OPENAI_API_KEY" not in selected
    assert "KALSHI_PRIVATE_KEY_PATH" not in selected


def test_invalid_local_url_is_not_reported_as_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LOCAL_URL_VARIABLE, "https://external.example/v1")
    catalog = {p["provider"]: p for p in provider_catalog()}
    assert catalog["openai_compatible"]["configured"] is False


def test_local_provider_disables_proxy_and_redirect_escapes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LOCAL_URL_VARIABLE, "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("HTTP_PROXY", "http://external.example:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://external.example:8080")
    monkeypatch.setenv("ALL_PROXY", "http://external.example:8080")
    environment = provider_environment(tmp_path, tmp_path, "openai_compatible")
    assert not {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"} & environment.keys()
    model = local_model("fixture-no-request")
    assert model.client._client.follow_redirects is False  # type: ignore[attr-defined]
    assert model.client._client.trust_env is False  # type: ignore[attr-defined]
    asyncio.run(model.client.close())  # type: ignore[attr-defined]


@pytest.mark.parametrize("provider", ["gemini", "openai", "anthropic"])
def test_real_worker_missing_credential_fails_persistently_without_templates(
    provider: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in PROVIDER_KEY_VARIABLES[provider]:
        monkeypatch.delenv(name, raising=False)
    repo = Path(__file__).resolve().parents[3]
    service = ResearchService(tmp_path, repo)
    job_id = service.submit(
        {
            "objective": "Test forecast calibration for Philadelphia temperature markets",
            "family": "weather",
            "acquisition": "none",
            "provider": {"provider": provider, "model_name": "fixture-no-request"},
        }
    )["id"]
    service.run_until_idle()
    job = service.detail(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert job["error"]["type"] == "ResearchCredentialError"
    assert job["hypotheses"] == []
    assert job["usage"]["ai_usd"] == "0"
    assert job["submission_enabled"] is False
    restarted = ResearchService(tmp_path, repo)
    restarted.recover()
    assert restarted.detail(job_id)["status"] == "failed"  # type: ignore[index]
