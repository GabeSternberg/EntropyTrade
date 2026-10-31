"""Durable multi-cycle integration with explicitly CONTROLLED receipts and injected clocks."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.tracking.replay import verify
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import collect, execute
from tests.exchange.test_gateway_http import _market_body
from tests.shadow_support import execution_wire
from tests.unit.test_public_families import WHEN, listing, spot
from tests.unit.test_tracking import REPO, monitor


def test_multi_cycle_receipts_official_outcomes_and_restart_keep_original_decisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store, family="bitcoin")
    clock = SimulatedClock(WHEN)

    def final(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        ticker = request.url.path.split("/")[-1]
        listing_request = httpx.Request(
            "GET",
            "https://api.elections.kalshi.com/trade-api/v2/markets",
            params={
                "series_ticker": "KXBTC",
                "status": "open",
                **({"cursor": "page2"} if ticker.endswith("100001") else {}),
            },
        )
        body = json.loads(listing(listing_request).content)["markets"][0]
        assert body["ticker"] == ticker
        body.update(
            status="finalized",
            result="no",
            settlement_value_dollars="0.0000",
            settlement_ts="2026-10-26T02:00:00Z",
        )
        return httpx.Response(200, json={"market": body})

    async def controlled(
        snapshot: dict[str, Any],
        repo: Path,
        root: Path,
        *,
        fee_versions: tuple[FeeVersion, ...] = (),
    ) -> dict[str, Any]:
        return await collect(
            snapshot,
            repo,
            root,
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(spot),
            execution_transport=httpx.MockTransport(execution_wire),
            outcome_transport=httpx.MockTransport(final),
            clock=clock,
            fee_versions=fee_versions,
        )

    monkeypatch.setattr("entropytrade.tracking.worker.collect", controlled)
    first = store.claim()
    assert first is not None
    execute(store, REPO, *first)
    before = store.get(monitor_id, export=True)
    assert before is not None
    assert before["cycles"][0]["status"] == "completed"
    original = before["cycles"][0]
    assert len(original["result"]["decisions"]) == 2
    assert all(c["outcome"] is None for c in before["contracts"])
    frozen_files = {
        p: file_hash(p)
        for p in (tmp_path / "shadow" / monitor_id / first[1]).rglob("*")
        if p.is_file()
    }

    clock.advance(timedelta(days=2))
    store.control(monitor_id, "pause")
    store.control(monitor_id, "resume")
    second = store.claim()
    assert second is not None
    execute(store, REPO, *second)
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    after = reopened.get(monitor_id, export=True)
    assert after is not None
    assert after["cycles"][1] == original
    assert len(after["contracts"]) == 2
    assert all(c["outcome"]["available_at"] == clock.now().isoformat() for c in after["contracts"])
    assert all(file_hash(path) == digest for path, digest in frozen_files.items())
    assert not after["submission_enabled"]
    assert after["fills"] == []
    assert after["performance"] is None
    for cycle in after["cycles"]:
        assert verify(tmp_path / "shadow" / monitor_id / cycle["id"])["verified"]
        for artifact in cycle["result"]["artifacts"]:
            assert (
                file_hash(tmp_path / "shadow" / monitor_id / cycle["id"] / artifact["path"])
                == artifact["sha256"]
            )
    inputs = tmp_path / "shadow" / monitor_id / after["cycles"][0]["id"] / "decision-inputs.json"
    inputs.write_text("{}")
    with pytest.raises(ValueError, match="checksum/path mismatch"):
        verify(inputs.parent)


def test_partial_worker_failure_retains_evidence_and_pause_blocks_late_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)

    async def interrupted(
        _snapshot: dict[str, Any],
        _repo: Path,
        root: Path,
        *,
        fee_versions: tuple[FeeVersion, ...] = (),
    ) -> dict[str, Any]:
        (root / "partial.json").write_text('{"evidence":"CONTROLLED partial receipt"}')
        raise ValueError("CONTROLLED interrupted acquisition")

    monkeypatch.setattr("entropytrade.tracking.worker.collect", interrupted)
    claim = store.claim()
    assert claim is not None
    execute(store, REPO, *claim)
    failed = store.get(monitor_id)
    assert failed is not None
    cycle = failed["cycles"][0]
    assert cycle["status"] == "failed"
    assert cycle["result"]["artifacts"][0]["path"] == "partial.json"
    assert "CONTROLLED interrupted" in cycle["result"]["failure"]

    async def paused(
        _snapshot: dict[str, Any],
        _repo: Path,
        _root: Path,
        *,
        fee_versions: tuple[FeeVersion, ...] = (),
    ) -> dict[str, Any]:
        store.control(monitor_id, "pause")
        return {"detail": "late", "capture": {"failures": []}, "outcome_failures": []}

    store.control(monitor_id, "pause")
    store.control(monitor_id, "resume")
    monkeypatch.setattr("entropytrade.tracking.worker.collect", paused)
    second = store.claim()
    assert second is not None
    execute(store, REPO, *second)
    result = store.get(monitor_id)
    assert result is not None
    assert result["cycles"][0]["status"] == "interrupted"
    assert result["cycles"][0]["result"] is None


def test_frozen_model_collection_books_replay_and_later_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from entropytrade.data.schema import MarketEvidence
    from tests.unit.test_tracking_models import inputs, saved_model

    spec, data, markets, model = inputs()
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = store.create(saved_model(store, spec, model))
    clock = SimulatedClock(data.samples[0].decision_time)
    market = next(iter(markets.values()))
    body = _market_body()
    body.update(
        ticker=market.ticker,
        event_ticker=market.event_ticker,
        open_time=market.open_time.isoformat(),
        close_time=market.close_time.isoformat(),
    )

    async def source(root: Path, **_kwargs: Any) -> Any:
        root.mkdir()
        (root / "raw.json").write_text(json.dumps({"markets": [body]}))
        evidence = MarketEvidence(
            market=market,
            capture_basis="receipt",
            raw_ref="raw.json",
            raw_hash=file_hash(root / "raw.json"),
        )
        (root / "markets.jsonl").write_text(evidence.model_dump_json())
        return data.revalidated(
            provenance={
                **data.provenance,
                "limitations": ["CONTROLLED sources and model; no empirical evidence"],
                "capture": {"failures": [], "universe_complete": True},
            }
        )

    def final(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "market": {
                    **body,
                    "status": "finalized",
                    "result": "yes",
                    "settlement_value_dollars": "1.0000",
                    "settlement_ts": (market.close_time + timedelta(minutes=1)).isoformat(),
                }
            },
        )

    real_collect = collect

    async def controlled(
        snapshot: dict[str, Any],
        repo: Path,
        root: Path,
        *,
        fee_versions: tuple[FeeVersion, ...] = (),
    ) -> dict[str, Any]:
        return await real_collect(
            snapshot,
            repo,
            root,
            clock=clock,
            fee_versions=fee_versions,
            execution_transport=httpx.MockTransport(execution_wire),
            outcome_transport=httpx.MockTransport(final),
        )

    monkeypatch.setattr("entropytrade.tracking.worker.capture_public", source)
    monkeypatch.setattr("entropytrade.tracking.worker.collect", controlled)
    first = store.claim()
    assert first is not None
    execute(store, REPO, *first)
    before = store.get(monitor_id, export=True)
    assert before is not None
    cycle = before["cycles"][0]
    assert cycle["status"] == "completed"
    decision = cycle["result"]["decisions"][0]
    assert decision["prediction"]["model_hash"] == model.model_hash
    assert decision["quote"]["asks"][0]["quantity"] == "4.00"
    assert decision["reasons"] == ["certified_fees", "missing_fee_evidence"]
    assert decision["intent"] is None
    assert verify(tmp_path / "shadow" / monitor_id / first[1])["verified"]
    frozen_bytes = (tmp_path / "shadow" / monitor_id / first[1] / "result.json").read_bytes()

    clock.advance_to(market.close_time + timedelta(hours=2))
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    reopened.control(monitor_id, "pause")
    reopened.control(monitor_id, "resume")
    second = reopened.claim()
    assert second is not None
    execute(reopened, REPO, *second)
    after = reopened.get(monitor_id, export=True)
    assert after is not None
    assert after["contracts"][0]["outcome"]["available_at"] == clock.now().isoformat()
    assert after["cycles"][1] == cycle
    assert (
        tmp_path / "shadow" / monitor_id / first[1] / "result.json"
    ).read_bytes() == frozen_bytes
    assert after["model_binding"] == before["model_binding"]
    assert not after["submission_enabled"]
    assert verify(tmp_path / "shadow" / monitor_id / second[1])["verified"]
