"""Provider construction is explicit, credential-isolated and request-free."""

import pytest

from entropytrade.agents.guard import provider_requests_blocked
from entropytrade.agents.provider import (
    PROVIDER_KEY_VARIABLES,
    RESEARCH_KEY_VARIABLE,
    ResearchProviderConfig,
    research_key,
    research_model,
)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_ambient_keys_cannot_enable_research(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(RESEARCH_KEY_VARIABLE, raising=False)
    for name in PROVIDER_KEY_VARIABLES[provider]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-ambient")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-ambient")
    config = ResearchProviderConfig.model_validate({"provider": provider, "model_name": "fixture"})
    with pytest.raises(ValueError, match=RESEARCH_KEY_VARIABLE):
        research_model(config)
    assert provider_requests_blocked()


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_provider_specific_research_key_wins_over_legacy(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = ResearchProviderConfig.model_validate({"provider": provider, "model_name": "fixture"})
    monkeypatch.setenv(RESEARCH_KEY_VARIABLE, "legacy-research-key")
    monkeypatch.setenv(PROVIDER_KEY_VARIABLES[provider][0], "specific-research-key")
    assert research_key(config) == "specific-research-key"
    assert provider_requests_blocked()


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_another_providers_research_key_cannot_authorize_call(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for names in PROVIDER_KEY_VARIABLES.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    other = "anthropic" if provider == "openai" else "openai"
    monkeypatch.setenv(PROVIDER_KEY_VARIABLES[other][0], "another-providers-research-key")
    config = ResearchProviderConfig.model_validate({"provider": provider, "model_name": "fixture"})
    with pytest.raises(ValueError, match=PROVIDER_KEY_VARIABLES[provider][0]):
        research_key(config)


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
