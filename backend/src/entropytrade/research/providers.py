"""Public provider catalog for the website. Reports configuration, never credential values.

A Claude Code, ChatGPT or Codex subscription does not provide API credits; each hosted
provider needs its own API key in the server environment.
"""

import os
from typing import Any

PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "provider": "local_templates",
        "label": "Local templates (deterministic, no model)",
        "requires": [],
        "billing": "none",
        "output": "deterministic",
        "suggested_models": [],
        "note": "Family hypothesis templates ranked by the objective. Not language-model "
        "reasoning; always available.",
    },
    {
        "provider": "gemini",
        "label": "Google Gemini API",
        "requires": ["GEMINI_API_KEY"],
        "billing": "metered",
        "output": "prompted_json",
        "suggested_models": ["gemini-3.5-flash-lite"],
        "note": "Prompted JSON output; Gemini rejects some nested tool schemas.",
    },
    {
        "provider": "anthropic",
        "label": "Anthropic Claude API",
        "requires": ["ENTROPYTRADE_RESEARCH_API_KEY"],
        "billing": "metered",
        "output": "tool_call",
        "suggested_models": ["claude-haiku-5-5", "claude-sonnet-5-5"],
        "note": "Needs an Anthropic API key; a Claude subscription does not include API credits.",
    },
    {
        "provider": "openai",
        "label": "OpenAI API",
        "requires": ["ENTROPYTRADE_RESEARCH_API_KEY"],
        "billing": "metered",
        "output": "tool_call",
        "suggested_models": [],
        "note": "Needs an OpenAI API key; a ChatGPT or Codex subscription is not API credit.",
    },
    {
        "provider": "openai_compatible",
        "label": "Local OpenAI-compatible endpoint (Ollama, vLLM)",
        "requires": ["ENTROPYTRADE_LOCAL_LLM_URL"],
        "billing": "local",
        "output": "prompted_json",
        "suggested_models": [],
        "note": "Loopback URLs only. Structured-output support varies by model; invalid output "
        "fails validation instead of being repaired.",
    },
)


def provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            **item,
            "configured": all(os.environ.get(name, "").strip() for name in item["requires"]),
        }
        for item in PROVIDERS
    ]
