"""Authentic receipt replay and separately labelled controlled temporal mutations."""

import json
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from entropytrade.agents.evidence import EvidenceConfig, ResearchEvidence
from entropytrade.api.jobs import validate_request
from entropytrade.data.schema import Observation
from entropytrade.data.sources import file_hash
from entropytrade.experiments.data import WeatherPredictions, weather_data
from entropytrade.experiments.synthetic import prepare_synthetic
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import temporal_plan
from entropytrade.ml.experiment import ModelingConfig, run_modeling
from entropytrade.weather.history import _observations, build_snapshot, load_snapshot
from tests.integration.weather_history_retained import SOURCE
from tests.r2_support import observation


@pytest.fixture
def captures() -> list[Path]:
    found = sorted(SOURCE.glob("*/*/public"))
    assert len(found) == 2
    return found


def feature_rows(root: Path, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return list(pq.read_table(root / snapshot["features"] / "features.parquet").to_pylist())


def test_authentic_snapshot_replay_deduplicates_and_preserves_clocks(
    tmp_path: Path, captures: list[Path]
) -> None:
    first = build_snapshot(tmp_path / "first", captures)
    again = build_snapshot(tmp_path / "second", list(reversed(captures)) + captures)
    assert first == again
    assert first == build_snapshot(tmp_path / "first", captures)
    assert first["readiness"]["independent_events"] == 4
    assert first["readiness"]["date_blocks"] == 2
    assert first["readiness"]["eligible_events"] == 4
    assert first["readiness"]["scalar_label_events"] == 0
    assert first["readiness"]["status"] == "insufficient_data"
    root = tmp_path / "first" / first["dataset_id"].removeprefix("sha256:")
    decisions = {json.loads((p / "manifest.json").read_text())["decision_time"] for p in captures}
    rows = feature_rows(root, first)
    assert {row["decision_time"] for row in rows} == decisions
    assert len(rows) == len({(r["market_ticker"], r["decision_time"]) for r in rows})
    assert all(r["rules_known_at_decision"] and r["outcome"] is None for r in rows)
    assert all(r["temperature_target_f"] is None for r in rows)
    source = [
        Observation.model_validate_json(line)
        for original in captures
        for line in (original / "observations.jsonl").read_text().splitlines()
    ]
    retained = [
        Observation.model_validate_json(r["payload_json"])
        for r in pq.read_table(root / "dataset/observations.parquet").to_pylist()
    ]
    assert {o.available_at for o in retained} <= {o.available_at for o in source}
    assert len(retained) == len(_observations(source))
    for item in retained:
        matches = [
            o
            for o in source
            if o.revision_id == item.revision_id
            and o.entity_id == item.entity_id
            and o.valid_at == item.valid_at
        ]
        assert item.available_at == min(o.available_at for o in matches if o.available_at)
    (root / first["features"] / "features.parquet").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(root)


def test_frozen_partition_and_source_holdout_survive_added_receipts(
    tmp_path: Path, captures: list[Path]
) -> None:
    original = build_snapshot(tmp_path / "datasets", captures[:1])
    event = json.loads((captures[0] / "markets.jsonl").read_text().splitlines()[0])["market"][
        "event_ticker"
    ]
    expanded = build_snapshot(tmp_path / "datasets", captures, protected_events=frozenset({event}))
    assert (
        original["identity"]["temporal_boundaries"] == expanded["identity"]["temporal_boundaries"]
    )
    root = tmp_path / "datasets" / expanded["dataset_id"].removeprefix("sha256:")
    data = weather_data(root / expanded["features"])
    assert event in data.protected_events
    evidence = ResearchEvidence(
        EvidenceConfig(
            root=root,
            features=expanded["features"],
            holdout_start=date.fromisoformat(expanded["identity"]["temporal_boundaries"][2]),
        )
    )
    assert all(row["event_id"] != event for row in evidence.markets)
    final = build_snapshot(tmp_path / "datasets", captures)
    assert final == expanded  # Protection cannot be forgotten by the next snapshot.
    assert (
        load_snapshot(tmp_path / "datasets" / original["dataset_id"].removeprefix("sha256:"))
        == original
    )


def test_duplicate_vintages_revisions_and_delayed_receipts_are_not_retimed() -> None:
    at = datetime(2026, 10, 29, 10, tzinfo=UTC)
    old = observation(at.date(), 70, at)
    repeat = old.revalidated(
        raw_ref="other/path",
        raw_hash="another-body",
        received_at=at + timedelta(hours=1),
        available_at=at + timedelta(hours=1),
    )
    revised = observation(at.date(), 72, at + timedelta(hours=2), revision="revised")
    result = _observations([repeat, revised, old, old])
    assert len(result) == 2
    assert next(o for o in result if o.value == 70).available_at == at
    assert next(o for o in result if o.value == 72).available_at == at + timedelta(hours=2)
    assert not revised.known_at(at)
    with pytest.raises(ValueError, match="conflicting"):
        _observations([old, old.revalidated(value=old.value + 1)])


def test_partial_staging_recovers_without_overwriting_snapshot(
    tmp_path: Path, captures: list[Path]
) -> None:
    snapshot = build_snapshot(tmp_path / "reference", captures)
    root = tmp_path / "datasets"
    stage = root / (".building-" + snapshot["dataset_id"].removeprefix("sha256:"))
    stage.mkdir(parents=True)
    (stage / "partial").write_text("interrupted build")
    recovered = build_snapshot(root, captures)
    assert recovered == snapshot
    assert not stage.exists()


def test_refuse_empty_corrupt_cross_family_and_unsafe_inputs(
    tmp_path: Path, captures: list[Path]
) -> None:
    with pytest.raises(ValueError, match="No retained"):
        build_snapshot(tmp_path / "empty", [])
    source = tmp_path / "input"
    shutil.copytree(captures[0], source)
    (source / "markets.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="checksum"):
        build_snapshot(tmp_path / "corrupt", [source])
    for value in ("../bad", str(tmp_path), "sha256:" + "a" * 64, None):
        with pytest.raises(ValueError, match="dataset ID"):
            validate_request(
                {
                    "idea": "forecast",
                    "family": "weather",
                    "mode": "weather_history",
                    "dataset_id": value,
                }
            )
    with pytest.raises(ValueError, match="dataset selection"):
        validate_request(
            {"idea": "forecast", "family": "weather", "mode": "public", "dataset_id": "a" * 64}
        )


def test_fixed_calendar_modeling_uses_original_gates_and_never_holdout(tmp_path: Path) -> None:
    # Explicitly SYNTHETIC positive fitting proof, not empirical weather evidence.
    features = prepare_synthetic(tmp_path / "synthetic", days=120)
    rows = pq.read_table(features / "features.parquet").to_pylist()
    start = date(2025, 1, 1)
    cuts = tuple(start + timedelta(days=d) for d in (48, 60, 90))
    fixed = (cuts[0], cuts[1], cuts[2])
    plan = temporal_plan(rows, fixed)
    assert len(plan.fit) == 96
    assert len(plan.calibration) == 24
    assert len(plan.validation) == 60
    result = run_modeling(
        features=features,
        output=tmp_path / "models",
        registry_path=tmp_path / "registry.sqlite",
        tracking=tmp_path / "mlflow",
        config=ModelingConfig(boundaries=fixed, walk_forward=False),
        data_kind="synthetic",
    )
    assert result["models"]
    assert result["train_eligible_events"] >= 60
    assert result["calibration_eligible_events"] >= 20
    assert not result["holdout_evaluated"]
    directory = tmp_path / "models" / result["run_id"].removeprefix("sha256:")
    predictions = [
        json.loads(line) for line in (directory / "predictions.jsonl").read_text().splitlines()
    ]
    assert predictions
    assert {p["event_id"] for p in predictions} <= set(plan.validation)
    assert not {p["event_id"] for p in predictions} & set(plan.holdout)
    assert all(p["fit_asof"] == plan.fit_asof.isoformat() for p in predictions)
    # Protecting a former training event must refuse rather than silently retrain on it.
    manifest = json.loads((features / "manifest.json").read_text())
    manifest["temporal_boundaries"] = [d.isoformat() for d in fixed]
    manifest["feature_version"] = scientific_hash(
        {k: v for k, v in manifest.items() if k != "feature_version"}
    )
    (features / "manifest.json").write_text(json.dumps(manifest))
    predictor = WeatherPredictions(
        features,
        tmp_path / "protected-models",
        tmp_path / "protected.sqlite",
        tmp_path / "protected-mlflow",
        data_kind="synthetic",
    )
    predictor.protected_events = frozenset({plan.fit[0]})
    from entropytrade.agents.fixture import demo_specs

    with pytest.raises(ValueError, match="protected boundary"):
        predictor.prepare(demo_specs()[0], "ridge")
    assert not (tmp_path / "protected-models").exists()


def test_scalar_labels_are_source_matched_revision_clocked_and_not_bias_leaks(
    tmp_path: Path, captures: list[Path]
) -> None:
    # CONTROLLED scalar receipts appended to authentic forecast copies; never empirical.
    from decimal import Decimal

    from entropytrade.ml.experiment import _examples

    source = tmp_path / "controlled-labels"
    shutil.copytree(captures[0], source)
    manifest = json.loads((source / "manifest.json").read_text())
    market = json.loads((source / "markets.jsonl").read_text().splitlines()[0])["market"]
    day = date.fromisoformat(market["rules"]["settlement_target_date"])
    station = next(
        p["station"]
        for p in manifest["weather_config"]["locations"]
        if p["series"] == market["series_ticker"]
    )
    available = datetime.combine(day + timedelta(days=2), datetime.min.time(), UTC)
    raw = source / "raw/controlled-scalar.json"
    raw.write_text('{"evidence": "CONTROLLED scalar labels, not empirical"}')
    wrong = Observation(
        source_id="nws-cli",
        entity_id=station,
        variable="settlement_high_f",
        valid_on=day,
        value=Decimal(90),
        unit="degF",
        role="observation",
        timing_basis="received",
        received_at=available,
        available_at=available,
        raw_ref="raw/controlled-scalar.json",
        raw_hash=file_hash(raw),
        evidence="CONTROLLED source test",
    )
    correct = wrong.revalidated(
        source_id="weather-company", value=Decimal(70), revision_id="original"
    )
    revised = correct.revalidated(
        value=Decimal(71),
        revision_id="corrected",
        available_at=available + timedelta(days=2),
        received_at=available + timedelta(days=2),
        revised_at=available + timedelta(days=2),
    )
    normalized = source / "observations.jsonl"
    with normalized.open("a") as stream:
        for label in (wrong, correct, revised):
            stream.write(label.model_dump_json() + "\n")
    for name in ("raw/controlled-scalar.json", "observations.jsonl"):
        manifest["checksums"][name] = file_hash(source / name)
    manifest["dataset_version"] = scientific_hash(
        {k: v for k, v in manifest.items() if k != "dataset_version"}
    )
    (source / "manifest.json").write_text(json.dumps(manifest))
    snapshot = build_snapshot(tmp_path / "datasets", [source])
    root = tmp_path / "datasets" / snapshot["dataset_id"].removeprefix("sha256:")
    rows = feature_rows(root, snapshot)
    selected = [r for r in rows if r["event_id"] == market["event_ticker"]]
    assert selected
    assert all(r["temperature_target_f"] == 70 for r in selected)
    assert all(r["temperature_available_at"] == available.isoformat() for r in selected)
    assert not _examples(selected, (market["event_ticker"],), available - timedelta(seconds=1))
    assert (
        _examples(selected, (market["event_ticker"],), available + timedelta(days=1))[0].target_f
        == 70
    )
    assert (
        _examples(selected, (market["event_ticker"],), available + timedelta(days=3))[0].target_f
        == 71
    )
    protected = build_snapshot(
        tmp_path / "datasets", [source], protected_events=frozenset({market["event_ticker"]})
    )
    protected_root = tmp_path / "datasets" / protected["dataset_id"].removeprefix("sha256:")
    for row in feature_rows(protected_root, protected):
        if row["event_id"] == market["event_ticker"]:
            assert row["temperature_target_f"] is None
        assert (
            market["event_ticker"] not in json.loads(row["feature_evidence_json"])["bias_event_ids"]
        )


def test_official_binary_receipts_preserve_availability_without_scalar_inference(
    tmp_path: Path, captures: list[Path]
) -> None:
    import asyncio

    import httpx

    from entropytrade.data.schema import MarketEvidence
    from entropytrade.domain.time import SimulatedClock
    from entropytrade.tracking.worker import outcomes

    capture = captures[0]
    evidence = MarketEvidence.model_validate_json(
        (capture / "markets.jsonl").read_text().splitlines()[0]
    )
    market = evidence.market
    raw = next(
        m
        for m in json.loads((capture / evidence.raw_ref).read_text())["markets"]
        if m["ticker"] == market.ticker
    )
    received = market.close_time + timedelta(days=2)
    raw.update(
        status="finalized",
        result="yes",
        settlement_value_dollars="1.0000",
        settlement_ts=(market.close_time + timedelta(minutes=1)).isoformat(),
    )
    cycle = tmp_path / "controlled-outcomes"
    cycle.mkdir()
    result = asyncio.run(
        outcomes(
            cycle / "outcomes",
            [
                {
                    "ticker": market.ticker,
                    "market": {
                        "market": market.model_dump(mode="json", exclude_computed_fields=True)
                    },
                    "outcome": None,
                    "last_attempt": "",
                }
            ],
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"market": raw})
            ),
            clock=SimulatedClock(received),
        )
    )
    assert len(result["outcomes"]) == 1
    snapshot = build_snapshot(tmp_path / "datasets", captures, outcome_roots=[cycle, cycle])
    root = tmp_path / "datasets" / snapshot["dataset_id"].removeprefix("sha256:")
    selected = [r for r in feature_rows(root, snapshot) if r["market_ticker"] == market.ticker]
    assert selected
    assert all(
        r["outcome"] == "yes" and r["outcome_available_at"] == received.isoformat()
        for r in selected
    )
    assert all(r["temperature_target_f"] is None for r in selected)
    assert (
        build_snapshot(tmp_path / "replay", list(reversed(captures)), outcome_roots=[cycle])
        == snapshot
    )
    raw_path = cycle / result["outcomes"][0]["receipt"]["raw_ref"]
    raw_path.write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        build_snapshot(tmp_path / "corrupt", captures, outcome_roots=[cycle])


