"""Explicit research credentials and provider selection; construction sends no requests."""

import os
from typing import Literal

from pydantic import Field
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from entropytrade.domain.base import DomainModel

RESEARCH_KEY_VARIABLE = "ENTROPYTRADE_RESEARCH_API_KEY"


class ResearchCredentialError(ValueError):
    """The dedicated research credential was not supplied; ambient keys are ignored."""


class ResearchProviderConfig(DomainModel):
    """Serializable public configuration. Credentials are deliberately absent."""

    provider: Literal["openai", "anthropic"]
    model_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


def research_model(config: ResearchProviderConfig) -> Model:
    """Construct a provider model using only the dedicated research key.

    Does not opt into requests, mutate the fixture guard or use ambient SDK base URLs.
    A later isolated research worker must scope and budget actual provider calls.
    """
    key = os.environ.get(RESEARCH_KEY_VARIABLE, "").strip()
    if not key:
        raise ResearchCredentialError(f"set {RESEARCH_KEY_VARIABLE} for provider-backed research")
    if config.provider == "openai":
        selected = OpenAIProvider(api_key=key, base_url="https://api.openai.com/v1")
        selected.client.max_retries = 0
        return OpenAIChatModel(config.model_name, provider=selected)
    anthropic = AnthropicProvider(api_key=key, base_url="https://api.anthropic.com")
    anthropic.client.max_retries = 0
    return AnthropicModel(config.model_name, provider=anthropic)
