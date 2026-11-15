"""CIS 1990 entry point for the real provider and Philadelphia public-source workflow."""

import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from entropytrade.agents.course_sources import fetch_course_sources
from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence, previous_research
from entropytrade.agents.pipeline import run_research
from entropytrade.agents.provider import ResearchProviderConfig, research_key

DEMO_MODEL = "gemini-3.5-flash-lite"
DEMO_OUTPUT = Path("data/cache/cis1990")
DEMO_PROMPT = (
    "Research a Philadelphia daily-high-temperature market on Kalshi. Retrieve relevant market "
    "rules and available NWS forecasts. Identify two falsifiable forecasting signals and propose "
    "a testable strategy if supported. For a reusable research proposal, use the KXHIGHPHIL "
    "series rather than claiming a current ticker belongs to historical coverage. Evaluate data "
    "sufficiency for backtesting. Explain unavailable evidence or unsupported features."
)


async def run_course_demo(*, output: Path, check_sources: bool, emit: Callable[[str], None]) -> int:
    provider = ResearchProviderConfig(provider="gemini", model_name=DEMO_MODEL)
    if not check_sources:
        research_key(provider)
    mode = (
        "public-source check only" if check_sources else f"Gemini API via PydanticAI ({DEMO_MODEL})"
    )
    data_mode = "live public GETs" if check_sources else "live public GETs and retained coverage"
    emit(f"Runtime: {mode} | Evidence: {data_mode}")
    if not check_sources:
        emit(f"Request: {DEMO_PROMPT}")
    sources = await fetch_course_sources()
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
    if check_sources:
        output.mkdir(parents=True, exist_ok=True)
        path = output / f"sources-{uuid4()}.json"
        path.write_text(
            json.dumps({"mode": "live_public_sources_only", **sources}, indent=2) + "\n"
        )
        emit(f"Source trace: {path}")
        return 0 if matched else 1

    registry = output / "registry.sqlite"
    config = EvidenceConfig.model_validate_json(Path("configs/research/weather.json").read_text())
    evidence = ResearchEvidence(
        config, history=previous_research(registry), current_sources=sources
    )
    result = await run_research(
        prompt=DEMO_PROMPT,
        evidence=evidence,
        provider=provider,
        registry_path=registry,
        output=output,
        enable_provider=True,
        progress=lambda _, message: emit(message),
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