def test_calendar_membership_stays_frozen_with_overnight_and_repeated_decisions() -> None:
    from entropytrade.features.pipeline import feature_rows as transform
    from entropytrade.ml.experiment import _examples
    from tests.r2_support import LOCATION, row

    start = date(2025, 1, 1)
    rows = [row(start + timedelta(days=n)) for n in range(100)]
    # CONTROLLED: decisions arrive before target day and recur across UTC midnight.
    repeated = []
    for item in rows:
        at = datetime.fromisoformat(item["decision_time"])
        item["decision_time"] = (at - timedelta(days=1)).isoformat()
        repeated.append({**item, "decision_time": (at + timedelta(hours=10)).isoformat()})
    cuts = (start + timedelta(days=48), start + timedelta(days=60), start + timedelta(days=90))
    observations = []
    for item in rows:
        target = date.fromisoformat(item["target_date"])
        at = datetime.fromisoformat(item["decision_time"])
        observations.extend(
            [
                observation(target, 70, at - timedelta(hours=1), revision=target.isoformat()),
                observation(
                    target,
                    71,
                    at + timedelta(days=2),
                    source="weather-company",
                    role="observation",
                    variable="settlement_high_f",
                    revision=target.isoformat(),
                ),
            ]
        )
    transformed = transform(rows + repeated, observations, [LOCATION])
    plan = temporal_plan(transformed, cuts)
    assert len(plan.fit) == 48
    assert len(plan.calibration) == 12
    assert len(plan.validation) == 30
    assert len(plan.holdout) == 10
    assert plan.fit_asof == min(
        datetime.fromisoformat(r["decision_time"])
        for r in rows
        if r["event_id"] in plan.calibration
    )
    examples = _examples(transformed, plan.fit, plan.fit_asof)
    assert examples
    assert all(e.decision <= plan.fit_asof and e.label_available <= plan.fit_asof for e in examples)
    assert not {e.event_id for e in examples} & set(
        plan.calibration + plan.validation + plan.holdout
    )


