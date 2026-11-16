"""Explicit research credentials and provider selection; construction sends no requests."""

import os
from typing import Literal

from google.genai.types import HttpRetryOptions
from pydantic import Field
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from entropytrade.domain.base import DomainModel

RESEARCH_KEY_VARIABLE = "ENTROPYTRADE_RESEARCH_API_KEY"
GEMINI_KEY_VARIABLE = "GEMINI_API_KEY"


class ResearchCredentialError(ValueError):
    """The dedicated research credential was not supplied; ambient keys are ignored."""


class ResearchProviderConfig(DomainModel):
    """Serializable public configuration. Credentials are deliberately absent."""

    provider: Literal["openai", "anthropic", "gemini"]
    model_name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


def gemini_bad_request_reason(body: object) -> str:
    """Map a provider diagnostic to fixed text safe to display or save."""
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    detail = message.casefold() if isinstance(message, str) else ""
    if "api key" in detail:
        return "Gemini rejected the API key. Check the key in Google AI Studio and try again."
    if "schema" in detail:
        return "Gemini rejected the request schema. No candidate decisions were validated."
    return "Gemini rejected the request parameters. No candidate decisions were validated."


def research_key(config: ResearchProviderConfig) -> str:
    variable = GEMINI_KEY_VARIABLE if config.provider == "gemini" else RESEARCH_KEY_VARIABLE
    key = os.environ.get(variable, "").strip()
    if not key:
        raise ResearchCredentialError(f"set {variable} for provider-backed research")
    return key


LOCAL_URL_VARIABLE = "ENTROPYTRADE_LOCAL_LLM_URL"
LOCAL_KEY_VARIABLE = "ENTROPYTRADE_LOCAL_LLM_KEY"


def local_endpoint() -> str:
    """A server-configured OpenAI-compatible endpoint (for example Ollama or vLLM).

    Loopback only: retrieved prompts must not leave the machine through this path.
    """
    from urllib.parse import urlsplit

    url = os.environ.get(LOCAL_URL_VARIABLE, "").strip().rstrip("/")
    parts = urlsplit(url)
    if (
        not url
        or parts.scheme not in {"http", "https"}
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ResearchCredentialError(
            f"set {LOCAL_URL_VARIABLE} to a loopback OpenAI-compatible base URL"
        )
    return url


def local_model(model_name: str) -> Model:
    """Construct a model for a local endpoint; no request is sent here."""
    selected = OpenAIProvider(
        api_key=os.environ.get(LOCAL_KEY_VARIABLE, "").strip() or "local",
        base_url=local_endpoint(),
    )
    selected.client.max_retries = 0
    return OpenAIChatModel(model_name, provider=selected)


def research_model(config: ResearchProviderConfig) -> Model:
    """Construct a provider model using only the dedicated research key.

    Does not opt into requests, mutate the fixture guard or use ambient SDK base URLs.
    A later isolated research worker must scope and budget actual provider calls.
    """
    key = research_key(config)
    if config.provider == "gemini":
        google = GoogleProvider(
            api_key=key,
            base_url="https://generativelanguage.googleapis.com",
            retry_options=HttpRetryOptions(attempts=1),
        )
        return GoogleModel(config.model_name, provider=google, settings={"thinking": False})
    if config.provider == "openai":
        selected = OpenAIProvider(api_key=key, base_url="https://api.openai.com/v1")
        selected.client.max_retries = 0
        return OpenAIChatModel(config.model_name, provider=selected)
    anthropic = AnthropicProvider(api_key=key, base_url="https://api.anthropic.com")
    anthropic.client.max_retries = 0
    return AnthropicModel(config.model_name, provider=anthropic)
