"""TEST-ONLY localhost server with controlled Kalshi/NWS and Gemini HTTP in its worker."""

import argparse
import asyncio
import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx2
from pydantic_ai.providers.google import GoogleProvider  # noqa: TID251

from entropytrade.agents import course_demo, course_sources, provider
from entropytrade.agents.fixture import operational_models
from entropytrade.agents.pipeline import run_research
from entropytrade.api.jobs import Jobs
from entropytrade.api.server import WorkbenchServer
from entropytrade.api.worker import execute_job
from tests.cis1990_support import FIXTURE_KEY, FIXTURE_NOW, gemini_response, public_fixture

if TYPE_CHECKING:
    from entropytrade.agents.evidence import ResearchEvidence


class ControlledJobs(Jobs):
    def update(
        self,
        job_id: str,
        stage: str,
        detail: str,
        *,
        status: str = "running",
        result: dict[str, Any] | None = None,
    ) -> bool:
        if result and "data_mode" in result:
            result = {**result, "data_mode": "controlled_http"}
        return super().update(job_id, stage, detail, status=status, result=result)


@contextmanager
def controlled_worker(repo: Path, *, outage: bool = False) -> Iterator[None]:
    spawn = subprocess.Popen

    def launch(command: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        if command[1:3] == ["-m", "entropytrade.api.worker"]:
            command = [*command[:2], "tests.integration.cis1990_fixture", *command[3:]]
            if outage:
                command += ["--outage"]
            kwargs["env"] = {
                **kwargs["env"],
                "PYTHONPATH": os.pathsep.join(
                    str(repo / part) for part in ("backend", "backend/src")
                ),
            }
        return spawn(command, **kwargs)

    with patch("entropytrade.api.runner.subprocess.Popen", side_effect=launch):
        yield


def execute_controlled(workspace: Path, repo: Path, job_id: str, *, outage: bool) -> None:
    assert os.environ.get("GEMINI_API_KEY") == FIXTURE_KEY
    assert "GOOGLE_API_KEY" not in os.environ
    assert "ENTROPYTRADE_RESEARCH_API_KEY" not in os.environ

    async def fetch() -> dict[str, Any]:
        return await course_sources.fetch_course_sources(transport=public_fixture("DEV-001", []))

    async def research(**kwargs: Any) -> dict[str, Any]:
        evidence: ResearchEvidence = kwargs["evidence"]
        request_count = 0

        async def respond(request: httpx2.Request) -> httpx2.Response:
            nonlocal request_count
            request_count += 1
            assert request.url.host == "generativelanguage.googleapis.com"
            assert request.url.path.endswith(f"/{course_demo.DEMO_MODEL}:generateContent")
            assert request.headers["x-goog-api-key"] == FIXTURE_KEY
            await asyncio.sleep(1.2 if request_count == 1 else 0.35)
            if outage:
                return httpx2.Response(503, json={"error": {"message": FIXTURE_KEY}})
            topics = {entry["query"]["topic"]: entry["evidence_id"] for entry in evidence.calls}
            for topic in ("current_markets", "weather"):
                if topic not in topics:
                    return gemini_response(("inspect_evidence", {"query": {"topic": topic}}))

            # The test outputs retain citations from the same worker's actual evidence calls.
            index = request_count - 3
            model = operational_models(kwargs["prompt"], evidence, kwargs["run_id"])[index]
            payload = model.custom_output_args
            assert isinstance(payload, dict)
            current_ids = [topics["current_markets"], topics["weather"]]
            if index == 0:
                payload["evidence_ids"] = current_ids
                payload["limitations"] = [*payload["limitations"], f"Redaction check {FIXTURE_KEY}"]
            elif index in {1, 2}:
                for item in payload["hypotheses" if index == 1 else "candidates"]:
                    item["evidence_ids"] = current_ids
            body = json.loads(request.content)
            name = next(
                tool["name"]
                for group in body["tools"]
                for tool in group["functionDeclarations"]
                if tool["name"] != "inspect_evidence"
            )
            return gemini_response((name, payload))

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as client:
            with patch.object(
                provider,
                "GoogleProvider",
                side_effect=lambda **values: GoogleProvider(http_client=client, **values),
            ):
                return await run_research(**kwargs)

    with (
        patch.object(course_sources, "utc_now", return_value=FIXTURE_NOW),
        patch.object(course_demo, "fetch_course_sources", fetch),
        patch.object(course_demo, "run_research", research),
    ):
        execute_job(ControlledJobs(workspace), repo, job_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--job")
    parser.add_argument("--port", type=int, default=43155)
    parser.add_argument("--outage", action="store_true")
    args = parser.parse_args()
    if args.job:
        execute_controlled(args.workspace, args.repo, args.job, outage=args.outage)
        return

    with (
        controlled_worker(args.repo, outage=args.outage),
        WorkbenchServer(args.repo, args.workspace, port=args.port) as server,
    ):
        server.runner.start()
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
