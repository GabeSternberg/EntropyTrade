"""Controlled full collector/account transaction and offline workspace recovery."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.tracking.accounting import verify_export
from entropytrade.tracking.replay import verify
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import collect
from tests.exchange.test_gateway_http import _market_body
from tests.fee_support import controlled_fee
from tests.integration.paper_fixture import seed
from tests.paper_support import paper_inputs
from tests.shadow_support import execution_wire
from tests.unit.test_tracking import REPO


def test_collection_with_later_public_books_persists_fills_and_official_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = paper_inputs()
    data = ExperimentData.model_validate(inputs["decision_inputs"]["data"])
    bundle = PredictionBundle.model_validate(inputs["decision_inputs"]["bundle"])
    sample = data.samples[0]
    clock = SimulatedClock(sample.decision_time)
    body = {
        **_market_body(),
        "ticker": sample.ticker,
        "event_ticker": sample.event_id,
        "series_ticker": sample.family,
        "open_time": (sample.decision_time - timedelta(days=1)).isoformat(),
        "close_time": sample.close_time.isoformat(),
    }
    market = market_from_body(body, series=sample.family, captured_at=sample.decision_time)

    async def source(root: Path, **_kwargs: Any) -> ExperimentData:
        root.mkdir()
        (root / "raw.json").write_text(json.dumps({"markets": [body]}))
        (root / "markets.jsonl").write_text(
            MarketEvidence(
                market=market,
                capture_basis="receipt",
                raw_ref="raw.json",
                raw_hash=file_hash(root / "raw.json"),
            ).model_dump_json()
        )
        return data.revalidated(
            provenance={
                "capture": {"failures": [], "universe_complete": True},
                "limitations": ["CONTROLLED SYNTHETIC public source fixture"],
            }
        )

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert not any("kalshi-access" in h or "authorization" in h for h in request.headers)
        if request.url.path.endswith("/orderbook"):
            return httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [[".40", "10.00"]],
                        "no_dollars": [[".50", "10.00"]],
                    }
                },
            )
        return execution_wire(request)

    def final(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={
                "market": {
                    **body,
                    "status": "finalized",
                    "result": "yes",
                    "settlement_value_dollars": "1.0000",
                    "settlement_ts": (sample.close_time + timedelta(seconds=1)).isoformat(),
                }
            },
        )

    async def latency(_seconds: float) -> None:
        clock.advance(timedelta(seconds=1))

    def controlled_score(_spec: object, current: ExperimentData, *_args: Any) -> PredictionBundle:
        return bundle.revalidated(
            records=tuple(
                bundle.records[0].revalidated(
                    decision_time=s.decision_time, feature_hash=s.feature_hash
                )
                for s in current.samples
            )
        )

    monkeypatch.setattr("entropytrade.tracking.worker.capture_public", source)
    monkeypatch.setattr("entropytrade.tracking.worker.score", controlled_score)
    monkeypatch.setattr("entropytrade.tracking.worker.asyncio.sleep", latency)
    store = TrackingStore(Jobs(tmp_path))
    job = store.jobs.create(
        {
            "idea": "CONTROLLED synthetic collector accounting",
            "family": "weather",
            "mode": "recorded",
        }
    )
    store.jobs.update(
        job,
        "completed",
        "CONTROLLED",
        status="completed",
        result={
            "data_kind": "real",
            "proposals": [{"candidate_id": "c0", "spec": inputs["decision_inputs"]["spec"]}],
        },
    )
    mid = store.create({"job_id": job, "candidate_id": "c0", "interval_seconds": 60})
    for index in range(2):
        if index:
            clock.advance_to(sample.close_time + timedelta(hours=2))
            store = TrackingStore(Jobs(tmp_path))
            store.recover()
            store.control(mid, "pause")
            store.control(mid, "resume")
        claim = store.claim()
        assert claim
        current = store.get(mid, export=True)
        assert current
        root = tmp_path / "shadow" / mid / claim[1]
        root.mkdir(parents=True)
        result = asyncio.run(
            collect(
                current,
                REPO,
                root,
                clock=clock,
                execution_transport=httpx.MockTransport(wire),
                outcome_transport=httpx.MockTransport(final),
                fee_versions=(controlled_fee(),),
            )
        )
        assert not result["execution"]["failures"]
        result["artifacts"] = [
            {
                "path": p.relative_to(root).as_posix(),
                "sha256": file_hash(p),
                "bytes": p.stat().st_size,
            }
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]
        (root / "result.json").write_text(json.dumps(result, sort_keys=True))
        assert store.finish(mid, claim[1], result)
        assert verify(root)["verified"]
        if not index:
            assert result["paper"]["summary"]["fill_count"] == 1
            assert result["paper_execution"]["book_count"] == 1
    value = store.get(mid, export=True)
    assert value
    assert value["paper_summary"]["settlement_count"] == 1
    assert value["paper_summary"]["data_kind"] == "synthetic"
    assert verify_export(value)["paper_cycles"] == 2


def test_portable_account_snapshot_restore_and_legacy_upgrade(tmp_path: Path) -> None:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED application identity")
    workspace = tmp_path / "data/cache/original"
    receipt = seed(workspace, authentic=False)
    store = TrackingStore(Jobs(workspace))
    original = store.get(receipt["monitor_id"], export=True)
    archive = tmp_path / "data/account.zip"
    snapshot(tmp_path, workspace, archive)
    destination = tmp_path / "data/cache/restored"
    restore(tmp_path, archive, destination)
    reopened = TrackingStore(Jobs(destination))
    assert reopened.get(receipt["monitor_id"], export=True) == original
    assert original
    assert verify_export(original)["paper_cycles"] == 5
    # Legacy workspaces without the table are accepted only if they contain no paper chain.
    legacy = TrackingStore(Jobs(tmp_path / "data/cache/legacy"))
    with legacy.jobs.connect() as db:
        db.execute("DROP TABLE shadow_accounts")
    old_archive = tmp_path / "data/legacy.zip"
    snapshot(tmp_path, legacy.jobs.root, old_archive)
    old_destination = tmp_path / "data/cache/legacy-restored"
    restore(tmp_path, old_archive, old_destination)
    upgraded = TrackingStore(Jobs(old_destination))
    assert upgraded.history() == []
