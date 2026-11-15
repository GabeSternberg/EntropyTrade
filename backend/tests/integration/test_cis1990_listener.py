"""Real loopback API and durable course jobs, with a test-only controlled worker."""

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from entropytrade.strategy_registry.store import Registry
from tests.cis1990_support import FIXTURE_KEY
from tests.integration.cis1990_fixture import controlled_worker
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO, await_job


@pytest.fixture
def workspace() -> Iterator[Path]:
    with TemporaryDirectory(prefix="cis1990-listener-", dir=REPO / "data/cache") as path:
        yield Path(path)


def test_course_route_guards_and_missing_credentials(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-key-does-not-enable-course")
    with listening(workspace, workers=False) as (server, client):
        config = client.get("/api/cis1990").json()
        headers = {"X-EntropyTrade-CSRF": config["csrf_token"]}
        assert config["configured"] is False
        assert not config["latest"]
        assert client.post("/api/cis1990", json={}).status_code == 403
        assert (
            client.post(
                "/api/cis1990",
                json={"api_key": FIXTURE_KEY},
                headers={**headers, "Origin": "https://example.invalid"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/cis1990", json={"model": "other"}, headers=headers).status_code == 400
        )
        absent = client.post("/api/cis1990", json={}, headers=headers)
        assert absent.status_code == 503
        assert "Enter a Gemini API key" in absent.json()["error"]
        for bad_key in (None, {"token": FIXTURE_KEY}, FIXTURE_KEY + "\x00", "a" * 513):
            invalid = client.post("/api/cis1990", json={"api_key": bad_key}, headers=headers)
            assert invalid.status_code == 400
            assert FIXTURE_KEY not in invalid.text
        assert server.jobs.queued() is None
        rejected = client.post(
            "/api/jobs",
            json={"idea": "override", "family": "weather", "mode": "cis1990"},
            headers=headers,
        )
        assert rejected.status_code == 400
        assert client.get("/views-cis1990.js").status_code == 200
        assert client.get("/api/catalog").json()["submission_enabled"] is False
        accepted = client.post("/api/cis1990", json={"api_key": FIXTURE_KEY}, headers=headers)
        assert accepted.status_code == 202
        assert FIXTURE_KEY not in accepted.text
        job_id = accepted.json()["id"]
        assert client.get(f"/api/cis1990/{job_id}/trace").status_code == 404
        cancelled = client.post(f"/api/cis1990/{job_id}/cancel", json={}, headers=headers)
        assert cancelled.json() == {"cancelled": True}
        assert client.get("/api/cis1990").json()["latest"]["status"] == "cancelled"
        assert server.runner.forget_course_key(job_id) is None
        assert server.jobs.queued() is None


@pytest.mark.parametrize("outage", [False, True])
def test_course_job_and_trace_over_real_listener(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, outage: bool
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", FIXTURE_KEY if outage else "different-server-default")
    monkeypatch.setenv("GOOGLE_API_KEY", "ambient-google")
    monkeypatch.setenv("ENTROPYTRADE_RESEARCH_API_KEY", "ambient-other-research")
    with controlled_worker(REPO, outage=outage), listening(workspace) as (server, client):
        config = client.get("/api/cis1990")
        assert config.json()["configured"] is True
        assert FIXTURE_KEY not in config.text
        headers = {"X-EntropyTrade-CSRF": config.json()["csrf_token"]}
        request = {} if outage else {"api_key": "  " + FIXTURE_KEY + "  "}
        response = client.post("/api/cis1990", json=request, headers=headers)
        assert response.status_code == 202
        job_id = response.json()["id"]
        duplicate = client.post("/api/cis1990", json={"api_key": "duplicate-key"}, headers=headers)
        assert duplicate.json()["id"] == job_id
        assert client.get("/api/jobs").json() == []
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
        assert (
            client.post(f"/api/jobs/{job_id}/cancel", json={}, headers=headers).status_code == 404
        )

        job = await_job(server.jobs, job_id)
        job_response = client.get(f"/api/cis1990/{job_id}")
        assert job_response.json() == job
        assert FIXTURE_KEY not in job_response.text
        assert "ambient-google" not in job_response.text
        assert job["status"] == ("failed" if outage else "completed"), job["detail"]
        trace = client.get(f"/api/cis1990/{job_id}/trace")
        assert trace.status_code == 200
        assert FIXTURE_KEY not in trace.text
        assert trace.json() == job["result"]
        result = trace.json()
        assert result["run_id"] == job_id
        assert result["data_mode"] == "controlled_http"
        assert result["provider"]["provider"] == "gemini"
        assert result["current_sources"]["weather"]["status"] == "available"
        assert not (workspace / "runs" / job_id).exists()
        run_json = (workspace / "cis1990" / job_id / "run.json").read_text()
        assert FIXTURE_KEY not in run_json
        registry = Registry(workspace / "cis1990/registry.sqlite")
        try:
            persisted = registry.agent_run(job_id)
            assert persisted is not None
            assert FIXTURE_KEY not in persisted
        finally:
            registry.close()
        assert server.runner.forget_course_key(job_id) is None
        if outage:
            assert result["failure"]["stage"] == "research"
            assert result["failure"]["http_status"] == 503
            assert result["model_request_failures"][0]["status"] == "failed"
        else:
            roles = ["research", "hypothesis", "quant", "critic"]
            assert [stage["role"] for stage in result["stages"]] == roles
            assert all("prompt" not in stage and stage["output"] for stage in result["stages"])
            assert all(
                f"research_{role}_completed" in {event["stage"] for event in job["events"]}
                for role in roles
            )
            assert any(row["status"] == "INSUFFICIENT_DATA" for row in result["decisions"])
            assert result["usage"]["input_tokens"] > 0
            assert result["pricing_status"] == "available"
            assert "Redaction check [redacted]" in trace.text
            assert (
                client.post(
                    "/api/monitors",
                    json={"job_id": job_id, "candidate_id": "c0", "interval_seconds": 60},
                    headers=headers,
                ).status_code
                == 400
            )
    with listening(workspace, workers=False) as (_, client):
        assert client.get("/api/cis1990").json()["latest"] == job
        assert client.get(f"/api/cis1990/{job_id}/trace").content == trace.content
