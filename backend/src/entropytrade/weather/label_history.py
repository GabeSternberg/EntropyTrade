"""Bind acquired scalar labels back to the selected immutable contract evidence."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from entropytrade.data.schema import MarketEvidence, Observation
from entropytrade.weather.collection import WeatherConfig
from entropytrade.weather.labels import compatible_rules, load_batch


def retained_labels(
    paths: Sequence[Path],
    markets: Sequence[MarketEvidence],
    config: WeatherConfig,
    protected: frozenset[str],
) -> tuple[list[Observation], list[dict[str, Any]], dict[str, Path], dict[str, bytes]]:
    observations: list[Observation] = []
    audit, copies, bodies = [], {}, {}
    locations = {p.series: p for p in config.locations}
    protected_pairs = {
        (locations[m.market.series_ticker].station, m.market.rules.settlement_target_date)
        for m in markets
        if m.market.event_ticker in protected and m.market.series_ticker in locations
    }
    retained_bytes = 0
    for path in sorted(paths, key=lambda p: p.stem):
        batch = load_batch(path)
        relevant = {m.market.event_ticker for m in markets} & {t.event_id for t in batch.targets}
        if not relevant:
            continue
        retained_bytes += path.stat().st_size
        if retained_bytes > 256 * 1024 * 1024:
            raise ValueError("retained weather label inputs exceed 256 MB budget")
        prefix = "scalar-labels/" + batch.version.removeprefix("sha256:")
        copies[prefix + ".json"] = path
        summary = batch.summary()
        records = []
        for record in summary["records"]:
            target = record["target"]
            if target["event_id"] not in relevant:
                continue
            originals = [m.market for m in markets if m.market.event_ticker == target["event_id"]]
            matching = all(
                m.series_ticker in locations
                and locations[m.series_ticker].station == target["station"]
                and locations[m.series_ticker].timezone == target["timezone"]
                and m.rules.settlement_target_date is not None
                and m.rules.settlement_target_date.isoformat() == target["target_date"]
                and compatible_rules(
                    m.rules.model_dump(mode="json"),
                    m.ticker,
                    target["station"],
                    target["target_date"],
                )
                for m in originals
            ) and {m.rules.rules_hash for m in originals} == set(target["rules_hashes"])
            if not matching:
                record = {
                    **record,
                    "observation": None,
                    "refusal": "acquired label rules/station/date differ from selected contracts",
                }
            if target["event_id"] in protected or any(
                (target["station"], m.rules.settlement_target_date) in protected_pairs
                for m in originals
            ):
                record = {
                    **record,
                    "observation": None,
                    "refusal": "protected label excluded from research",
                }
            if record["observation"] is not None:
                item = Observation.model_validate(record["observation"])
                receipt = next(r for r in batch.receipts if r.digest == item.raw_hash)
                relative = "scalar-labels/raw/" + receipt.digest.removeprefix("sha256:") + ".json"
                bodies[relative] = receipt.body()
                item = item.revalidated(raw_ref=relative)
                observations.append(item)
                record = {**record, "observation": item.model_dump(mode="json")}
            records.append(record)
        audit.append(
            {
                **summary,
                "records": records,
                "verified_events": sum(r["observation"] is not None for r in records),
                "refused_events": sum(r["observation"] is None for r in records),
            }
        )
    return observations, audit, copies, bodies
