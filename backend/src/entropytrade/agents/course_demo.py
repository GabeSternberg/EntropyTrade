"""CIS 1990 entry point for the real provider and Philadelphia public-source workflow."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from entropytrade.agents.course_sources import fetch_course_sources
from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence, previous_research
from entropytrade.agents.pipeline import run_research
from entropytrade.agents.provider import ResearchProviderConfig, research_key

DEMO_MODEL = "gemini-3.5-flash-lite"
DEMO_PROVIDER = ResearchProviderConfig(provider="gemini", model_name=DEMO_MODEL)
DEMO_OUTPUT = Path("data/cache/cis1990")
DEMO_PROMPT = (
    "Research a Philadelphia daily-high-temperature market on Kalshi. Retrieve relevant market "
    "rules and available NWS forecasts. Identify two falsifiable forecasting signals and propose "
    "a testable strategy if supported. For a reusable research proposal, use the KXHIGHPHIL "
    "series rather than claiming a current ticker belongs to historical coverage. Evaluate data "
    "sufficiency for backtesting. Explain unavailable evidence or unsupported features."
)


def redact_course_value(value: Any, key: str) -> Any:
    if isinstance(value, str):
        return value.replace(key, "[redacted]")
    if isinstance(value, dict):
        # Field names and run identity are assigned by the application.
        return {
            name: item if name in {"run_id", "status"} else redact_course_value(item, key)
            for name, item in value.items()
        }
    if isinstance(value, list):
        return [redact_course_value(item, key) for item in value]
    return value


def _describe_sources(sources: dict[str, Any], emit: Callable[[str], None]) -> None:
    for source in sources.values():
        requests = ", ".join(
            f"{item['url']} [HTTP {item.get('http_status', 'unavailable')}, "
            f"{item.get('error', item['status'])}]"
            for item in source["requests"]
        )
        emit(f"{source['source']}: {source['status']} | {requests}")
    matched = sources["weather"]["market_dates_with_forecast"]
    full = sources["weather"]["market_dates_with_full_forecast"]
    emit("Market dates with NWS forecast hours: " + (", ".join(matched) if matched else "none"))
    emit("Market dates with a full NWS forecast: " + (", ".join(full) if full else "none"))


async def run_philadelphia_research(
    *,
    repo: Path,
    output: Path,
    run_id: str | None = None,
    progress: Callable[[str, str], None] | None = None,
    sources_ready: Callable[[dict[str, Any]], None] | None = None,
    stage_complete: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """The shared CLI and website workflow. Inputs are fixed by the application."""
    key = research_key(DEMO_PROVIDER)
    if progress:
        progress("sources", "Retrieving public Kalshi listings and NWS forecast hours")
    sources = await fetch_course_sources()
    if sources_ready:
        sources_ready(sources)
    registry = output / "registry.sqlite"
    config = EvidenceConfig.model_validate_json(
        (repo / "configs/research/weather.json").read_text()
    )
    evidence = ResearchEvidence(
        config.revalidated(root=repo / config.root),
        history=previous_research(registry),
        current_sources=sources,
    )
    return await run_research(
        prompt=DEMO_PROMPT,
        evidence=evidence,
        provider=DEMO_PROVIDER,
        registry_path=registry,
        output=output,
        enable_provider=True,
        progress=progress,
        stage_complete=stage_complete,
        redact=lambda trace: redact_course_value(trace, key),
        run_id=run_id,
    )


async def run_course_demo(*, output: Path, check_sources: bool, emit: Callable[[str], None]) -> int:
    if check_sources:
        emit("Runtime: public-source check only | Evidence: live public GETs")
        sources = await fetch_course_sources()
        _describe_sources(sources, emit)
        output.mkdir(parents=True, exist_ok=True)
        path = output / f"sources-{uuid4()}.json"
        path.write_text(
            json.dumps({"mode": "live_public_sources_only", **sources}, indent=2) + "\n"
        )
        emit(f"Source trace: {path}")
        return 0 if sources["weather"]["market_dates_with_forecast"] else 1

    research_key(DEMO_PROVIDER)
    emit(
        f"Runtime: Gemini API via PydanticAI ({DEMO_MODEL}) | "
        "Evidence: live GETs and retained coverage"
    )
    emit(f"Request: {DEMO_PROMPT}")
    result = await run_philadelphia_research(
        repo=Path.cwd(),
        output=output,
        progress=lambda _, message: emit(message),
        sources_ready=lambda sources: _describe_sources(sources, emit),
    )
    emit(result["report"])
    emit(
        json.dumps(
            {
                "status": result["status"],
                "runtime": DEMO_MODEL,
                "stages": [entry["role"] for entry in result["stages"]],
                "usage": result["usage"],
                "proposals": result["candidates"],
                "decisions": result["decisions"],
                "failure": result.get("failure"),
                "trace": str(output / result["run_id"] / "run.json"),
            },
            indent=2,
        )
    )
    return 0 if result["status"] == "completed" else 1
