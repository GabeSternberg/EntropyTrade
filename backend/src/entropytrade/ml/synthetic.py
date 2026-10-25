"""Controlled synthetic proof. No generated number is empirical Kalshi performance."""

import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.dataset import make_rows
from entropytrade.data.schema import DatasetConfig, Location, MarketEvidence, Observation
from entropytrade.domain.enums import MarketResult, MarketStatus, MarketType, StrikeType
from entropytrade.domain.market import (
    Market,
    MarketRules,
    PriceRange,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.features.registry import scientific_hash


def synthetic_dataset(root: Path, *, days: int = 300, seed: int = 17) -> Path:
    if not 100 <= days <= 365:
        raise ValueError("synthetic proof uses 100-365 independent date blocks")
    root.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)  # noqa: S311 - deterministic synthetic experiment
    locations = (
        Location(
            name="SYNTHETIC Philadelphia",
            series="SYNTHPHL",
            station="SYNTH-PHL",
            timezone="America/New_York",
        ),
        Location(
            name="SYNTHETIC Chicago",
            series="SYNTHCHI",
            station="SYNTH-CHI",
            timezone="America/Chicago",
        ),
    )
    start = date(2025, 1, 1)
    config = DatasetConfig(
        locations=locations,
        start=start,
        end=start + timedelta(days=days - 1),
        sources=("synthetic-gfs", "synthetic-nws", "weather-company"),
    )
    markets: list[MarketEvidence] = []
    observations: list[Observation] = []
    for index in range(days):
        day = start + timedelta(days=index)
        decision = datetime(day.year, day.month, day.day, 15, tzinfo=UTC)
        for city_index, location in enumerate(locations):
            seasonal = 65 + 18 * math.sin(2 * math.pi * index / 365.25)
            weather = seasonal + rng.gauss(0, 6)
            target = round(weather + rng.gauss(0, 2))
            for provider in ("synthetic-gfs", "synthetic-nws"):
                latest = weather + (2 if city_index == 0 else -1) + rng.gauss(0, 2)
                for revision, value, hours in (
                    ("old", latest + rng.gauss(0, 2), 30),
                    ("new", latest, 6),
                ):
                    available = decision - timedelta(hours=hours)
                    observations.append(
                        Observation(
                            source_id=provider,
                            model=provider,
                            entity_id=location.station,
                            variable="daily_high_f",
                            value=Decimal(str(value)),
                            unit="degF",
                            valid_on=day,
                            issued_at=available - timedelta(minutes=30),
                            available_at=available,
                            received_at=available,
                            timing_basis="received",
                            revision_id=revision + str(index),
                            evidence="SYNTHETIC controlled receipt",
                            raw_ref="synthetic:seed:" + str(seed),
                            raw_hash=scientific_hash(
                                [provider, index, city_index, revision, value]
                            ),
                        )
                    )
            label_at = decision + timedelta(hours=19)
            observations.append(
                Observation(
                    source_id="weather-company",
                    entity_id=location.station,
                    variable="settlement_high_f",
                    value=Decimal(target),
                    unit="degF",
                    valid_on=day,
                    role="observation",
                    available_at=label_at,
                    received_at=label_at,
                    timing_basis="received",
                    evidence="SYNTHETIC outcome, not an actual provider observation",
                    raw_ref="synthetic:truth",
                    raw_hash=scientific_hash([index, city_index, target]),
                )
            )
            event = location.series + "-" + day.strftime("%y%b%d").upper()
            strikes = (
                Strike(strike_type=StrikeType.LESS, cap=Decimal(50)),
                Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(50), cap=Decimal(69)),
                Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(70), cap=Decimal(89)),
                Strike(strike_type=StrikeType.GREATER, floor=Decimal(89)),
            )
            for j, strike in enumerate(strikes):
                ticker = event + "-SYNTH" + str(j)
                rules = MarketRules(
                    market_ticker=ticker,
                    rules_primary=(
                        "SYNTHETIC integer Fahrenheit high according to The Weather Company."
                    ),
                    settlement_basis="contract_text",
                    settlement_sources=(SettlementSource(name="The Weather Company"),),
                    captured_at=decision - timedelta(hours=24),
                )
                market = Market(
                    ticker=ticker,
                    event_ticker=event,
                    series_ticker=location.series,
                    market_type=MarketType.BINARY,
                    title="SYNTHETIC probability fixture",
                    status=MarketStatus.ACTIVE,
                    open_time=decision - timedelta(hours=24),
                    close_time=decision + timedelta(hours=14),
                    strike=strike,
                    rules=rules,
                    tick_schedule=TickSchedule(
                        ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal("0.01")),)
                    ),
                )
                for final in (False, True):
                    sample = (
                        market
                        if not final
                        else market.revalidated(
                            status=MarketStatus.FINALIZED,
                            result=MarketResult.YES
                            if strike.resolves_yes(Decimal(target))
                            else MarketResult.NO,
                            rules=rules.revalidated(captured_at=label_at),
                        )
                    )
                    markets.append(
                        MarketEvidence(
                            market=sample,
                            created_at=market.open_time,
                            capture_basis="receipt",
                            raw_ref="synthetic:market",
                            raw_hash=scientific_hash(sample.model_dump(mode="json")),
                        )
                    )
    version = scientific_hash({"synthetic_seed": seed, "days": days, "generator": "v1"})
    rows, _ = make_rows(config, markets, observations, [], version)
    pq.write_table(pa.Table.from_pylist(rows), root / "rows.parquet", compression="zstd")
    pq.write_table(
        pa.Table.from_pylist([{"payload_json": o.model_dump_json()} for o in observations]),
        root / "observations.parquet",
        compression="zstd",
    )
    manifest: dict[str, Any] = {
        "dataset_version": version,
        "data_kind": "synthetic",
        "seed": seed,
        "days": days,
        "config": config.model_dump(mode="json"),
        "description": "Controlled synthetic pipeline proof; not empirical Kalshi data.",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return root
