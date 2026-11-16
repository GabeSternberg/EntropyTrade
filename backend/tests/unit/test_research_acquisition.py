"""Milestone B: source discovery, read-only acquisition, features and forward collection.

Network responses are replayed from real, unmodified captures of the public sources
(``tests/fixtures/research``). This is a controlled replay, not live acquisition.
"""

import gzip
import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.research import model
from entropytrade.research.acquire import (
    ADAPTERS,
    AcquisitionError,
    AllowlistTransport,
    Fetched,
    Receipt,
    issuance,
    pfm_maxima,
    products,
)
from entropytrade.research.inventory import inventory
from entropytrade.research.model import (
    AssessmentStatus,
    DataKind,
    DataRequirement,
    HypothesisStatus,
    JobStatus,
)
from entropytrade.research.service import ResearchService
from entropytrade.research.sources import evaluate, load_catalog
from tests.research_fixture_support import ReplayTransport, recorded

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)  # window 2026-11-06..2026-11-12 at lookback 7
OBJECTIVE = (
    "Find profitable strategies for Kalshi daily temperature markets using weather forecasts."
)


def fetched(prefix: str) -> list[Fetched]:
    return [
        Fetched(
            receipt=Receipt(
                url=url,
                status=status,
                received_at=NOW,
                sha256="sha256:" + "0" * 64,
                size=len(body),
                headers=headers,
            ),
            body=body,
        )
        for url, (status, headers, body) in recorded().items()
        if prefix in url
    ]


PARAMS = {"entity": "CLIPHL", "series": "KXHIGHPHIL", "start": "2026-11-06", "end": "2026-11-12"}


def test_pfm_products_parse_with_issuance_clocks_and_fail_closed() -> None:
    catalog = load_catalog(REPO)
    params = PARAMS | catalog["iem-nws-pfm"].entities["CLIPHL"]
    parsed = ADAPTERS["iem_afos_pfm"].parse(fetched("PFMPHI"), params, NOW)
    assert parsed.records
    for record in parsed.records:
        assert record["timing_basis"] == "provider_publication"
        assert record["available_at"] == record["published_at"]
        assert datetime.fromisoformat(record["available_at"]) <= NOW
        assert -60 <= Decimal(record["value"]) <= 140
        assert "2026-11-06" <= record["valid_on"] <= "2026-11-12"
        # A forecast is never issued after its own target day.
        assert datetime.fromisoformat(record["available_at"]).date() <= date.fromisoformat(
            record["valid_on"]
        )
    revisions = parsed.slices[
        (DataKind.FORECAST_REVISIONS, "daytime_max_f", "iem-nws-pfm", "issuance")
    ]["CLIPHL"]
    assert len(revisions) == 7  # every target day has several issued vintages
    product = next(products(fetched("PFMPHI")[0].body.decode()))
    with pytest.raises(ValueError, match="location does not match"):
        pfm_maxima(product, "Philadelphia-Philadelphia PA", "41.00", "75.24")
    with pytest.raises(ValueError, match="not present"):
        pfm_maxima(product, "Atlantis-Nowhere NJ", "39.87", "75.24")
    tampered = product.replace("FOUS51 KPHI ", "FOUS51 KPHI 0", 1)
    with pytest.raises(ValueError, match=r"WMO header|issuance"):
        issuance(tampered)


def test_cli_reports_use_final_issuance_and_refuse_same_day_reports() -> None:
    params = PARAMS | {"pil": "CLIPHL"}
    parsed = ADAPTERS["iem_afos_cli"].parse(fetched("CLIPHL"), params, NOW)
    days = {r["valid_on"] for r in parsed.records}
    assert days == {f"2026-11-{d:02d}" for d in range(6, 13)}
    assert parsed.refused > 0  # afternoon "valid today" reports
    for record in parsed.records:
        assert datetime.fromisoformat(record["available_at"]).date() > date.fromisoformat(
            record["valid_on"]
        )
        assert record["role"] == "observation"


def test_settlement_labels_and_contracts_parse_from_authority_receipts() -> None:
    labels = ADAPTERS["weather_company_labels"].parse(fetched("weather.com"), PARAMS, NOW)
    assert len(labels.records) == 7
    assert {r["source_id"] for r in labels.records} == {"weather-company"}
    assert all(r["timing_basis"] == "received" for r in labels.records)
    contracts = ADAPTERS["kalshi_settled_markets"].parse(fetched("elections.kalshi"), PARAMS, NOW)
    assert contracts.records
    assert {r["settlement_sources"][0] for r in contracts.records} == {"The Weather Company"}
    assert all(r["rules_basis"] == "retrieved_after_settlement" for r in contracts.records)
    assert all(r["result"] in {"yes", "no"} for r in contracts.records)


