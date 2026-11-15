"""Development cases using controlled HTTP at the actual Google SDK and source adapters."""

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from pydantic_ai.providers.google import GoogleProvider  # noqa: TID251

from entropytrade.agents import course_sources, provider
from entropytrade.agents.course_demo import DEMO_MODEL, run_course_demo
from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence
from entropytrade.agents.fixture import operational_models
from entropytrade.agents.guard import provider_requests_blocked
from entropytrade.agents.pipeline import run_research
from entropytrade.agents.provider import ResearchCredentialError, ResearchProviderConfig
from tests.cis1990_support import (
    FIXTURE_GRID,
    FIXTURE_INJECTION,
    FIXTURE_KEY,
    FIXTURE_NOW,
    gemini_response,
    public_fixture,
)

_CASES = Path("docs/cis1990/dev-cases")


@pytest.mark.parametrize("case_id", ["DEV-001", "DEV-002", "DEV-003"])
def test_development_case(case_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = json.loads((_CASES / f"{case_id}.json").read_text())
    assert case["id"] == case_id
    assert all(
        case[k]
        for k in ("required_sources", "pass_criteria", "acceptable_refusal", "incorrect_or_unsafe")
    )
    monkeypatch.setattr(course_sources, "utc_now", lambda: FIXTURE_NOW)
    monkeypatch.setenv("GEMINI_API_KEY", FIXTURE_KEY)
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-do-not-use")
    public_requests: list[str] = []
    requests: list[dict[str, Any]] = []
    run_id = str(uuid4())

    async def execute() -> dict[str, Any]:
        sources = await course_sources.fetch_course_sources(
            transport=public_fixture(case_id, public_requests)
        )
        config = EvidenceConfig.model_validate_json(
            Path("configs/research/weather.json").read_text()
        )
        evidence = ResearchEvidence(config, current_sources=sources)
        stages = iter(("research", "hypothesis", "quant", "critic"))
        retries = 0

        def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal retries
            body = json.loads(request.content)
            requests.append(body)
            assert request.method == "POST"
            assert request.headers["x-goog-api-key"] == FIXTURE_KEY
            assert request.url.host == "generativelanguage.googleapis.com"
            assert request.url.path.endswith(f"/{DEMO_MODEL}:generateContent")
            tools = {
                item["name"] for group in body["tools"] for item in group["functionDeclarations"]
            }
            assert "inspect_evidence" in tools
            assert "submit_order" not in tools
            transcript = json.dumps(body)
            if len(requests) == 2 and case_id == "DEV-003":
                assert FIXTURE_INJECTION in transcript
                return gemini_response(("submit_order", {}))
            topics = {entry["query"]["topic"]: entry["evidence_id"] for entry in evidence.calls}
            for topic in ("current_markets", "weather"):
                if topic not in topics:
                    return gemini_response(("inspect_evidence", {"query": {"topic": topic}}))

            output_tool = next(iter(tools - {"inspect_evidence"}))
            if case_id == "DEV-001" and retries == 0:
                retries += 1
                return gemini_response((output_tool, {"market_understanding": "too short"}))
            role = next(stages)
            index = ("research", "hypothesis", "quant", "critic").index(role)
            outputs = operational_models(case["prompt"], evidence, run_id)
            payload = outputs[index].custom_output_args
            assert isinstance(payload, dict)
            if role == "research":
                assert "functionResponse" in transcript
                payload["evidence_ids"] = [topics["current_markets"], topics["weather"]]
                if case_id == "DEV-002":
                    payload["limitations"] = ["NWS hourly forecast is unavailable (HTTP 503)."]
                if case_id == "DEV-003":
                    assert FIXTURE_INJECTION in transcript
            if role == "quant" and case_id == "DEV-003":
                payload["candidates"][0]["required_features"] = ["secret_model_probability"]
            if role == "critic":
                assert "minimum_edge" in transcript
                if case_id == "DEV-002":
                    for verdict in payload["verdicts"]:
                        verdict["accept_for_experiment"] = False
                        verdict["reason"] = (
                            "NWS hourly forecast is unavailable and historical coverage "
                            "is insufficient."
                        )
            return gemini_response((output_tool, payload))

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
            monkeypatch.setattr(
                provider,
                "GoogleProvider",
                lambda **kwargs: GoogleProvider(http_client=client, **kwargs),
            )
            return await run_research(
                prompt=case["prompt"],
                evidence=evidence,
                provider=ResearchProviderConfig(provider="gemini", model_name=DEMO_MODEL),
                registry_path=tmp_path / "registry.sqlite",
                output=tmp_path / "runs",
                enable_provider=True,
                run_id=run_id,
            )

    result = asyncio.run(execute())
    trace = tmp_path / "runs" / run_id / "run.json"
    assert result["status"] == "completed", (
        result["failure"] if "failure" in result else result["report"]
    )
    assert json.loads(trace.read_text())["status"] == "completed"
    assert FIXTURE_KEY not in trace.read_text()
    assert provider_requests_blocked()
    assert sorted(public_requests) == sorted(
        [course_sources.MARKETS_URL, course_sources.POINTS_URL, FIXTURE_GRID]
    )
    assert [stage["role"] for stage in result["stages"]] == [
        "research",
        "hypothesis",
        "quant",
        "critic",
    ]
    assert result["usage"]["requests"] == len(requests)
    assert result["usage"]["input_tokens"] > 0
    assert all(r["usage"]["cost"] and r["latency_ms"] >= 0 for r in result["responses"])
    assert all(not d["status"].startswith("READY") for d in result["decisions"])
    assert all(d["critic"]["reason"] for d in result["decisions"])
    assert "No backtest was run" in result["report"]
    evidence_ids = {
        event["evidence_id"] for event in result["tool_activity"] if event["role"] == "research"
    }
    assert set(result["note"]["evidence_ids"]) == evidence_ids
    assert result["coverage"]["eligible_events"] == result["coverage"]["scalar_label_events"] == 0
    weather = result["current_sources"]["weather"]
    if case_id == "DEV-001":
        assert len(requests) == 7  # Two evidence calls, one structured retry, and four outputs.
        assert weather["market_dates_with_full_forecast"] == ["2026-10-03"]
        assert weather["items"][1]["projected_hourly_max_f"] == "73"
        assert weather["scope"].endswith("forecast proxies")
        assert (
            result["current_sources"]["current_markets"]["items"][0]["rules"]["settlement_sources"][
                0
            ]["name"]
            == "The Weather Company"
        )
        assert any(
            d["structurally_valid"] and d["status"] == "INSUFFICIENT_DATA"
            for d in result["decisions"]
        )
    elif case_id == "DEV-002":
        assert weather["status"] == "unavailable"
        assert weather["items"] == []
        assert weather["requests"][-1]["http_status"] == 503
        assert "HTTP 503" in result["note"]["limitations"][0]
        assert "unavailable" in result["decisions"][0]["critic"]["reason"]
    else:
        assert result["responses"][1]["requested_tools"] == ["submit_order"]
        assert all(event["tool"] == "inspect_evidence" for event in result["tool_activity"])
        assert result["decisions"][0]["status"] == "REJECTED"
        assert any(
            "secret_model_probability" in reason for reason in result["decisions"][0]["reasons"]
        )


def test_missing_gemini_key_stops_before_source_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-do-not-use")

    def unexpected_source_call() -> None:
        pytest.fail("source I/O before credential validation")

    monkeypatch.setattr(
        "entropytrade.agents.course_demo.fetch_course_sources", unexpected_source_call
    )
    with pytest.raises(ResearchCredentialError, match="set GEMINI_API_KEY"):
        asyncio.run(run_course_demo(output=tmp_path, check_sources=False, emit=lambda _: None))
    assert not list(tmp_path.iterdir())


def test_gemini_http_failure_redacts_provider_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", FIXTURE_KEY)
    monkeypatch.setattr(course_sources, "utc_now", lambda: FIXTURE_NOW)
    attempts = 0
    messages: list[str] = []

    async def sources() -> dict[str, Any]:
        return await course_sources.fetch_course_sources(transport=public_fixture("DEV-001", []))

    def fail(_request: httpx2.Request) -> httpx2.Response:
        nonlocal attempts
        attempts += 1
        return httpx2.Response(
            503, json={"error": {"code": 503, "message": FIXTURE_KEY, "status": "UNAVAILABLE"}}
        )

    async def execute() -> int:
        monkeypatch.setattr("entropytrade.agents.course_demo.fetch_course_sources", sources)
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(fail)) as client:
            monkeypatch.setattr(
                provider,
                "GoogleProvider",
                lambda **kwargs: GoogleProvider(http_client=client, **kwargs),
            )
            return await run_course_demo(output=tmp_path, check_sources=False, emit=messages.append)

    assert asyncio.run(execute()) == 1
    assert attempts == 1
    trace = next(tmp_path.glob("*/run.json")).read_text()
    assert FIXTURE_KEY not in trace
    assert FIXTURE_KEY not in "".join(messages)
    result = json.loads(trace)
    assert result["failure"]["http_status"] == 503
    assert result["responses"] == []
    assert result["model_request_failures"][0]["status"] == "failed"
    assert result["pricing_status"] == "not_observed"
    assert result["decisions"] == []
    assert provider_requests_blocked()


def test_source_check_preserves_partial_forecast_without_daily_maximum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(course_sources, "utc_now", lambda: FIXTURE_NOW)

    async def sources() -> dict[str, Any]:
        return await course_sources.fetch_course_sources(
            transport=public_fixture("DEV-001", [], forecast_hours=12)
        )

    monkeypatch.setattr("entropytrade.agents.course_demo.fetch_course_sources", sources)
    assert (
        asyncio.run(run_course_demo(output=tmp_path, check_sources=True, emit=lambda _: None)) == 0
    )
    trace = json.loads(next(tmp_path.glob("sources-*.json")).read_text())
    assert trace["mode"] == "live_public_sources_only"
    weather = trace["weather"]
    assert weather["market_dates_with_forecast"] == ["2026-10-03"]
    assert weather["market_dates_with_full_forecast"] == []
    assert weather["items"][1]["max_in_returned_hours_f"] == "61"
    assert weather["items"][1]["projected_hourly_max_f"] is None
