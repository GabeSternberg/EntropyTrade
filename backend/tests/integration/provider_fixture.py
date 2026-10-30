"""TEST-ONLY listener/worker with controlled OpenAI wire responses.

The website, SQLite queue, subprocess lifecycle, PydanticAI serialization and protected
experiment engine are real. Only provider HTTP is controlled; no external request/key.
Production has no switch to invoke this fixture or select a provider URL/module.
"""

import argparse
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from entropytrade.agents.pipeline import run_research
from entropytrade.api.jobs import Jobs
from entropytrade.api.server import WorkbenchServer
from entropytrade.api.worker import execute_job
from entropytrade.experiments import workflow
from tests.provider_support import wire_research


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--job")
    parser.add_argument("--port", type=int, default=43136)
    args = parser.parse_args()
    if args.job:
        original_research = run_research

        async def controlled(**kwargs: Any) -> dict[str, Any]:
            prompt = kwargs["prompt"]
            case = (
                "outage"
                if "CONTROLLED outage" in prompt
                else ("slow" if "CONTROLLED slow" in prompt else "success")
            )
            return await wire_research(original_research, case=case, calls=[], **kwargs)

        with patch.object(workflow, "run_research", controlled):
            execute_job(Jobs(args.workspace), args.repo, args.job)
        return

    original_launch = subprocess.Popen

    def launch(command: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        if command[1:3] == ["-m", "entropytrade.api.worker"]:
            command = [*command[:2], "tests.integration.provider_fixture", *command[3:]]
            kwargs["env"] = {
                **kwargs["env"],
                "PYTHONPATH": str(args.repo / "backend") + ":" + str(args.repo / "backend/src"),
            }
        return original_launch(command, **kwargs)

    with patch("entropytrade.api.runner.subprocess.Popen", side_effect=launch):
        server = WorkbenchServer(
            args.repo,
            args.workspace,
            port=args.port,
            research_provider={"provider": "openai", "model_name": "gpt-4.1-mini"},
        )
        server.runner.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