def test_shadow_discovery_checks_committed_receipts_before_snapshot(
    tmp_path: Path, captures: list[Path]
) -> None:
    from uuid import uuid4

    from entropytrade.api.jobs import Jobs
    from entropytrade.tracking.store import TrackingStore

    jobs = Jobs(tmp_path / "workspace")
    TrackingStore(jobs)
    job_id = jobs.create(
        {"idea": "CONTROLLED discovery metadata", "family": "weather", "mode": "recorded"}
    )
    monitor_id, cycle_id = str(uuid4()), str(uuid4())
    source = captures[0].parent
    root = jobs.root / "shadow" / monitor_id / cycle_id
    shutil.copytree(source, root)
    result = json.loads((root / "result.json").read_text())
    at = result["capture"]["decision_time"]
    with jobs.connect() as db:
        db.execute(
            "INSERT INTO monitors VALUES (?, ?, 'controlled', 'weather', '{}', 'unused', "
            "'paused', 300, ?, ?, 0, NULL)",
            (monitor_id, job_id, at, at),
        )
        db.execute(
            "INSERT INTO shadow_cycles VALUES (?, ?, 1, 'completed', ?, ?, "
            "'authentic receipt replay', ?, ?)",
            (cycle_id, monitor_id, at, at, json.dumps(result), scientific_hash(result)),
        )
    retained, outcomes, protected = jobs.weather_inputs()
    assert retained == [root / "public"]
    assert outcomes == [root]
    snapshot = build_snapshot(
        jobs.root / "runs/weather-datasets",
        retained,
        outcome_roots=outcomes,
        protected_events=protected,
    )
    assert snapshot["capture_count"] == 1
    assert snapshot["readiness"]["scalar_label_events"] == 0
    (root / "outcomes/summary.json").write_text('{"outcomes": [], "modified": true}')
    with pytest.raises(ValueError, match="missing or corrupt evidence artifact"):
        jobs.weather_inputs()
