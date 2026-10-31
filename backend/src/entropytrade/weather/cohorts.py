"""Bounded, restartable cohort assembly through the retained snapshot/feature pipeline."""

import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.tracking.history import PARTITION_SIZE, anchor, catalog, selected_inputs
from entropytrade.weather.history import MAX_BYTES, _build_snapshot, build_snapshot, load_snapshot

if TYPE_CHECKING:
    from entropytrade.api.jobs import Jobs

MAX_PARTITIONS = 8


def partition_ids(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= MAX_PARTITIONS
        or any(not isinstance(v, str) for v in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("select one to eight distinct partition IDs")
    from entropytrade.weather.history import snapshot_id

    return [snapshot_id(v) for v in value]


def build_cohort(jobs: "Jobs", history_ids: object, outcome_ids: object = None) -> dict[str, Any]:
    """Publish only complete cohorts; completed immutable batches survive an interrupted retry.

    Batch outputs are evidence caches, never concatenated engineered features. Rebuilding
    features jointly is necessary for causal history/bias joins across batch boundaries.
    The aggregate retains the existing 256 MB raw-input cap and fixed model gates.
    """
    history = partition_ids(history_ids)
    outcomes = history if outcome_ids is None else partition_ids(outcome_ids)
    available = catalog(jobs)["partitions"]
    order = {p["partition_id"]: p["number"] for p in available}
    if not set(history + outcomes) <= order.keys():
        raise ValueError("history partition changed or is unknown; refresh the catalog")
    history.sort(key=order.__getitem__)
    outcomes.sort(key=order.__getitem__)
    output = jobs.root / "runs/weather-datasets"
    batch_output = output / ".batches"
    frozen = anchor(jobs)
    protected: frozenset[str] = frozenset()
    # Union ALL source/model/prior-snapshot protections before constructing any batch.
    for parent in (output, batch_output):
        for path in sorted(parent.glob("[0-9a-f]" * 64)):
            protected |= frozenset(load_snapshot(path)["identity"]["protected_events"])
    captures: dict[str, list[Path]] = {}
    labels: list[Path] = []
    for identifier in dict.fromkeys(history + outcomes):
        selected, later, inherited = selected_inputs(jobs, identifier, identifier)
        protected |= inherited
        if identifier in history:
            captures[identifier] = selected
        if identifier in outcomes:
            labels.extend(later)
    holdout = frozen + timedelta(days=90)
    for paths in captures.values():
        for path in paths:
            for line in (path / "markets.jsonl").read_text().splitlines():
                market = MarketEvidence.model_validate_json(line).market
                if (
                    market.rules.settlement_target_date
                    and market.rules.settlement_target_date >= holdout
                ):
                    protected |= frozenset({market.event_ticker})
    # Preflight prevents building batches for an over-budget cohort. Final assembly also
    # checks the copied inventory, including complete shadow replay artifacts.
    roots = {p for batch in captures.values() for p in batch} | set(labels)
    if sum(p.stat().st_size for root in roots for p in root.rglob("*") if p.is_file()) > MAX_BYTES:
        raise ValueError("retained weather inputs exceed 256 MB budget")
    batches = []
    frozen_captures = []
    for identifier in history:
        batch = build_snapshot(
            batch_output,
            captures[identifier],
            protected_events=protected,
            frozen_anchor=frozen,
            selection={"partition_id": identifier},
        )
        batches.append({"partition_id": identifier, "dataset_id": batch["dataset_id"]})
        root = batch_output / batch["dataset_id"].removeprefix("sha256:")
        shadow_versions = set()
        for digest in batch["identity"]["shadow_cycles"]:
            cycle = root / "shadow" / digest
            shadow_versions.add(
                json.loads((cycle / "decision-inputs.json").read_text())["data"]["dataset_version"]
            )
            frozen_captures.append(cycle / "public")
        frozen_captures.extend(
            root / f"receipts/{index:04d}"
            for index, version in enumerate(batch["identity"]["captures"])
            if version not in shadow_versions
        )
    # Recheck membership after building: a growing partial partition must be refreshed,
    # never silently combined with the membership from an earlier catalog.
    current = {p["partition_id"] for p in catalog(jobs)["partitions"]}
    if not set(history + outcomes) <= current:
        raise ValueError("history partition changed during cohort build; refresh the catalog")
    selection = {
        "partition_ids": history,
        "outcome_partition_ids": outcomes,
        "cohort": {
            "schema": "retained-weather-cohort-v1",
            "batches": batches,
            "partition_size": PARTITION_SIZE,
            "max_partitions": MAX_PARTITIONS,
            "implementation": file_hash(Path(__file__)),
        },
    }
    from entropytrade.weather.label_service import batches as label_batches

    return _build_snapshot(
        output,
        frozen_captures,
        outcome_roots=labels,
        scalar_batches=label_batches(jobs.root),
        protected_events=protected,
        frozen_anchor=frozen,
        selection=selection,
    )
