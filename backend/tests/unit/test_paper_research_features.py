"""Exact C feature definitions in forward paper cycles; source bytes are controlled replays."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketStatus, MarketType, StrikeType
from entropytrade.domain.market import (
    Market,
    MarketRules,
    PriceRange,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.domain.time import SimulatedClock
from entropytrade.experiments.data import ContractSample, ExperimentData
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import RawStore
from entropytrade.research.materialize import materialize
from entropytrade.research.model import DecisionPoint
from entropytrade.research.registry import FeatureRegistry
from entropytrade.tracking.research_features import (
    SourceTransport,
    acquire_research_features,
    load_research_evidence,
    materialize_research_features,
)
from tests.research_fixture_support import recorded

REPO = Path(__file__).resolve().parents[3]
WHEN = datetime(2026, 11, 11, 23, 0, 10, tzinfo=UTC)
DAY = date(2026, 11, 12)
TICKER = "KXHIGHPHIL-26NOV12-T80"


async def no_sleep(_: float) -> None:
    pass


def fixture(
    names: tuple[str, ...] = ("nws_pfm_max_f", "nws_cli_bias_f"),
) -> tuple[ExperimentData, dict[str, Any], Market]:
    registry = FeatureRegistry()
    definitions = [registry.get(name).model_dump(mode="json") for name in names]
    binding = {
        "kind": "research_weather_v1",
        "status": "bound",
        "snapshot": {
            "features": definitions,
            "feature_names": names,
            "feature_schema_hash": scientific_hash(definitions),
            "selected_schedule": {"day_offset": -1, "local_time": "18:00:00"},
            "max_decision_delay_seconds": 60,
            "protected_events": [],
            "series_locations": {
                "KXHIGHPHIL": {
                    "entity": "CLIPHL",
                    "timezone": "America/New_York",
                    "name": "Philadelphia",
                }
            },
        },
    }
    binding["binding_hash"] = scientific_hash(binding)
    market = Market(
        ticker=TICKER,
        event_ticker="KXHIGHPHIL-26NOV12",
        series_ticker="KXHIGHPHIL",
        market_type=MarketType.BINARY,
        title="CONTROLLED forward Philadelphia contract",
        status=MarketStatus.ACTIVE,
        open_time=WHEN - timedelta(days=1),
        close_time=WHEN + timedelta(days=2),
        strike=Strike(strike_type=StrikeType.GREATER, floor=Decimal(80)),
        rules=MarketRules(
            market_ticker=TICKER,
            rules_primary=(
                "Highest Philadelphia temperature in Fahrenheit according to The Weather Company."
            ),
            settlement_sources=(SettlementSource(name="The Weather Company"),),
            settlement_basis="contract_text",
            settlement_target_date=DAY,
            captured_at=WHEN - timedelta(minutes=1),
        ),
        tick_schedule=TickSchedule(
            ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal(".01")),)
        ),
    )
    sample = ContractSample(
        event_id=market.event_ticker,
        ticker=TICKER,
        family="KXHIGHPHIL",
        target_date=DAY,
        decision_time=WHEN - timedelta(seconds=5),
        close_time=market.close_time,
        features_available_at=WHEN - timedelta(seconds=10),
        features={"forecast_high_f": None, "hours_to_close": Decimal(48)},
        versions={"forecast_high_f": "1", "hours_to_close": "1"},
        feature_hash=scientific_hash({"CONTROLLED": "legacy-hourly-missing"}),
        sources=("kalshi",),
        rules_known=True,
        eligible=False,
    )
    data = ExperimentData(
        dataset_version=scientific_hash({"CONTROLLED": "forward"}),
        feature_version=scientific_hash({"CONTROLLED": "legacy-hourly"}),
        data_kind="real",
        samples=(sample,),
        feature_definitions={"features": []},
        provenance={"adapter": "public-forward-v1:weather"},
    )
    return data, binding, market


def source_transport(*, fail: bool = False) -> httpx.MockTransport:
    responses = recorded()
    pfm = b"\n".join(body for url, (_, _, body) in responses.items() if "PFMPHI" in url)
    cli = b"\n".join(body for url, (_, _, body) in responses.items() if "CLIPHL" in url)

    def get(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "mesonet.agron.iastate.edu"
        assert not request.headers.get("Authorization")
        if fail:
            return httpx.Response(503, content=b"CONTROLLED source unavailable")
        return httpx.Response(200, content=pfm if request.url.params["pil"] == "PFMPHI" else cli)

    return httpx.MockTransport(get)


def acquire(
    tmp_path: Path, data: ExperimentData, binding: dict[str, Any], *, fail: bool = False
) -> Any:
    return asyncio.run(
        acquire_research_features(
            tmp_path / "research-features",
            REPO,
            data,
            binding,
            transport=source_transport(fail=fail),
            clock=SimulatedClock(WHEN),
            sleep=no_sleep,
        )
    )


def test_authentic_pfm_cli_bytes_materialize_exact_features_after_receipts(tmp_path: Path) -> None:
    data, binding, market = fixture()
    evidence = acquire(tmp_path, data, binding)
    assert not evidence.failures
    assert evidence.requests <= 8
    assert evidence.manifests
    at = WHEN + timedelta(seconds=10)
    data = data.revalidated(samples=(data.samples[0].revalidated(decision_time=at),))
    result = materialize_research_features(data, evidence, {TICKER: market}, binding)
    sample = result.samples[0]
    assert sample.eligible
    assert set(sample.features) == {"nws_pfm_max_f", "nws_cli_bias_f"}
    assert "forecast_high_f" not in sample.features
    assert "verified-research-features" in sample.sources
    assert sample.features_available_at == WHEN
    assert sample.features_available_at < sample.decision_time
    assert result.provenance["feature_schema_hash"] == binding["snapshot"]["feature_schema_hash"]
    assert result.feature_definitions["features"] == binding["snapshot"]["features"]
    for receipt in evidence.receipts:
        assert RawStore(evidence.root).get(receipt["sha256"])
    files_before = {
        str(path.relative_to(evidence.root)): file_hash(path)
        for path in evidence.root.rglob("*")
        if path.is_file()
    }
    loaded = load_research_evidence(evidence.root, binding)
    rebuilt = materialize_research_features(data, loaded, {TICKER: market}, binding, persist=False)
    assert rebuilt == result
    assert files_before == {
        str(path.relative_to(evidence.root)): file_hash(path)
        for path in evidence.root.rglob("*")
        if path.is_file()
    }


def test_pfm_revision_is_not_hourly_difference(tmp_path: Path) -> None:
    data, binding, market = fixture(("nws_pfm_max_f", "nws_pfm_revision_f"))
    evidence = acquire(tmp_path, data, binding)
    data = data.revalidated(
        samples=(data.samples[0].revalidated(decision_time=WHEN + timedelta(seconds=10)),)
    )
    result = materialize_research_features(data, evidence, {TICKER: market}, binding)
    assert result.samples[0].features["nws_pfm_revision_f"] is not None
    records = evidence.records["CLIPHL"]
    definition = FeatureRegistry().get("nws_pfm_revision_f")
    point = DecisionPoint(day_offset=-1, local_time=datetime.min.time().replace(hour=18, second=20))
    expected = materialize(
        definition,
        entity="CLIPHL",
        timezone="America/New_York",
        schedule=[point],
        window=(DAY, DAY),
        inputs={"forecast": records},
    )[0]
    assert result.samples[0].features["nws_pfm_revision_f"] == Decimal(expected["value"])


@pytest.mark.parametrize(
    "condition",
    [
        "source_failure",
        "outside_window",
        "protected",
        "future_receipt",
        "wrong_payout",
        "wrong_authority",
    ],
)
def test_missing_or_incompatible_evidence_blocks_paper_features(
    tmp_path: Path, condition: str
) -> None:
    data, binding, market = fixture()
    if condition == "outside_window":
        binding["snapshot"]["selected_schedule"]["local_time"] = "17:00:00"
    elif condition == "protected":
        binding["snapshot"]["protected_events"] = ["CLIPHL:" + DAY.isoformat()]
    binding["binding_hash"] = scientific_hash(
        {key: value for key, value in binding.items() if key != "binding_hash"}
    )
    evidence = acquire(tmp_path, data, binding, fail=condition == "source_failure")
    if condition in {"outside_window", "protected"}:
        assert evidence.requests == 0
    decision = (
        WHEN - timedelta(seconds=1)
        if condition == "future_receipt"
        else WHEN + timedelta(seconds=10)
    )
    data = data.revalidated(samples=(data.samples[0].revalidated(decision_time=decision),))
    if condition == "wrong_payout":
        market = market.revalidated(market_type=MarketType.SCALAR)
    elif condition == "wrong_authority":
        market = market.revalidated(
            rules=market.rules.revalidated(settlement_sources=(SettlementSource(name="NWS"),))
        )
    result = materialize_research_features(data, evidence, {TICKER: market}, binding)
    assert not result.samples or not result.samples[0].eligible


def test_allowlist_blocks_arbitrary_hosts_methods_and_credentials() -> None:
    from entropytrade.research.acquire import AcquisitionError
    from entropytrade.research.sources import load_catalog

    source = load_catalog(REPO)["iem-nws-pfm"]

    async def run() -> None:
        transport = SourceTransport(source, httpx.MockTransport(lambda _: httpx.Response(200)))
        for request in (
            httpx.Request("POST", "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"),
            httpx.Request("GET", "https://example.com/cgi-bin/afos/retrieve.py"),
            httpx.Request(
                "GET",
                "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py",
                headers={"Authorization": "forbidden"},
            ),
        ):
            with pytest.raises(AcquisitionError, match="allowlist"):
                await transport.handle_async_request(request)

    asyncio.run(run())


@pytest.mark.parametrize("limit", ["requests", "bytes"])
def test_acquisition_budgets_stop_extra_source_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
) -> None:
    import entropytrade.tracking.research_features as features

    data, binding, _ = fixture()
    monkeypatch.setattr(features, "MAX_REQUESTS" if limit == "requests" else "MAX_BYTES", 1)
    evidence = acquire(tmp_path, data, binding)
    assert evidence.requests == 1
    assert evidence.failures
    assert "budget" in evidence.failures[-1]["reason"]


def test_canonical_chain_is_refused_before_creating_any_feature_files(tmp_path: Path) -> None:
    data, binding, _ = fixture()
    chain = tmp_path / "chain"
    chain.mkdir()
    with pytest.raises(ValueError, match="canonical"):
        asyncio.run(
            acquire_research_features(
                chain / "research-features",
                REPO,
                data,
                binding,
                transport=source_transport(),
                clock=SimulatedClock(WHEN),
                sleep=no_sleep,
            )
        )
    assert list(chain.iterdir()) == []


def test_materialization_reloads_verified_records_and_detects_changed_raw_bytes(
    tmp_path: Path,
) -> None:
    data, binding, market = fixture()
    evidence = acquire(tmp_path, data, binding)
    # Mutable in-memory caches cannot change the immutable data used for paper decisions.
    evidence.records.clear()
    data = data.revalidated(
        samples=(data.samples[0].revalidated(decision_time=WHEN + timedelta(seconds=10)),)
    )
    result = materialize_research_features(data, evidence, {TICKER: market}, binding)
    assert result.samples[0].eligible
    digest = evidence.receipts[0]["sha256"].removeprefix("sha256:")
    path = evidence.root / "raw" / digest[:2] / digest
    path.write_bytes(b"CONTROLLED corruption")
    with pytest.raises(ValueError, match="checksum"):
        materialize_research_features(data, evidence, {TICKER: market}, binding)


def test_protected_prior_reference_days_do_not_leak_into_bias_feature(tmp_path: Path) -> None:
    data, binding, market = fixture()
    binding["snapshot"]["protected_events"] = ["CLIPHL:2026-11-05", "CLIPHL:2026-11-06"]
    binding["binding_hash"] = scientific_hash(
        {key: value for key, value in binding.items() if key != "binding_hash"}
    )
    evidence = acquire(tmp_path, data, binding)
    data = data.revalidated(
        samples=(data.samples[0].revalidated(decision_time=WHEN + timedelta(seconds=10)),)
    )
    result = materialize_research_features(data, evidence, {TICKER: market}, binding)
    assert result.samples[0].features["nws_pfm_max_f"] is not None
    assert result.samples[0].features["nws_cli_bias_f"] is None
    assert not result.samples[0].eligible


def test_symlinked_parent_is_refused_before_any_source_file_write(tmp_path: Path) -> None:
    data, binding, _ = fixture()
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        asyncio.run(
            acquire_research_features(
                alias / "paper-features",
                REPO,
                data,
                binding,
                transport=source_transport(),
                clock=SimulatedClock(WHEN),
                sleep=no_sleep,
            )
        )
    assert list(target.iterdir()) == []