def test_transport_allowlist_blocks_everything_outside_the_catalog() -> None:
    source = load_catalog(REPO)["iem-nws-cli"]
    inner = httpx.MockTransport(lambda request: httpx.Response(200, content=b"ok"))
    transport = AllowlistTransport(source, inner)
    with httpx.Client(transport=transport) as client:
        good = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=CLIPHL"
        assert client.get(good).status_code == 200
        for url in (
            "http://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py",
            "https://mesonet.agron.iastate.edu/other",
            "https://example.invalid/cgi-bin/afos/retrieve.py",
            "https://user:pw@mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py",
        ):
            with pytest.raises(AcquisitionError):
                client.get(url)
        with pytest.raises(AcquisitionError):
            client.post(good)
        with pytest.raises(AcquisitionError):
            client.get(good, headers={"Authorization": "Bearer x"})
    compressed = AllowlistTransport(
        source,
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, content=gzip.compress(b'{"ok": 1}')
            )
        ),
    )
    with httpx.Client(transport=compressed) as client:
        assert client.get(good).json() == {"ok": 1}  # decoded once, exactly
    huge = AllowlistTransport(
        source, httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 9_000_000))
    )
    with httpx.Client(transport=huge) as client, pytest.raises(AcquisitionError, match="byte"):
        client.get(good)


def requirement(**changes: Any) -> DataRequirement:
    base: dict[str, Any] = {
        "requirement_id": "r",
        "kind": DataKind.FORECAST_VINTAGES,
        "family": "weather",
        "entity": "CLIPHL",
        "series": "KXHIGHPHIL",
        "variable": "daytime_max_f",
        "start": date(2026, 10, 1),
        "end": date(2026, 11, 1),
        "clock": "issuance",
        "min_events": 5,
        "blocking": "predictive",
        "purpose": "test requirement",
    }
    return DataRequirement.model_validate(base | changes)


