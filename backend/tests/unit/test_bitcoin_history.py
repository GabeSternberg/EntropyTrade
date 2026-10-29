"""Controlled clocks/wire and synthetic models; no empirical performance assertions."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.agents.evidence import EvidenceConfig
from entropytrade.agents.fixture import demo_specs
from entropytrade.api.jobs import Jobs, validate_request
from entropytrade.api.worker import execute_job, review_result
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import AdapterRegistry, ContractSample, ExperimentData
from entropytrade.experiments.workflow import research_and_test
from entropytrade.families.bitcoin_history import (
    SECONDARY,
    OutcomeTransport,
    build_history,
    capture_samples,
    history_data,
    recognized_terms,
)
from entropytrade.families.bitcoin_models import MODELS, BitcoinPredictions, history_readiness
from entropytrade.families.public import capture_public
from entropytrade.features.registry import scientific_hash
from tests.exchange.test_gateway_http import _market_body
from tests.unit.test_public_families import weather

REPO = Path(__file__).resolve().parents[3]
AT = datetime(2026, 10, 25, 15, tzinfo=UTC)


def body() -> dict[str, Any]:
    value = _market_body()
    value.update(
        ticker="KXBTC-26OCT2517-T100000",
        event_ticker="KXBTC-26OCT2517",
        title="CONTROLLED Bitcoin rule fixture",
        floor_strike="100000",
        open_time="2026-10-24T00:00:00Z",
        close_time="2026-10-25T21:00:00Z",
        latest_expiration_time="2026-10-26T21:00:00Z",
        rules_primary=(
            "If the simple average of the sixty seconds of CF Benchmarks' "
            "Bitcoin Real-Time Index (BRTI) before 5 PM EDT is above 100000 "
            "at 5 PM EDT on Oct 25, 2026, then the market resolves to Yes."
        ),
        rules_secondary=SECONDARY,
    )
    return value


def capture(root: Path, at: datetime = AT) -> Path:
    def listing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"markets": [body()], "cursor": ""})

    def spot(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"price": "100100", "time": at.isoformat()})

    asyncio.run(
        capture_public(
            root,
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(at),
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(spot),
        )
    )
    return root


@pytest.mark.parametrize(
    "mutation", ["negated", "secondary", "zone", "strike", "close", "exception"]
)
def test_rule_recognition_rejects_ambiguous_or_inconsistent_terms(mutation: str) -> None:
    raw = body()
    assert recognized_terms(market_from_body(raw, captured_at=AT, series="KXBTC")) == date(
        2026, 10, 25
    )
    if mutation == "negated":
        raw["rules_primary"] = "Do not use CF Benchmarks. " + raw["rules_primary"]
    elif mutation == "secondary":
        raw["rules_secondary"] += " May use a different index."
    elif mutation == "zone":
        raw["rules_primary"] = raw["rules_primary"].replace("EDT", "EST")
    elif mutation == "strike":
        raw["floor_strike"] = "100001"
    elif mutation == "close":
        raw["close_time"] = "2026-10-25T20:00:00Z"
    else:
        raw["early_close_condition"] = "special resolution condition"
    assert recognized_terms(market_from_body(raw, captured_at=AT, series="KXBTC")) is None


def test_history_reconciles_official_targets_with_receipt_clock_and_archive_fallback(
    tmp_path: Path,
) -> None:
    source = capture(tmp_path / "capture")
    calls = []
    received = AT + timedelta(days=1)

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.method == "GET"
        assert not any("authorization" in key or "kalshi-access" in key for key in request.headers)
        if "/historical/" not in request.url.path:
            return httpx.Response(404, json={"error": {"code": "not_found", "message": "archived"}})
        raw = body()
        raw.update(
            status="finalized",
            result="yes",
            settlement_value_dollars="1.0000",
            settlement_ts="2026-10-25T21:05:00Z",
        )
        return httpx.Response(200, json={"market": raw})

    result = asyncio.run(
        build_history(
            tmp_path / "history",
            [source, source],
            clock=SimulatedClock(received),
            transport=httpx.MockTransport(response),
        )
    )
    sample = result.samples[0]
    assert len(calls) == 2
    assert sample.outcome is MarketResult.YES
    assert sample.outcome_available_at == received
    assert sample.decision_time == AT
    assert not sample.rules_known
    assert sample.book is None
    assert not result.protected_events
    assert result.provenance["partition"]["holdout_start"] == "2027-01-23"
    assert result.provenance["capture_count"] == 1
    assert history_data(tmp_path / "history") == result
    # Restart/retry uses original finalized receipt, without another network request.
    again = asyncio.run(
        build_history(
            tmp_path / "again",
            [source],
            previous=[tmp_path / "history"],
            clock=SimulatedClock(received + timedelta(days=1)),
            transport=httpx.MockTransport(lambda r: pytest.fail("resolved target was refetched")),
        )
    )
    assert again.samples[0].outcome_available_at == received
    assert again.provenance["partition"] == result.provenance["partition"]
    assert again.provenance["reconciliation"]["requested"] == 0
    (tmp_path / "history/outcomes/0001.json").write_text("{}")
    with pytest.raises(ValueError, match="checksum/path"):
        history_data(tmp_path / "history")


@pytest.mark.parametrize("status", ["determined", "disputed", "amended"])
def test_nonfinal_result_cannot_become_training_label(tmp_path: Path, status: str) -> None:
    source = capture(tmp_path / "capture")
    raw = body()
    raw.update(
        status=status,
        result="yes",
        settlement_value_dollars="1.0000",
        settlement_ts="2026-10-25T21:05:00Z",
    )
    data = asyncio.run(
        build_history(
            tmp_path / "history",
            [source],
            clock=SimulatedClock(AT + timedelta(days=1)),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"market": raw})),
        )
    )
    assert data.samples[0].outcome is None


def test_raw_normalization_and_snapshot_path_checks_fail_closed(tmp_path: Path) -> None:
    source = capture(tmp_path / "capture")
    assert capture_samples(source)
    normalized = source / "markets.jsonl"
    item = json.loads(normalized.read_text())
    item["market"]["close_time"] = "2026-10-25T22:00:00Z"
    normalized.write_text(json.dumps(item) + "\n")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["checksums"]["markets.jsonl"] = file_hash(normalized)
    manifest.pop("dataset_version")
    manifest["dataset_version"] = scientific_hash(manifest)
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="normalization disagrees"):
        capture_samples(source)


def test_offline_snapshot_keeps_fixed_partition_and_earliest_event(tmp_path: Path) -> None:
    source = capture(tmp_path / "capture")
    result = asyncio.run(build_history(tmp_path / "history", [source], fetch=False))
    assert result.provenance["reconciliation"]["fetch_enabled"] is False
    assert result.provenance["reconciliation"]["requested"] == 0
    assert result.provenance["reconciliation"]["receipts"] == []
    assert all(s.outcome is None for s in result.samples)
    later = capture(tmp_path / "later", AT + timedelta(minutes=30))
    inherited = asyncio.run(
        build_history(
            tmp_path / "inherited", [source, later], previous=[tmp_path / "history"], fetch=False
        )
    )
    assert inherited.provenance["partition"] == result.provenance["partition"]
    assert len(inherited.samples) == len(result.samples)
    assert inherited.samples[0].decision_time == AT


def test_outcome_transport_denies_accounts_foreign_tickers_auth_and_writes() -> None:
    async def check() -> None:
        async with httpx.AsyncClient(
            transport=OutcomeTransport(
                ["KXBTC-X-T1"], httpx.MockTransport(lambda r: httpx.Response(200))
            )
        ) as client:
            for url in [
                "https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
                "https://api.elections.kalshi.com/trade-api/v2/markets/OTHER",
                "http://api.elections.kalshi.com/trade-api/v2/markets/KXBTC-X-T1",
            ]:
                with pytest.raises(ValueError, match="denied"):
                    await client.get(url)
            url = "https://api.elections.kalshi.com/trade-api/v2/markets/KXBTC-X-T1"
            with pytest.raises(ValueError, match="denied"):
                await client.get(url, headers={"Authorization": "fixture"})
            with pytest.raises(ValueError, match="budget"):
                await client.post(url)

    asyncio.run(check())


def model_data() -> ExperimentData:
    samples = []
    for index in range(120):
        at = datetime(2025, 1, 1, 12, tzinfo=UTC) + timedelta(days=index)
        for strike, value in enumerate((Decimal(-1), Decimal(0), Decimal(1))):
            samples.append(
                ContractSample(
                    event_id=f"KXBTC-{index}",
                    ticker=f"KXBTC-{index}-T{strike}",
                    family="KXBTC",
                    target_date=at.date(),
                    decision_time=at,
                    close_time=at + timedelta(hours=1),
                    features_available_at=at,
                    features={"scaled_moneyness": value, "hours_to_close": Decimal(1)},
                    versions={"scaled_moneyness": "1", "hours_to_close": "1"},
                    feature_hash=scientific_hash({"event": index, "strike": strike}),
                    sources=("coinbase", "kalshi"),
                    rules_known=False,
                    eligible=True,
                    outcome=MarketResult.YES
                    if (strike == 2 or (strike == 1 and index % 2))
                    else MarketResult.NO,
                    outcome_available_at=at + timedelta(hours=2),
                )
            )
    return ExperimentData(
        dataset_version="controlled-synthetic",
        feature_version="controlled-features",
        data_kind="synthetic",
        samples=tuple(samples),
        protected_events=frozenset(f"KXBTC-{i}" for i in range(90, 120)),
        feature_definitions={
            "features": [
                {"name": n, "version": "1"} for n in ("scaled_moneyness", "hours_to_close")
            ]
        },
        provenance={
            "source_kinds": ["coinbase", "kalshi"],
            "partition": {
                "anchor": "2025-01-01",
                "fit_before": "2025-03-02",
                "holdout_start": "2025-04-01",
            },
        },
    )


def test_binary_models_are_monotone_deterministic_and_ignore_later_labels(tmp_path: Path) -> None:
    data = model_data()
    first = BitcoinPredictions(data, tmp_path / "first").prepare(demo_specs()[0], MODELS[0])
    assert first.records
    assert {r.family for r in first.records} == set(MODELS)
    assert all(
        r.partition == "validation" and r.event_id not in data.protected_events
        for r in first.records
    )
    assert first.model_metadata["parameters"]["coefficient"] > 0
    changed = data.revalidated(
        samples=tuple(
            s.revalidated(outcome=MarketResult.YES)
            if s.event_id not in first.model_metadata["split"]["fit"]
            else s
            for s in data.samples
        )
    )
    second = BitcoinPredictions(changed, tmp_path / "second").prepare(demo_specs()[0], MODELS[0])
    assert first == second
    # Late receipt dates cannot be backdated to close/settlement for training.
    late = data.revalidated(
        samples=tuple(
            s.revalidated(outcome_available_at=datetime(2026, 1, 1, tzinfo=UTC))
            for s in data.samples
        )
    )
    blocked = BitcoinPredictions(late, tmp_path / "late").prepare(demo_specs()[0], MODELS[0])
    assert not blocked.records
    assert "received before fit cutoff" in blocked.refusals[MODELS[0]]


def test_shared_research_experiments_and_browser_projection_accept_binary_provider(
    tmp_path: Path,
) -> None:
    data = model_data()
    adapters = AdapterRegistry()
    adapters.register(
        "bitcoin", lambda p: data, BitcoinPredictions(data, tmp_path / "workflow/models")
    )
    config = EvidenceConfig(
        root=tmp_path, features="unused", holdout_start=date(2025, 4, 1), model_families=MODELS
    )
    config_path = tmp_path / "evidence.json"
    config_path.write_text(config.model_dump_json())
    result = research_and_test(
        prompt="Test scaled_moneyness > 0",
        evidence_config=config_path,
        output=tmp_path / "workflow",
        registry=tmp_path / "registry.sqlite",
        tracking=tmp_path / "mlflow",
        adapters=adapters,
        market_family="bitcoin",
        offline=True,
        local_templates=True,
    )
    review = review_result(result, tmp_path / "workflow")
    assert review["probabilities"]
    assert all(c["forecast_metrics"]["independent_events"] == 30 for c in result["candidates"])
    assert all(c["benchmark"]["independent_events"] == 30 for c in result["candidates"])
    assert all(
        c["status"] == "INSUFFICIENT_DATA" and not c["scenarios"] for c in result["candidates"]
    )
    assert not review["final_holdout_evaluated"]
    assert all("outcome" not in p and p["split"] == "validation" for p in review["probabilities"])


def test_conflicting_event_dates_cannot_cross_model_partitions(tmp_path: Path) -> None:
    data = model_data()
    conflicting = data.samples[0].revalidated(target_date=date(2025, 4, 10))
    data = data.revalidated(samples=(conflicting, *data.samples[1:]))
    bundle = BitcoinPredictions(data, tmp_path).prepare(demo_specs()[0], MODELS[0])
    assert not bundle.records
    assert "cannot span multiple target dates" in bundle.refusals[MODELS[0]]


def test_readiness_uses_event_counts_and_receipt_cutoffs_without_exposing_holdout() -> None:
    data = model_data()
    ready = history_readiness(data)
    assert ready["minimum_evidence_met"]
    assert ready["fit"]["events"] == ready["fit"]["dates"] == 60  # 180 related strikes
    assert ready["validation"]["events"] == ready["validation_labeled"]["events"] == 30
    # Every fitting label is received after the frozen fit cutoff. Validation remains
    # separate; neither its labels nor final holdout labels can repair training history.
    late = data.revalidated(
        samples=tuple(
            s.revalidated(outcome_available_at=datetime(2026, 1, 1, tzinfo=UTC))
            if s.target_date < date(2025, 3, 2)
            else s
            for s in data.samples
        )
    )
    blocked = history_readiness(late)
    assert not blocked["minimum_evidence_met"]
    assert blocked["fit"]["events"] == blocked["fit"]["dates"] == 0
    assert blocked["fit"]["missing_events"] == 40
    assert blocked["fit"]["missing_dates"] == 20
    assert blocked["fit_outcome_classes"] == []
    assert blocked["validation"] == ready["validation"]
    assert blocked["validation_labeled"] == ready["validation_labeled"]
    assert all("KXBTC-" not in summary for summary in blocked["summaries"])


def test_readiness_reports_single_class_and_unlabeled_validation(tmp_path: Path) -> None:
    data = model_data()
    data = data.revalidated(
        samples=tuple(
            s.revalidated(outcome=None, outcome_available_at=None)
            if date(2025, 3, 2) <= s.target_date < date(2025, 4, 1)
            else s.revalidated(outcome=MarketResult.NO)
            for s in data.samples
        )
    )
    blocked = history_readiness(data)
    assert not blocked["minimum_evidence_met"]
    assert blocked["fit"]["missing_events"] == blocked["fit"]["missing_dates"] == 0
    assert blocked["fit_outcome_classes"] == [MarketResult.NO.value]
    assert blocked["validation"]["events"] == 30
    assert blocked["validation_labeled"]["events"] == 0
    bundle = BitcoinPredictions(data, tmp_path).prepare(demo_specs()[0], MODELS[0])
    assert not bundle.records
    assert bundle.model_metadata["history_readiness"] == blocked
    assert "both binary outcomes" in bundle.refusals[MODELS[0]]


def test_empty_workspace_history_is_a_saved_honest_review(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    request = {"idea": "Research Bitcoin spot", "family": "bitcoin", "mode": "history"}
    assert validate_request(request) == request
    with pytest.raises(ValueError, match="Bitcoin only"):
        validate_request({**request, "family": "weather"})
    job_id = jobs.create(request)
    jobs.update(job_id, "starting", "Worker starting")
    execute_job(jobs, REPO, job_id)
    job = jobs.get(job_id)
    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["bitcoin_history"]["capture_count"] == 0
    assert not job["result"]["probabilities"]
    assert all(c["status"] == "UNSUPPORTED" for c in job["result"]["candidates"])
    jobs.recover()
    assert jobs.get(job_id) == job
