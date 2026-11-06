"""Explicitly CONTROLLED normalized receipts, never authentic historical/performance evidence."""

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from entropytrade.api.jobs import Jobs
from entropytrade.data.schema import MarketEvidence, Observation
from entropytrade.data.sources import file_hash
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.store import TrackingStore
from tests.exchange.test_gateway_http import _market_body
from tests.unit.test_public_families import weather

START = date(2025, 1, 1)
LABEL = "CONTROLLED cohort software fixture; simulated receipts/clocks, no empirical performance"


def body(day: date, series: str, city: str, *, settled: bool = False) -> dict[str, Any]:
    stamp = day.strftime("%y%b%d").upper()
    at = datetime.combine(day, datetime.min.time(), UTC)
    payload = _market_body()
    payload.update(
        ticker=f"{series}-{stamp}-T70",
        event_ticker=f"{series}-{stamp}",
        title=f"CONTROLLED highest temperature in {city}",
        open_time=(at - timedelta(days=1)).isoformat(),
        close_time=(at + timedelta(days=1, hours=6)).isoformat(),
        latest_expiration_time=(at + timedelta(days=1, hours=7)).isoformat(),
        floor_strike="70",
        rules_primary=f"If the highest temperature in {city} is greater "
        "than 70° Fahrenheit, according to The Weather Company at weather.com/kalshi, "
        "the market resolves to Yes.",
    )
    if settled:
        result = "yes" if high(day) > 70 else "no"
        payload.update(
            status="finalized",
            result=result,
            settlement_value_dollars="1.0000" if result == "yes" else "0.0000",
            settlement_ts=(at + timedelta(days=1, hours=7)).isoformat(),
        )
    return payload


def high(day: date) -> int:
    return 65 + (day - START).days % 13


def seed_cohort(workspace: Path, *, labels: bool = True) -> dict[str, Any]:
    if workspace.exists():
        raise ValueError("CONTROLLED cohort needs a fresh workspace")
    jobs = Jobs(workspace)
    TrackingStore(jobs)
    # Pinned to the two original locations so the CONTROLLED counts (200 events on 100
    # dates) do not move when the operational forward config adds locations.
    config = weather().revalidated(
        locations=tuple(p for p in weather().locations if p.series in {"KXHIGHPHIL", "KXHIGHCHI"})
    )
    for n in range(130):
        day = START + timedelta(days=n * 100 // 130)
        at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15, minutes=n % 2)
        job_id = jobs.create({"idea": LABEL, "family": "weather", "mode": "public"})
        root = workspace / "runs" / job_id / "public"
        (root / "raw").mkdir(parents=True)
        wire = []
        observations = []
        for location in config.locations:
            wire.append(body(day, location.series, location.name))
            begin = datetime.combine(day, datetime.min.time(), ZoneInfo(location.timezone))
            end = (begin + timedelta(days=1)).astimezone(UTC)
            valid = begin.astimezone(UTC)
            while valid < end:
                observations.append(
                    Observation(
                        source_id="open-meteo",
                        model="CONTROLLED-gfs",
                        entity_id=location.station,
                        variable="temperature_f",
                        valid_on=day,
                        valid_at=valid,
                        value=Decimal(high(day) - 1),
                        unit="degF",
                        revision_id=day.isoformat(),
                        available_at=at,
                        received_at=at,
                        timing_basis="received",
                        evidence=LABEL,
                        raw_ref="raw/controlled.json",
                        raw_hash="pending",
                    )
                )
                valid += timedelta(hours=1)
            if labels and day > START:
                previous = day - timedelta(days=1)
                wire.append(body(previous, location.series, location.name, settled=True))
                observations.append(
                    Observation(
                        source_id="weather-company",
                        model="CONTROLLED-scalar",
                        entity_id=location.station,
                        variable="settlement_high_f",
                        valid_on=previous,
                        value=Decimal(high(previous)),
                        unit="degF",
                        revision_id=previous.isoformat(),
                        available_at=at,
                        received_at=at,
                        timing_basis="received",
                        evidence=LABEL,
                        role="observation",
                        raw_ref="raw/controlled.json",
                        raw_hash="pending",
                    )
                )
        raw = root / "raw/controlled.json"
        raw.write_text(
            json.dumps(
                {
                    "evidence": LABEL,
                    "markets": wire,
                    "observations": [o.model_dump(mode="json") for o in observations],
                }
            )
        )
        digest = file_hash(raw)
        markets = [
            MarketEvidence(
                market=market_from_body(p, captured_at=at, series=p["ticker"].split("-")[0]),
                capture_basis="receipt",
                raw_ref="raw/controlled.json",
                raw_hash=digest,
            )
            for p in wire
        ]
        for name, items in (
            ("markets.jsonl", markets),
            ("observations.jsonl", [o.revalidated(raw_hash=digest) for o in observations]),
        ):
            (root / name).write_text("".join(o.model_dump_json() + "\n" for o in items))
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
            "weather_config": config.model_dump(mode="json"),
            "evidence": LABEL,
            "checksums": {
                p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob("*") if p.is_file()
            },
        }
        manifest["dataset_version"] = scientific_hash(manifest)
        (root / "manifest.json").write_text(json.dumps(manifest))
        jobs.update(job_id, "controlled", LABEL, status="completed", result={"evidence": LABEL})
    return {"evidence": LABEL, "catalog": jobs.weather_partitions()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    args.receipt.write_text(json.dumps(seed_cohort(args.workspace), indent=2))
