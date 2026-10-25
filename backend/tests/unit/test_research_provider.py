"""Provider construction is explicit, credential-isolated and request-free."""

import pytest

from entropytrade.agents.guard import provider_requests_blocked
from entropytrade.agents.provider import (
    RESEARCH_KEY_VARIABLE,
    ResearchProviderConfig,
    research_model,
)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_ambient_keys_cannot_enable_research(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(RESEARCH_KEY_VARIABLE, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-ambient")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-ambient")
    config = ResearchProviderConfig.model_validate({"provider": provider, "model_name": "fixture"})
    with pytest.raises(ValueError, match=RESEARCH_KEY_VARIABLE):
        research_model(config)
    assert provider_requests_blocked()


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_constructing_provider_keeps_guard_and_configuration_secret_free(
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(RESEARCH_KEY_VARIABLE, "fixture-dedicated-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://invalid.example")
    config = ResearchProviderConfig.model_validate({"provider": provider, "model_name": "fixture"})
    model = research_model(config)
    assert model.model_name == "fixture"
    assert "fixture-dedicated-key" not in config.model_dump_json()
    assert provider_requests_blocked()
