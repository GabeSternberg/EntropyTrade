"""Isolated provider worker: one hypothesis-generation call per process.

PydanticAI's request switch is process-wide, so provider calls never run inside the web
server. The server writes a bounded context file, starts this module with an allowlisted
environment, and validates the result file after the process exits. Exception text is
never persisted because it can contain request bodies or credentials.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from entropytrade.research.model import ResearchRequest

KEY_VARIABLES = {
    "gemini": ("GEMINI_API_KEY",),
    "openai": ("ENTROPYTRADE_RESEARCH_API_KEY",),
    "anthropic": ("ENTROPYTRADE_RESEARCH_API_KEY",),
    "openai_compatible": ("ENTROPYTRADE_LOCAL_LLM_URL", "ENTROPYTRADE_LOCAL_LLM_KEY"),
}
_PROXY = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, allow_nan=False))
    temporary.replace(path)


def run(workspace: Path, job_id: str, attempt: int) -> dict[str, Any]:
    from entropytrade.agents.hypotheses import classify, propose, provider_model
    from entropytrade.research.store import ResearchStore

    directory = workspace / "research" / "jobs" / job_id
    context = json.loads((directory / f"context-{attempt}.json").read_text())
    job = ResearchStore(workspace / "research").get_job(job_id)
    if job is None:
        raise KeyError("research job not found")
    request = ResearchRequest.model_validate(job["request"])
    provider = request.provider.provider
    if provider == "local_templates":
        raise ValueError("local templates do not use the provider worker")
    try:
        model = provider_model(provider, request.provider.model_name)
        result = asyncio.run(
            propose(
                objective=request.objective,
                context=context,
                model=model,
                provider=provider,
                budget_usd=request.budget.ai_usd,
            )
        )
        result["responses"] = model.responses
    except Exception as exc:  # noqa: BLE001 - durable failure boundary; never persist text
        result = {"status": "failed", "failure": classify(exc)}
        if "model" in locals():
            result["responses"] = model.responses
            usage = model.observed_usage
            result["usage"] = {
                "requests": usage.requests,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            }
            result["cost_usd"] = str(usage.cost) if usage.cost is not None else None
    result["provider"] = provider
    result["model_name"] = request.provider.model_name
    return result


class SubprocessProposer:
    """Start the worker with an allowlisted environment and wait with cancellation."""

    def __init__(self, repo: Path, workspace: Path, *, lease_fd: int | None = None) -> None:
        self.repo, self.workspace = repo, workspace
        self.lease_fds = () if lease_fd is None else (lease_fd,)

    def __call__(
        self,
        job_id: str,
        attempt: int,
        provider: str,
        context: dict[str, Any],
        *,
        timeout: float,
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        from entropytrade.api.runner import worker_environment

        directory = self.workspace / "research" / "jobs" / job_id
        atomic_json(directory / f"context-{attempt}.json", context)
        output = directory / f"proposals-{attempt}.json"
        if output.is_file():
            return dict(json.loads(output.read_text()))
        environment = worker_environment(self.repo, self.workspace)
        for name in (*KEY_VARIABLES.get(provider, ()), *_PROXY):
            if os.environ.get(name):
                environment[name] = os.environ[name]
        command = [
            sys.executable,
            "-m",
            "entropytrade.research.worker",
            "--workspace",
            str(self.workspace),
            "--job",
            job_id,
            "--attempt",
            str(attempt),
        ]
        with subprocess.Popen(  # noqa: S603 - fixed module and validated UUID, no shell
            command,
            cwd=self.repo,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=self.lease_fds,
        ) as process:
            started = time.monotonic()
            while process.poll() is None:
                if cancelled() or time.monotonic() - started > timeout:
                    process.kill()
                    process.wait()
                    return {
                        "status": "failed",
                        "failure": {
                            "type": "Cancelled" if cancelled() else "TimeoutError",
                            "transient": not cancelled(),
                            "reason": "Hypothesis generation was cancelled."
                            if cancelled()
                            else "The provider worker exceeded its wall-time budget.",
                        },
                    }
                time.sleep(0.2)
        if not output.is_file():
            return {
                "status": "failed",
                "failure": {
                    "type": "WorkerExit",
                    "transient": False,
                    "reason": "The provider worker exited without a result; check dependencies.",
                },
            }
        return dict(json.loads(output.read_text()))


def main() -> None:
    parser = argparse.ArgumentParser(description="EntropyTrade research provider worker")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    from entropytrade.research.store import job_identifier

    job_id = job_identifier(args.job)
    result = run(args.workspace, job_id, args.attempt)
    atomic_json(
        args.workspace / "research" / "jobs" / job_id / f"proposals-{args.attempt}.json",
        json.loads(json.dumps(result, default=str)),
    )


if __name__ == "__main__":
    main()
