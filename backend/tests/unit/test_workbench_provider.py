"""Provider jobs use real serialization and deterministic gates; controlled HTTP only."""

import json
from pathlib import Path
from typing import Any

import pytest

from entropytrade.agents.guard import provider_requests_blocked
from entropytrade.agents.pipeline import run_research
from entropytrade.api.jobs import Jobs, validate_request
from entropytrade.api.worker import execute_job
from entropytrade.experiments import workflow
from tests.provider_support import wire_research

REPO = Path(__file__).resolve().parents[3]
CONFIG = {"provider": "openai", "model_name": "gpt-4.1-mini"}
REQUEST = {
    "idea": "Investigate Philadelphia forecast revisions and model disagreement",
    "family": "weather",
    "mode": "recorded",
    "reasoning": "provider",
    "enable_provider": True,
}


@pytest.mark.parametrize("case", ["success", "outage", "malformed", "deadline"])
def test_provider_job_runs_typed_research_then_deterministic_experiments_or_saved_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    original = run_research
    calls: list[dict[str, Any]] = []

    async def controlled_research(**kwargs: Any) -> dict[str, Any]:
        return await wire_research(original, case=case, calls=calls, **kwargs)

    monkeypatch.setattr(workflow, "run_research", controlled_research)
    jobs = Jobs(tmp_path)
    job_id = jobs.create(REQUEST, provider=CONFIG)
    jobs.update(job_id, "starting", "Starting controlled provider transport check")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    review = job["result"]
    assert review is not None, job["detail"]
    assert provider_requests_blocked()
    assert review["reasoning"] == "provider"
    assert "mock" not in review["reasoning_limit"]
    assert review["research"]["provider"] == CONFIG
    assert review["research"]["limits"]["requests"] == 16
    assert not review["final_holdout_evaluated"]
    assert not review["probabilities"]
    assert "fixture-dedicated-key" not in json.dumps(job)
    assert json.loads((tmp_path / "runs" / job_id / "review.json").read_text()) == review
    assert Jobs(tmp_path).get(job_id) == job
    assert all(a["sha256"] for a in review["artifacts"])
    assert calls
    if case == "success":
        assert job["status"] == "completed"
        assert len(calls) == 5
        assert len(review["hypotheses"]) == len(review["proposals"]) == 3
        assert len(review["candidates"]) == 3
        assert all(not c["tested"] and not c["scenarios"] for c in review["candidates"])
        assert review["experiment_id"].startswith("sha256:")
        assert review["lineage"]["research_hash"].startswith("sha256:")
        assert [s["role"] for s in review["research"]["stages"]] == [
            "research",
            "hypothesis",
            "quant",
            "critic",
        ]
        assert {e["stage"] for e in job["events"]} >= {
            "research_research",
            "research_hypothesis",
            "research_quant",
            "research_critic",
            "experiments",
        }
        assert "eligible_events" in json.dumps(calls[1]["messages"])
        assert not any('"outcome"' in s["prompt"] for s in review["research"]["stages"])
    else:
        assert job["status"] == "failed"
        assert review["status"] == "research_failed"
        assert review["experiment_id"] is None
        assert not review["candidates"]
        assert review["research"]["failure"]["stage"] == "research"
        assert "experiments" not in {e["stage"] for e in job["events"]}
        assert not (tmp_path / "runs" / job_id / "workflow/experiments").exists()
        if case == "deadline":
            assert review["research"]["failure"]["type"] == "TimeoutError"


@pytest.mark.parametrize(
    ("case", "requests", "stage"),
    [
        ("unpriced_tool", 1, "research"),
        ("unpriced_retry", 1, "research"),
        ("unpriced_output", 1, "research"),
        ("unpriced_second_tool", 2, "research"),
        ("unpriced_second_retry", 2, "research"),
        ("unpriced_second_output", 2, "research"),
        ("unpriced_later_stage", 3, "hypothesis"),
    ],
)
def test_unpriced_response_stops_requests_and_persists_failed_review_without_experiments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    requests: int,
    stage: str,
) -> None:
    calls: list[dict[str, Any]] = []

    async def controlled_research(**kwargs: Any) -> dict[str, Any]:
        return await wire_research(run_research, case=case, calls=calls, **kwargs)

    monkeypatch.setattr(workflow, "run_research", controlled_research)
    jobs = Jobs(tmp_path)
    job_id = jobs.create(REQUEST, provider=CONFIG)
    jobs.update(job_id, "starting", "Checking controlled unknown response pricing")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert len(calls) == requests
    assert job["status"] == "failed"
    review = job["result"]
    assert review["status"] == "research_failed"
    assert review["experiment_id"] is None
    assert not review["candidates"]
    assert not review["probabilities"]
    assert not review["final_holdout_evaluated"]
    research = review["research"]
    assert research["failure"]["type"] == "ResearchPricingError"
    assert research["failure"]["stage"] == stage
    assert "pricing is unavailable" in review["report"]
    assert research["pricing_status"] == "unavailable"
    assert research["usage"]["requests"] == requests
    assert research["usage"]["input_tokens"] == requests * 100
    assert research["usage"]["output_tokens"] == requests * 100
    assert (research["usage"]["cost"] is None) == (requests == 1)
    assert len(research["responses"]) == requests
    assert research["responses"][-1]["usage"]["cost"] is None
    assert research["responses"][-1]["stage"] == stage
    assert research["responses"][-1]["provider_response_id"] == f"controlled-{requests - 1}"
    assert research["responses"][-1]["model_name"] == "CONTROLLED-model-without-pricing"
    assert all(r["usage"]["cost"] is not None for r in research["responses"][:-1])
    # Only the priced tool response may cause a tool call; the refused response does not.
    assert research["usage"]["tool_calls"] == (0 if requests == 1 else 1)
    assert "experiments" not in {e["stage"] for e in job["events"]}
    assert not (tmp_path / "runs" / job_id / "workflow/experiments").exists()
    saved = tmp_path / "runs" / job_id / "review.json"
    original_bytes = saved.read_bytes()
    assert json.loads(original_bytes) == review
    reopened = Jobs(tmp_path)
    reopened.recover()
    assert reopened.get(job_id) == job
    assert saved.read_bytes() == original_bytes
    assert len(calls) == requests
    assert "fixture-dedicated-key" not in json.dumps(job)
    assert provider_requests_blocked()


