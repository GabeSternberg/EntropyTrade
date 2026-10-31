"""CONTROLLED sustained collection; simulated clocks/data are never empirical history."""

import argparse
import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from entropytrade.api.jobs import Jobs
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import collect
from tests.exchange.test_gateway_http import _market_body
from tests.shadow_support import execution_wire
from tests.unit.test_public_families import WHEN, weather
from tests.unit.test_tracking import REPO, monitor


def seed_sustained(workspace: Path, count: int = 130) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("CONTROLLED acceptance requires a fresh workspace")
    store = TrackingStore(Jobs(workspace))
    monitor_id = monitor(store)
    clock = SimulatedClock(WHEN)
    body = _market_body()
    body.update(
        ticker="KXHIGHPHIL-26OCT25-T89",
        event_ticker="KXHIGHPHIL-26OCT25",
        open_time="2026-10-24T00:00:00Z",
        close_time="2026-10-26T04:00:00Z",
        latest_expiration_time="2026-10-26T05:00:00Z",
    )

    settled_body = dict(body)

    def markets(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"markets": [body], "cursor": ""})

    def source(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "latitude": 39.87,
                "longitude": -75.23,
                "hourly_units": {"temperature_2m": "°F"},
                "hourly": {
                    "time": [
                        (WHEN.replace(hour=0) + timedelta(hours=h)).isoformat() for h in range(120)
                    ],
                    "temperature_2m": [70] * 120,
                },
            },
        )

    def outcome(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "market": {
                    **settled_body,
                    "status": "finalized",
                    "result": "yes",
                    "settlement_value_dollars": "1.0000",
                    "settlement_ts": "2026-10-26T04:01:00Z",
                }
            },
        )

    config = weather().revalidated(locations=weather().locations[:1], providers=("open-meteo",))
    with (
        patch(
            "entropytrade.tracking.worker.WeatherConfig.model_validate_json", return_value=config
        ),
        patch("entropytrade.weather.collection.utc_now", clock.now),
        patch("entropytrade.storage.forecast_archive.utc_now", clock.now),
    ):
        for n in range(count):
            # The later page has different target dates AND a later controlled label.
            if n == count - 2:
                clock.advance_to(WHEN + timedelta(days=2))
                body.update(
                    ticker="KXHIGHPHIL-26OCT27-T89",
                    event_ticker="KXHIGHPHIL-26OCT27",
                    open_time="2026-10-26T00:00:00Z",
                    close_time="2026-10-28T04:00:00Z",
                    latest_expiration_time="2026-10-28T05:00:00Z",
                )
            store.control(monitor_id, "pause")
            store.control(monitor_id, "resume")
            claim = store.claim()
            assert claim is not None
            root = workspace / "shadow" / monitor_id / claim[1]
            root.mkdir(parents=True)
            current = store.get(monitor_id, export=True)
            assert current is not None
            result = asyncio.run(
                collect(
                    current,
                    REPO,
                    root,
                    clock=clock,
                    kalshi_transport=httpx.MockTransport(markets),
                    source_transport=httpx.MockTransport(source),
                    execution_transport=httpx.MockTransport(execution_wire),
                    outcome_transport=httpx.MockTransport(outcome),
                )
            )
            result["artifacts"] = [
                {
                    "path": p.relative_to(root).as_posix(),
                    "sha256": file_hash(p),
                    "bytes": p.stat().st_size,
                }
                for p in sorted(root.rglob("*"))
                if p.is_file()
            ]
            (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
            assert store.finish(monitor_id, claim[1], result)
            clock.advance(timedelta(minutes=1))
            if n == 63:
                store = TrackingStore(Jobs(workspace))
                store.recover()
    store.control(monitor_id, "pause")
    return {
        "evidence": "CONTROLLED collection, simulated clocks and source payloads; "
        "no empirical performance",
        "monitor_id": monitor_id,
        "cycles": count,
        "restart_after_cycle": 64,
        "catalog": store.jobs.weather_partitions(),
    }


def seed_authentic(workspace: Path) -> dict[str, Any]:
    """Import original whole cycles. Only destination IDs/DB bookkeeping are new."""
    import shutil

    from tests.integration.weather_history_retained import SOURCE

    if workspace.exists():
        raise ValueError("authentic acceptance requires a fresh workspace")
    store = TrackingStore(Jobs(workspace))
    monitor_id = monitor(store)
    for source_root in sorted(SOURCE.glob("*/*")):
        store.control(monitor_id, "pause")
        store.control(monitor_id, "resume")
        claim = store.claim()
        assert claim is not None
        root = workspace / "shadow" / monitor_id / claim[1]
        shutil.copytree(source_root, root)
        result = json.loads((root / "result.json").read_text())
        assert store.finish(monitor_id, claim[1], result)
    store.control(monitor_id, "pause")
    return {
        "evidence": "Authentic original shadow receipts; no new acquisition or performance",
        "monitor_id": monitor_id,
        "cycles": 2,
        "catalog": store.jobs.weather_partitions(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--authentic", action="store_true")
    args = parser.parse_args()
    args.receipt.write_text(
        json.dumps(
            (seed_authentic if args.authentic else seed_sustained)(args.workspace),
            sort_keys=True,
            indent=2,
        )
    )
