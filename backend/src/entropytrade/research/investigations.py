"""Crash-safe, bounded offline diagnostics using the existing research job queue.

The readiness database freezes an outbox request before research enqueue. A deterministic
destination ID makes a retry safe even after the job finishes or enqueue succeeds before
the outbox link commits. No credentials, acquisition permission or paper authority inherit
from the originating research request.
"""

import json
import re
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.domain.strategy import StrategySpec
from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import ProviderChoice, ResearchBudget, ResearchRequest
from entropytrade.research.store import investigation_job_id, job_identifier, reject_collector_chain

if TYPE_CHECKING:
    from entropytrade.research.service import ResearchService
    from entropytrade.tracking.readiness_store import ReadinessStore

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _metadata(path: Path) -> sqlite3.Connection:
    """Offline checkpointed metadata only: immutable mode cannot create WAL sidecars."""
    reject_collector_chain(path)
    for suffix in ("-wal", "-journal"):
        journal = path.with_name(path.name + suffix)
        reject_collector_chain(journal)
        if journal.exists() and journal.stat().st_size:
            raise ValueError("investigation restore requires checkpointed SQLite metadata")
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def _scope(monitor: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """Read frozen metadata only; a broken current model policy can still be diagnosed."""
    spec = (
        StrategySpec.model_validate_json(monitor["spec"])
        if isinstance(monitor["spec"], str)
        else StrategySpec.model_validate(monitor["spec"])
    )
    if spec.spec_hash() != monitor.get("spec_hash"):
        raise ValueError("investigation strategy scope checksum mismatch")
    binding = monitor["model_binding"]
    if isinstance(binding, str):
        binding = json.loads(binding)
    if (
        not isinstance(binding, dict)
        or binding.get("status") != "bound"
        or scientific_hash({key: value for key, value in binding.items() if key != "binding_hash"})
        != binding.get("binding_hash")
        or spec.model_ref is None
        or binding.get("model_ref") != spec.model_ref.model_dump(mode="json")
        or not isinstance(binding.get("snapshot"), dict)
    ):
        raise ValueError("investigation requires a verified frozen model scope")
    if (
        binding["snapshot"].get("model_hash") != spec.model_ref.version
        or binding["snapshot"].get("family") != spec.model_ref.family
    ):
        raise ValueError("investigation frozen model identity mismatch")
    frozen = binding["snapshot"].get("series")
    if (
        not isinstance(frozen, (list, tuple))
        or not frozen
        or any(not isinstance(series, str) for series in frozen)
    ):
        raise ValueError("investigation requires frozen model series")
    universe = spec.market_universe
    declared = set(universe.series_tickers) | {
        ticker.split("-", 1)[0] for ticker in (*universe.event_tickers, *universe.market_tickers)
    }
    if not declared or not declared <= set(frozen):
        raise ValueError("investigation cannot expand beyond the frozen strategy/model scope")
    family = monitor["family"]
    if not isinstance(family, str):
        raise ValueError("investigation family is missing")
    return family, tuple(sorted(declared))


def _safe_request(value: object) -> ResearchRequest:
    request = ResearchRequest.model_validate(value)
    budget = request.budget
    if (
        request.provider.provider != "local_templates"
        or request.provider.model_name
        or budget.ai_usd != 0
        or budget.max_http_requests != 0
        or budget.max_bytes != 0
        or not 60 <= budget.max_runtime_seconds <= 120
        or budget.max_retries != 0
        or request.acquisition != "none"
        or request.paper_preference != "never"
        or not request.universe
    ):
        raise ValueError("incident investigation must remain bounded and offline")
    return request


def _request(monitor: dict[str, Any], incident_id: str, objective: str) -> ResearchRequest:
    family, universe = _scope(monitor)
    return ResearchRequest(
        objective=f"Investigate retained paper incident {incident_id}. {objective}",
        family=family,
        universe=universe,
        provider=ProviderChoice(provider="local_templates"),
        budget=ResearchBudget(
            ai_usd=Decimal(0),
            max_http_requests=0,
            max_bytes=0,
            max_runtime_seconds=120,
            max_retries=0,
        ),
        acquisition="none",
        validation_depth="quick",
        paper_preference="never",
    )


def enqueue_investigation(
    research: "ResearchService",
    readiness: "ReadinessStore",
    monitor: dict[str, Any],
    incident_id: str,
    *,
    policy_hash: str,
    objective: str,
) -> dict[str, Any]:
    """Freeze the outbox, reuse its sole destination, then link and wake the same runner."""
    if research.workspace.resolve() != readiness.jobs.root.resolve():
        raise ValueError("incident and research stores must share a workspace")
    if (
        not 1 <= len(incident_id) <= 200
        or not incident_id.strip()
        or _HASH.fullmatch(policy_hash) is None
    ):
        raise ValueError("investigation requires an incident, policy hash and objective")
    request = _safe_request(_request(monitor, incident_id, objective).model_dump(mode="json"))
    entities = research.family(request.family).resolve_universe(request.objective, request.universe)
    universe = tuple(entity.series for entity in entities)
    outbox = readiness.investigate(
        monitor["id"], incident_id, policy_hash, request=request.model_dump(mode="json")
    )
    if _safe_request(json.loads(outbox["request_json"])).fingerprint() != request.fingerprint():
        raise ValueError("incident outbox request changed")
    job_id, created = research.store.create_job(
        request, universe=universe, now=research.now(), origin_key=outbox["id"]
    )
    research.wake.set()
    linked = readiness.investigate(
        monitor["id"],
        incident_id,
        policy_hash,
        request=request.model_dump(mode="json"),
        research_job_id=job_id,
    )
    job = research.store.get_job(job_id)
    if job is None:
        raise ValueError("incident research destination disappeared")
    return {**linked, "created": created, "status": job["status"], "objective": request.objective}


def verify_investigation(workspace: Path, outbox: dict[str, Any]) -> None:
    """Read-only restore proof. Never creates stores, jobs, model objects or network work."""
    reject_collector_chain(workspace)
    key = {name: outbox[name] for name in ("monitor_id", "incident_key", "policy_hash")}
    job_identifier(key["monitor_id"])
    if not key["incident_key"] or _HASH.fullmatch(key["policy_hash"]) is None:
        raise ValueError("invalid investigation incident or policy")
    if scientific_hash(key) != outbox["id"]:
        raise ValueError("investigation outbox identity mismatch")
    identifier = investigation_job_id(outbox["id"])
    if outbox["research_job_id"] not in {None, identifier}:
        raise ValueError("investigation links a different research destination")
    frozen = outbox.get("request_json")
    if frozen is None:
        if outbox["research_job_id"] is not None:
            raise ValueError("linked investigation lacks its frozen request")
        return
    request = _safe_request(json.loads(frozen))
    with closing(_metadata(workspace / "jobs.sqlite")) as db:
        row = db.execute(
            "SELECT family,spec,spec_hash,model_binding FROM monitors WHERE id=?",
            (key["monitor_id"],),
        ).fetchone()
    if row is None or (request.family, request.universe) != _scope(
        dict(zip(("family", "spec", "spec_hash", "model_binding"), row, strict=True))
    ):
        raise ValueError("investigation request differs from its frozen monitor scope")
    path = workspace / "research/research.sqlite"
    if not path.is_file():
        if outbox["research_job_id"] is not None:
            raise ValueError("linked investigation research metadata is missing")
        return
    with closing(_metadata(path)) as db:
        row = db.execute(
            "SELECT request,fingerprint,universe,family FROM research_jobs WHERE id=?",
            (identifier,),
        ).fetchone()
    if row is None:
        if outbox["research_job_id"] is not None:
            raise ValueError("linked investigation job is missing")
        return
    if (
        _safe_request(json.loads(row[0])).fingerprint() != request.fingerprint()
        or row[1] != request.fingerprint()
        or tuple(json.loads(row[2])) != request.universe
        or row[3] != request.family
    ):
        raise ValueError("investigation destination request changed")