def test_missing_research_key_is_a_durable_downloadable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENTROPYTRADE_RESEARCH_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-ambient-must-not-be-used")
    jobs = Jobs(tmp_path)
    job_id = jobs.create(REQUEST, provider=CONFIG)
    jobs.update(job_id, "starting", "Starting provider check without credentials")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert job["status"] == "failed"
    review = job["result"]
    assert review["research"]["failure"]["type"] == "ResearchCredentialError"
    assert "credential is missing" in review["report"]
    assert review["research"]["usage"]["requests"] == 0
    assert not review["research"]["stages"]
    assert not review["candidates"]
    assert not review["final_holdout_evaluated"]
    assert "fixture-ambient" not in json.dumps(job)


@pytest.mark.parametrize(
    "change",
    [
        {"enable_provider": False},
        {"enable_provider": "true"},
        {"enable_provider": 1},
        {"reasoning": "local"},
        {"reasoning": []},
        {"mode": "synthetic"},
        {"research_provider": CONFIG},
        {"api_key": "forbidden"},
        {"provider_url": "https://invalid"},
    ],
)
def test_provider_requests_require_opt_in_and_cannot_inject_configuration(
    tmp_path: Path,
    change: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match=r"provide only|opt-in|opt in|requires real|boolean"):
        Jobs(tmp_path).create({**REQUEST, **change}, provider=CONFIG)
    assert not Jobs(tmp_path).history()


def test_server_configuration_is_required_and_frozen_in_the_request(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    with pytest.raises(ValueError, match="configure"):
        jobs.create(REQUEST)
    config = dict(CONFIG)
    job_id = jobs.create(REQUEST, provider=config)
    config["model_name"] = "changed"
    job = jobs.get(job_id)
    assert job is not None
    assert job["request"]["research_provider"] == CONFIG
    assert validate_request(job["request"], stored=True) == job["request"]
    jobs.recover()
    assert jobs.get(job_id)["status"] == "interrupted"  # type: ignore[index]
    assert jobs.queued() is None


@pytest.mark.parametrize("provider_job", [False, True])
def test_only_opted_in_worker_inherits_dedicated_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider_job: bool,
) -> None:
    from entropytrade.api.runner import Runner, worker_environment
    from tests.unit.test_workbench_http import ControlledProcess

    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "KALSHI_API_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    ):
        monkeypatch.setenv(name, "fixture-ambient-secret")
    monkeypatch.setenv("ENTROPYTRADE_RESEARCH_API_KEY", "fixture-research-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://invalid.example")
    jobs = Jobs(tmp_path)
    request = (
        REQUEST if provider_job else {"idea": "Local", "family": "weather", "mode": "recorded"}
    )
    job_id = jobs.create(request, provider=CONFIG)
    jobs.update(job_id, "starting", "Checking worker isolation")
    environments: list[dict[str, str]] = []

    def launch(_command: list[str], **kwargs: Any) -> ControlledProcess:
        environments.append(kwargs["env"])
        return ControlledProcess(1)

    monkeypatch.setattr("entropytrade.api.runner.subprocess.Popen", launch)
    Runner(jobs, REPO).execute(job_id)
    env = environments[0]
    assert not any(
        name in env
        for name in (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENAI_BASE_URL",
            "KALSHI_API_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "HOME",
        )
    )
    if provider_job:
        assert env["ENTROPYTRADE_RESEARCH_API_KEY"] == "fixture-research-secret"
    else:
        assert env == worker_environment(REPO, tmp_path)
        assert "ENTROPYTRADE_RESEARCH_API_KEY" not in env
    assert "fixture-research-secret" not in json.dumps(jobs.get(job_id))


def test_provider_failure_and_pending_opt_in_survive_offline_restore_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from entropytrade.api.recovery import restore, snapshot
    from entropytrade.tracking.store import TrackingStore

    monkeypatch.delenv("ENTROPYTRADE_RESEARCH_API_KEY", raising=False)
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED lock identity")
    root = tmp_path / "data/cache/original"
    jobs = Jobs(root)
    TrackingStore(jobs)
    failed = jobs.create(REQUEST, provider=CONFIG)
    jobs.update(failed, "starting", "Starting missing-credential recovery check")
    execute_job(jobs, REPO, failed)
    original = jobs.get(failed)
    assert original is not None
    assert original["status"] == "failed"
    assert original["result"]["experiment_id"] is None
    queued = jobs.create(REQUEST, provider=CONFIG)
    archive = tmp_path / "data/recovery/provider.zip"
    snapshot(tmp_path, root, archive)
    destination = tmp_path / "data/cache/restored"
    restore(tmp_path, archive, destination)
    reopened = Jobs(destination)
    assert reopened.get(failed) == original
    assert (destination / "runs" / failed / "review.json").read_bytes() == (
        root / "runs" / failed / "review.json"
    ).read_bytes()
    reopened.recover()
    pending = reopened.get(queued)
    assert pending is not None
    assert pending["status"] == "interrupted"
    assert pending["request"]["research_provider"] == CONFIG
    assert reopened.queued() is None
    assert reopened.get(failed) == original
