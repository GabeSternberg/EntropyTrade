"""CONTROLLED multi-date receipts/source transitions; never authentic history evidence."""

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from entropytrade.api.jobs import Jobs
from entropytrade.api.server import WorkbenchServer
from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.store import TrackingStore
from entropytrade.weather.history import build_snapshot
from entropytrade.weather.label_service import LabelService
from tests.integration.cohort_fixture import body
from tests.integration.weather_history_retained import REPO
from tests.unit.test_public_families import weather

LABEL = (
    "CONTROLLED forward-validation software evidence; simulated dates/source/clock; no performance"
)
NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)


def seed_dates(workspace: Path, count: int = 12) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("CONTROLLED setup requires fresh workspace")
    jobs = Jobs(workspace)
    TrackingStore(jobs)
    config = weather().revalidated(locations=weather().locations[:1])
    captures = []
    for n in range(count):
        day = date(2026, 10, 1) + timedelta(days=n)
        at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15)
        payload = body(day, "KXHIGHPHIL", "Philadelphia")
        payload["rules_primary"] = (
            "If the maximum temperature in Philadelphia (CLIPHL) is greater than 70 degrees "
            "Fahrenheit, according to The Weather Company at weather.com/kalshi, "
            "the market resolves to Yes."
        )
        job = jobs.create({"idea": LABEL, "family": "weather", "mode": "public"})
        root = workspace / "runs" / job / "public"
        (root / "raw").mkdir(parents=True)
        raw = root / "raw/controlled.json"
        raw.write_text(json.dumps({"evidence": LABEL, "markets": [payload]}))
        digest = file_hash(raw)
        market = MarketEvidence(
            market=market_from_body(payload, captured_at=at, series="KXHIGHPHIL"),
            capture_basis="receipt",
            raw_ref="raw/controlled.json",
            raw_hash=digest,
        )
        (root / "markets.jsonl").write_text(market.model_dump_json() + "\n")
        (root / "observations.jsonl").write_text("")
        capture = {
            "family": "weather",
            "started_at": at.isoformat(),
            "decision_time": at.isoformat(),
            "failures": [],
            "universe_complete": True,
            "history_complete": False,
            "receipts": [
                {
                    "received_at": at.isoformat(),
                    "status": 200,
                    "raw_ref": "raw/controlled.json",
                    "hash": digest,
                }
            ],
            "evidence": LABEL,
        }
        (root / "capture.json").write_text(json.dumps(capture))
        manifest = {
            "family": "weather",
            "decision_time": at.isoformat(),
            "evidence": LABEL,
            "weather_config": config.model_dump(mode="json"),
            "checksums": {
                p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob("*") if p.is_file()
            },
        }
        manifest["dataset_version"] = scientific_hash(manifest)
        (root / "manifest.json").write_text(json.dumps(manifest))
        jobs.update(job, "controlled", LABEL, status="completed", result={"evidence": LABEL})
        captures.append(root)
    return build_snapshot(workspace / "runs/weather-datasets", captures)


def portal(day: str, phase: str = "official") -> dict[str, Any]:
    official = phase in {"official", "revised"}
    return {
        "date": day,
        "evidence": LABEL,
        "results": [
            {
                "station": {
                    "cliId": "PHL",
                    "icao": "KPHL",
                    "timezone": "America/New_York",
                    "isDomestic": True,
                },
                "status": "revised"
                if phase == "revised"
                else "official"
                if official
                else "preliminary",
                "data": {
                    "stationId": "PHL",
                    "reportDate": day,
                    "maxTemp": 72 if phase == "revised" else 70,
                    "isOfficial": official,
                },
            }
        ],
    }


def serve(workspace: Path, phase_file: Path, port: int) -> None:
    original = LabelService.acquire

    def state() -> dict[str, str]:
        return dict(json.loads(phase_file.read_text()))

    def now() -> datetime:
        return datetime.fromisoformat(state()["now"])

    async def controlled(
        self: LabelService,
        request: dict[str, Any],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        async def source(req: httpx.Request) -> httpx.Response:
            phase = state()["phase"]
            if phase == "stall":
                await asyncio.Event().wait()
            if phase == "outage":
                return httpx.Response(503, text=LABEL + " source outage")
            return httpx.Response(200, json=portal(req.url.params["date"], phase))

        await original(self, request, httpx.MockTransport(source))

    with (
        patch.object(LabelService, "acquire", controlled),
        patch("entropytrade.weather.label_schedule.utc_now", now),
        patch("entropytrade.weather.label_service.utc_now", now),
    ):
        server = WorkbenchServer(REPO, workspace, port=port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--phase", type=Path)
    parser.add_argument("--port", type=int, default=43151)
    args = parser.parse_args()
    if args.phase:
        serve(args.workspace, args.phase, args.port)
    else:
        seed_dates(args.workspace)