def test_source_evaluation_checks_clocks_authority_coverage_and_authorization() -> None:
    catalog = load_catalog(REPO)
    today = NOW.date()
    assert evaluate(catalog["iem-nws-pfm"], requirement(), today=today).decision == "acquire"
    hindsight = evaluate(catalog["open-meteo-previous-runs"], requirement(), today=today)
    assert hindsight.decision == "reject"
    assert hindsight.checks["clock"] is False
    unmapped = evaluate(catalog["iem-nws-pfm"], requirement(entity="CLIMDW"), today=today)
    assert unmapped.decision == "reject"
    label = requirement(kind=DataKind.SETTLEMENT_LABELS, variable="daily_high_f", clock="receipt")
    assert evaluate(catalog["weather-company-labels"], label, today=today).decision == "acquire"
    quotes = requirement(
        kind=DataKind.DECISION_QUOTES,
        variable="yes_quotes",
        clock="receipt",
        fidelity="quote",
        entity="KXHIGHPHIL",
    )
    assert (
        evaluate(catalog["kalshi-orderbook-forward"], quotes, today=today).decision
        == "forward_collect"
    )
    fee = requirement(
        kind=DataKind.FEE_SCHEDULE, variable="fee_schedule", clock="any", entity="KXHIGHPHIL"
    )
    assert (
        evaluate(catalog["kalshi-fee-schedule"], fee, today=today).decision
        == "authorization_required"
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never reach a real source; acquisition uses replayed responses."""

    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("unit test attempted a real network request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


def service(
    tmp_path: Path, transport: httpx.BaseTransport, clock: SimulatedClock
) -> ResearchService:
    return ResearchService(
        tmp_path / "workspace",
        REPO,
        clock=clock,
        transport=transport,
        sleep=lambda _: None,
    )


@pytest.fixture
def small_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    # The recorded window has seven days; the quick depth needs 20 in production.
    monkeypatch.setitem(model.MIN_EVENTS, "quick", 5)


def submit(svc: ResearchService, **extra: Any) -> str:
    request = {
        "objective": OBJECTIVE,
        "family": "weather",
        "lookback_days": 7,
        "validation_depth": "quick",
    }
    return str(svc.submit(request | extra)["id"])


@pytest.mark.usefixtures("small_depth")
def test_vertical_slice_acquires_registers_features_and_awaits_forward_evidence(
    tmp_path: Path,
) -> None:
    transport = ReplayTransport()
    clock = SimulatedClock(NOW)
    svc = service(tmp_path, transport, clock)
    job_id = submit(svc)
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    assert transport.unknown == []
    assert job["status"] == JobStatus.AWAITING_OBSERVATIONS
    completed = {a["source_id"] for a in job["acquisitions"] if a["status"] == "completed"}
    assert completed == {
        "iem-nws-pfm",
        "iem-nws-cli",
        "weather-company-labels",
        "kalshi-settled-markets",
    }
    # Immutable datasets, preserved raw bytes, receipt hashes.
    root = tmp_path / "workspace" / "research"
    for acquisition in job["acquisitions"]:
        path = root / "datasets" / ("sha256-" + acquisition["dataset_id"].removeprefix("sha256:"))
        manifest = json.loads((path / "manifest.json").read_text())
        for raw in manifest["raw_hashes"]:
            hexdigest = raw.removeprefix("sha256:")
            assert (root / "raw" / hexdigest[:2] / hexdigest).is_file()
    states = {(r["kind"], r["variable"]): r["assessment"]["status"] for r in job["requirements"]}
    assert states[("forecast_vintages", "daytime_max_f")] == AssessmentStatus.SATISFIED
    assert states[("reference_observations", "daily_high_f")] == AssessmentStatus.SATISFIED
    assert states[("settlement_labels", "daily_high_f")] == AssessmentStatus.SATISFIED
    assert states[("decision_quotes", "yes_quotes")] == AssessmentStatus.AWAITING_OBSERVATIONS
    assert (
        states[("forecast_vintages", "ensemble_member_f")]
        == AssessmentStatus.AWAITING_AUTHORIZATION
    )
    assert (
        states[("intraday_observations", "temperature_f")]
        == AssessmentStatus.AWAITING_AUTHORIZATION
    )
    features = {f["feature_id"]: f for f in job["features"]}
    assert {"nws_pfm_max_f", "nws_pfm_revision_f", "nws_cli_bias_f", "settlement_high_f"} <= set(
        features
    )
    assert features["nws_pfm_max_f"]["events"] == 7
    assert features["nws_cli_bias_f"]["non_null"] > 0
    artifact = (
        root
        / "features"
        / ("sha256-" + features["nws_pfm_max_f"]["artifact_id"].removeprefix("sha256:"))
    )
    for line in (artifact / "values.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["value"] is not None:
            assert row["inputs_available_at"] <= row["decision_time"]
    bias = next(
        h
        for h in job["hypotheses"]
        if h["spec"]["provenance"]["template_id"] == "weather-forecast-bias"
    )
    assert bias["facets"]["predictive"]["ready"] is True
    assert bias["status"] == HypothesisStatus.AWAITING_AUTHORIZATION  # fee certification is human
    assert any("fee" in r for r in bias["reasons"])
    forward = {(f["kind"], f["variable"]): f for f in job["forward_requests"]}
    assert forward[("decision_quotes", "yes_quotes")]["collector_status"] == "covered"
    assert forward[("forecast_vintages", "hourly_temperature_f")]["collector_status"] == "covered"
    ensemble = forward[("forecast_vintages", "ensemble_member_f")]
    assert ensemble["collector_status"] == "requires_collector_change"
    assert ensemble["status"] == "blocked_collector_change"
    assert svc.store.runnable(NOW) is None
    # Reevaluation: no AI call, no identical download.
    calls = len(transport.requested)
    clock.advance(timedelta(hours=7))
    svc.run_until_idle()
    assert len(transport.requested) == calls
    assert svc.store.get_job(job_id)["status"] == JobStatus.AWAITING_OBSERVATIONS  # type: ignore[index]
    # Genuine prospective quotes arrive (here: controlled shadow-monitor rows).
    arrive_quotes(tmp_path / "workspace")
    clock.advance(timedelta(hours=7))
    svc.run_until_idle()
    after = svc.detail(job_id)
    assert after is not None
    quotes = next(r for r in after["requirements"] if r["kind"] == "decision_quotes")
    assert quotes["assessment"]["status"] == AssessmentStatus.SATISFIED
    assert (
        next(f for f in after["forward_requests"] if f["kind"] == "decision_quotes")["status"]
        == "satisfied"
    )
    assert len(transport.requested) == calls


def arrive_quotes(workspace: Path) -> None:
    from entropytrade.api.jobs import Jobs
    from entropytrade.tracking.store import TrackingStore

    TrackingStore(Jobs(workspace))
    db = sqlite3.connect(workspace / "jobs.sqlite")
    with db:
        for day in range(6, 13):
            ticker = f"KXHIGHPHIL-26NOV{day:02d}-T60"
            db.execute(
                "INSERT INTO shadow_contracts "
                "VALUES ('m', ?, '{}', '2026-11-14T00:00:00+00:00', NULL)",
                (ticker,),
            )
        db.execute(
            "INSERT INTO shadow_cycles VALUES ('c', 'm', 1, 'completed', "
            "'2026-11-14T00:00:00+00:00', '2026-11-14T00:01:00+00:00', 'test', NULL, NULL)"
        )
    db.close()


@pytest.mark.usefixtures("small_depth")
def test_unavailable_history_is_refused_not_fabricated(tmp_path: Path) -> None:
    svc = service(tmp_path, ReplayTransport(), SimulatedClock(NOW))
    job_id = submit(svc, universe=["KXHIGHCHI"], acquisition="none")
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    assert job["acquisitions"] == []
    pfm = next(
        r
        for r in job["requirements"]
        if r["kind"] == "forecast_vintages" and r["variable"] == "daytime_max_f"
    )
    assert pfm["assessment"]["status"] == AssessmentStatus.UNOBTAINABLE
    bias = next(
        h
        for h in job["hypotheses"]
        if h["spec"]["provenance"]["template_id"] == "weather-forecast-bias"
    )
    assert bias["status"] == HypothesisStatus.INSUFFICIENT_EVIDENCE


@pytest.mark.usefixtures("small_depth")
def test_existing_datasets_satisfy_later_jobs_without_downloading_again(
    tmp_path: Path,
) -> None:
    transport = ReplayTransport()
    svc = service(tmp_path, transport, SimulatedClock(NOW))
    first = submit(svc)
    svc.run_until_idle()
    calls = len(transport.requested)
    second = submit(
        svc, acquisition="ask", validation_depth="quick", lookback_days=7, paper_preference="never"
    )
    svc.run_until_idle()
    assert len(transport.requested) == calls  # inherited, not downloaded again
    job = svc.detail(second)
    assert job is not None
    # The inventory already satisfies the second job, so nothing is planned or fetched.
    assert job["acquisitions"] == []
    satisfied = {r["kind"] for r in job["requirements"] if r["assessment"]["status"] == "satisfied"}
    assert {"forecast_vintages", "reference_observations", "settlement_labels"} <= satisfied
    assert first != second


@pytest.mark.usefixtures("small_depth")
def test_ask_mode_and_transient_failures(tmp_path: Path) -> None:
    transport = ReplayTransport(fail={"weather.com"})
    clock = SimulatedClock(NOW)
    svc = service(tmp_path, transport, clock)
    job_id = submit(svc, acquisition="ask")
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    assert job["status"] == JobStatus.AWAITING_AUTHORIZATION
    assert transport.requested == []
    pending = [a for a in job["acquisitions"] if a["status"] == "awaiting_approval"]
    assert len(pending) == 4
    for item in pending:
        decision = "deny" if item["source_id"] == "kalshi-settled-markets" else "approve"
        assert svc.approve(job_id, {"acquisition_id": item["id"], "decision": decision})
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    statuses = {a["source_id"]: a["status"] for a in job["acquisitions"]}
    assert statuses["kalshi-settled-markets"] == "denied"
    assert statuses["iem-nws-pfm"] == "completed"
    assert statuses["weather-company-labels"] == "queued"  # transient 503: retry scheduled
    assert job["usage"]["http_requests"] > 0
    with pytest.raises(ValueError, match="approve or deny"):
        svc.approve(job_id, {"acquisition_id": pending[0]["id"], "decision": "maybe"})


@pytest.mark.usefixtures("small_depth")
def test_restart_requeues_interrupted_acquisition_and_reuses_bytes(tmp_path: Path) -> None:
    transport = ReplayTransport()
    svc = service(tmp_path, transport, SimulatedClock(NOW))
    job_id = submit(svc)
    while svc.store.get_job(job_id)["status"] != JobStatus.ACQUIRING:  # type: ignore[index]
        svc.step()
    row = svc.store.job_acquisitions(job_id, statuses=("queued",))[0]
    svc.store.start_acquisition(row["id"], now=NOW)  # crash mid-fetch
    restarted = service(tmp_path, transport, SimulatedClock(NOW))
    restarted.recover()
    restarted.run_until_idle()
    job = restarted.detail(job_id)
    assert job is not None
    assert all(a["status"] == "completed" for a in job["acquisitions"])
    records, problems = inventory(tmp_path / "workspace", REPO)
    assert problems == []
    assert any(r.origin == "research_acquisition" for r in records)


@pytest.mark.usefixtures("small_depth")
def test_budget_limits_stop_acquisition(tmp_path: Path) -> None:
    svc = service(tmp_path, ReplayTransport(), SimulatedClock(NOW))
    job_id = submit(svc, budget={"max_http_requests": 2})
    svc.run_until_idle()
    job = svc.detail(job_id)
    assert job is not None
    assert job["usage"]["http_requests"] <= 2
    assert any("budget is exhausted" in e["detail"] for e in job["events"])
    # Unstarted shared acquisitions stay queued for other jobs; this job says why it stopped.
    assert "queued" in {a["status"] for a in job["acquisitions"]}
    assert {a["status"] for a in job["acquisitions"]} <= {"completed", "queued"}
    stopped = [
        r
        for r in job["requirements"]
        if r["assessment"]["reasons"][0].startswith("the job's acquisition budget ran out")
    ]
    assert stopped
    assert {r["assessment"]["status"] for r in stopped} == {AssessmentStatus.MISSING}


def test_collector_status_is_sanitized_and_never_satisfies_by_itself(tmp_path: Path) -> None:
    from entropytrade.research.collector_status import status
    from entropytrade.research.inventory import assess as assess_requirement

    workspace = tmp_path / "restored-copy"
    arrive_quotes(workspace)
    exported = status(workspace, REPO, now=NOW)
    text = json.dumps(exported)
    assert exported["schema"] == "entropytrade-collector-status-v1"
    assert '"{}"' not in text  # no captured market payloads
    assert "KXHIGHPHIL" in text
    target = tmp_path / "research-workspace" / "research" / "collector-status"
    target.mkdir(parents=True)
    (target / "status.json").write_text(text)
    records, problems = inventory(tmp_path / "research-workspace", REPO)
    assert problems == []
    remote = [r for r in records if r.origin == "collector_status"]
    assert remote
    need = requirement(
        kind=DataKind.DECISION_QUOTES,
        variable="yes_quotes",
        clock="receipt",
        fidelity="quote",
        entity="KXHIGHPHIL",
        start=date(2026, 11, 6),
        end=date(2026, 11, 12),
    )
    result = assess_requirement(need, records, NOW)
    assert result.status is AssessmentStatus.MISSING
    assert any("collector host" in r for r in result.reasons)


@pytest.mark.usefixtures("small_depth")
def test_preapproved_job_is_not_blocked_by_another_jobs_pending_ask(tmp_path: Path) -> None:
    transport = ReplayTransport()
    svc = service(tmp_path, transport, SimulatedClock(NOW))
    asking = submit(svc, acquisition="ask")
    svc.run_until_idle()
    assert svc.store.get_job(asking)["status"] == JobStatus.AWAITING_AUTHORIZATION  # type: ignore[index]
    automatic = submit(svc, validation_depth="quick", paper_preference="never")
    svc.run_until_idle()
    job = svc.detail(automatic)
    assert job is not None
    assert {a["status"] for a in job["acquisitions"]} == {"completed"}
    assert job["status"] == JobStatus.AWAITING_OBSERVATIONS


def test_shared_forward_request_requires_the_largest_minimum(tmp_path: Path) -> None:
    from entropytrade.research.store import ResearchStore

    store = ResearchStore(tmp_path / "research")
    quick = requirement(
        kind=DataKind.DECISION_QUOTES,
        variable="yes_quotes",
        clock="receipt",
        fidelity="quote",
        entity="KXHIGHPHIL",
        min_events=60,
    )
    common = {
        "source_id": "kalshi-orderbook-forward",
        "collector": "canonical_local_chain",
        "collector_status": "covered",
        "detail": "covered",
        "now": NOW,
        "next_check_at": NOW,
    }
    store.plan_forward(quick, events_observed=25, **common)  # type: ignore[arg-type]
    store.plan_forward(quick.revalidated(min_events=20), events_observed=25, **common)  # type: ignore[arg-type]
    (row,) = store.forward_requests()
    assert (row["events_required"], row["status"]) == (60, "awaiting_observations")
