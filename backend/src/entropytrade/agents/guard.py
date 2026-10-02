"""Keep provider model calls off unless a later phase opts in."""

import os

_BANNER = "PYDANTIC_AI_NO_BANNER"


def block_provider_requests() -> None:
    """Refuse Anthropic and OpenAI requests. TestModel is unaffected."""
    os.environ.setdefault(_BANNER, "1")
    import pydantic_ai.models as models

    models.ALLOW_MODEL_REQUESTS = False


def provider_requests_blocked() -> bool:
    import pydantic_ai.models as models

    return models.ALLOW_MODEL_REQUESTS is False


def require_no_provider_request() -> None:
    """Raise if a provider request would be allowed."""
    import pydantic_ai.models as models

    models.check_allow_model_requests()


def openai_constructor_error() -> str:
    """Build an OpenAI agent with no key. The error is the result; no request is sent."""
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import UserError

    try:
        Agent("openai:gpt-4o")
    except UserError as exc:
        return f"{type(exc).__name__}: {exc}"
    return "constructed"
