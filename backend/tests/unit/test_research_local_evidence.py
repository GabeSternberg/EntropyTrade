"""Original retained receipts bridge into research; no new external collection or returns."""

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.data.schema import MarketState
from entropytrade.data.sources import file_hash
from entropytrade.research import local_evidence
from entropytrade.research.acquire import RawStore, load_records
from entropytrade.research.execution_inputs import _records
from entropytrade.research.inventory import assess, inventory
from entropytrade.research.local_evidence import LocalExecutionAdapter, local_execution_evidence
from entropytrade.research.model import AssessmentStatus, DataKind, DataRequirement
from entropytrade.weather.history import build_snapshot
from tests.integration.shadow_history_fixture import seed_sustained
from tests.integration.weather_history_retained import SOURCE
from tests.shadow_support import execution_wire

NOW = datetime(2026, 11, 16, tzinfo=UTC)


@pytest.fixture(scope="module")
def source_snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("authentic-local-evidence")
    # Two previously retained authentic cycles: original clocks and raw source bodies.
    build_snapshot(workspace / "runs/weather-datasets", sorted(SOURCE.glob("*/*/public")))
    return workspace


def clone(source: Path, destination: Path) -> Path:
    shutil.copytree(source / "runs", destination / "runs")
    return destination


def test_authentic_local_snapshot_produces_typed_research_execution_records(
    source_snapshot: Path, tmp_path: Path
) -> None:
    workspace = clone(source_snapshot, tmp_path / "restored-workspace")
    original = {p: file_hash(p) for p in (workspace / "runs").rglob("*") if p.is_file()}
    result = local_execution_evidence(workspace, now=NOW)
    assert result["problems"] == []
    assert result["dataset_ids"]
    assert result["imported_bytes"] > 0
    root = workspace / "research"
    records = [r for identifier in result["dataset_ids"] for r in load_records(root, identifier)]
    assert {r["record_type"] for r in records} == {"market_evidence", "market_state"}
    markets, states, reduced, identities = _records(root, result["dataset_ids"], "real")
    assert markets
    assert states
    assert reduced == 0
    assert identities == []
    assert all(m.market.result is None for m, _ in markets)
    assert all(m.created_at is not None and m.created_at <= received for m, received in markets)
    assert all(
        s.available_at == s.received_at and received <= s.received_at
        for s, received in states
        if s.received_at
    )
    assert max(received for _, received in states) < NOW
    assert all(file_hash(path) == digest for path, digest in original.items())
    store = RawStore(root)
    for identifier in result["dataset_ids"]:
        manifest = json.loads(
            (
                root / "datasets" / identifier.replace("sha256:", "sha256-") / "manifest.json"
            ).read_text()
        )
        assert manifest["data_kind"] == "authentic"
        assert all(store.get(digest) for digest in manifest["raw_hashes"])
    assert result["inherited_boundaries"]["weather"]


def test_verified_local_copy_reuses_without_source_reparse_or_budget(
    source_snapshot: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = clone(source_snapshot, tmp_path / "reuse")
    first = local_execution_evidence(workspace, now=NOW)
    assert first["dataset_ids"]

    def refuse(*_: Any) -> None:
        raise AssertionError("cached local dataset reparsed original source")

    monkeypatch.setattr("entropytrade.research.local_evidence.load_snapshot", refuse)
    repeated = local_execution_evidence(workspace, now=NOW, max_bytes=0)
    assert repeated["problems"] == []
    assert repeated["dataset_ids"] == first["dataset_ids"]
    assert repeated["imported_bytes"] == 0


def test_zero_budget_copies_no_local_bytes(source_snapshot: Path, tmp_path: Path) -> None:
    workspace = clone(source_snapshot, tmp_path / "budget")
    result = local_execution_evidence(workspace, now=NOW, max_bytes=0)
    assert not result["dataset_ids"]
    assert result["imported_bytes"] == 0
    assert result["problems"]
    assert not (workspace / "research/raw").exists()


def test_tampered_source_snapshot_is_refused(source_snapshot: Path, tmp_path: Path) -> None:
    workspace = clone(source_snapshot, tmp_path / "corrupt")
    path = next((workspace / "runs/weather-datasets").glob("*/receipts/*/raw/0001.json"))
    path.write_bytes(path.read_bytes() + b" ")
    result = local_execution_evidence(workspace, now=NOW)
    assert not result["dataset_ids"]
    assert result["problems"]
    assert result["block_modeling"] is True
    assert result["inherited_boundaries"] == {}
    assert not (workspace / "research/raw").exists()


def test_inherited_holdout_exports_only_identity_shells(tmp_path: Path) -> None:
    workspace = tmp_path / "protected"
    build_snapshot(
        workspace / "runs/weather-datasets",
        sorted(SOURCE.glob("*/*/public")),
        frozen_anchor=date(2026, 7, 1),
    )
    result = local_execution_evidence(workspace, now=NOW)
    assert result["problems"] == []
    assert result["dataset_ids"]
    root = workspace / "research"
    records = [r for identifier in result["dataset_ids"] for r in load_records(root, identifier)]
    assert {r["record_type"] for r in records} == {"protected_identity"}
    assert all(
        set(r)
        == {"record_type", "ticker", "series", "target_date", "close_time", "raw_hash", "raw_ref"}
        for r in records
    )
    assert result["inherited_boundaries"]["weather"][2] == "2026-09-29"


def test_direct_canonical_chain_and_symlink_sources_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="canonical"):
        local_execution_evidence(tmp_path / "chain" / "restored", now=NOW)
    workspace = tmp_path / "workspace"
    (workspace / "runs").mkdir(parents=True)
    (workspace / "runs/weather-datasets").symlink_to(
        tmp_path / "elsewhere", target_is_directory=True
    )
    with pytest.raises(ValueError, match="symlink"):
        local_execution_evidence(workspace, now=NOW)


def test_raw_book_clock_matches_retained_source(source_snapshot: Path, tmp_path: Path) -> None:
    workspace = clone(source_snapshot, tmp_path / "clock")
    result = local_execution_evidence(workspace, now=NOW)
    states = [
        MarketState.model_validate({k: v for k, v in r.items() if k != "record_type"})
        for identifier in result["dataset_ids"]
        for r in load_records(workspace / "research", identifier)
        if r["record_type"] == "market_state"
    ]
    assert states
    assert all(
        str(s.available_at.year) == "2026" and s.available_at.month == 10
        for s in states
        if s.available_at
    )
    assert all(
        s.payload["received_at"] == s.available_at.isoformat().replace("+00:00", "Z")
        for s in states
        if s.available_at
    )


def test_cached_local_copy_survives_removal_of_source_snapshots(
    source_snapshot: Path, tmp_path: Path
) -> None:
    workspace = clone(source_snapshot, tmp_path / "independent")
    first = local_execution_evidence(workspace, now=NOW)
    shutil.rmtree(workspace / "runs/weather-datasets")
    reused = local_execution_evidence(workspace, now=NOW, max_bytes=0)
    assert reused["problems"] == []
    assert reused["dataset_ids"] == first["dataset_ids"]
    assert reused["inherited_boundaries"] == first["inherited_boundaries"]
    assert reused["imported_bytes"] == 0


def test_explicit_protection_before_calendar_holdout_blocks_scalar_modeling(tmp_path: Path) -> None:
    workspace = tmp_path / "incompatible-protection"
    build_snapshot(
        workspace / "runs/weather-datasets",
        sorted(SOURCE.glob("*/*/public")),
        protected_events=frozenset({"KXHIGHPHIL-26OCT30"}),
    )
    result = local_execution_evidence(workspace, now=NOW)
    assert result["dataset_ids"] == []
    assert result["block_modeling"] is True
    assert result["inherited_boundaries"] == {}
    assert result["problems"][0]["type"] == "SourceProtectionConflict"
    assert not (workspace / "research/raw").exists()


@pytest.mark.parametrize("kind", [DataKind.DECISION_QUOTES, DataKind.ORDER_BOOK_DEPTH])
def test_actual_two_sided_imported_books_satisfy_inventory_fidelity(
    source_snapshot: Path, tmp_path: Path, kind: DataKind
) -> None:
    workspace = clone(source_snapshot, tmp_path / "inventory")
    local_execution_evidence(workspace, now=NOW)
    records, problems = inventory(workspace, Path(__file__).resolve().parents[3])
    assert problems == []
    imported = next(r for r in records if r.origin == "research_acquisition" and r.kind is kind)
    assert imported.fidelity == "order_book"
    series, days = next(iter(imported.coverage.items()))
    requirement = DataRequirement(
        requirement_id="retained-books",
        kind=kind,
        family="weather",
        entity=series,
        series=series,
        variable="yes_quotes" if kind is DataKind.DECISION_QUOTES else "yes_book",
        start=date.fromisoformat(min(days)),
        end=date.fromisoformat(max(days)),
        clock="receipt",
        fidelity="order_book",
        min_events=len(days),
        blocking="execution",
        purpose="Verified sized order books retaining original receipt clocks.",
    )
    result = assess(requirement, records, NOW)
    assert result.status is AssessmentStatus.SATISFIED
    assert result.events_available == len(days)


def test_removed_source_cache_protection_survives_a_newer_manifest(
    source_snapshot: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / "mixed-protection"
    build_snapshot(
        workspace / "runs/weather-datasets",
        sorted(SOURCE.glob("*/*/public")),
        frozen_anchor=date(2026, 7, 1),
    )
    first = local_execution_evidence(workspace, now=NOW)
    assert first["dataset_ids"]
    shutil.rmtree(workspace / "runs/weather-datasets")
    shutil.copytree(source_snapshot / "runs/weather-datasets", workspace / "runs/weather-datasets")
    combined = local_execution_evidence(workspace, now=NOW)
    assert combined["problems"] == []
    assert combined["inherited_boundaries"] == first["inherited_boundaries"]
    assert set(first["protected_events"]) <= set(combined["protected_events"])
    records = [
        r
        for identifier in combined["dataset_ids"]
        for r in load_records(workspace / "research", identifier)
    ]
    assert records
    assert {r["record_type"] for r in records} == {"protected_identity"}


def test_controlled_one_sided_books_do_not_satisfy_quote_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Actual collection/verification path with explicitly CONTROLLED HTTP payloads.
    # No empirical depth, external request, or performance result is represented here.
    def one_sided(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/orderbook"):
            return httpx.Response(
                200, json={"orderbook_fp": {"yes_dollars": [["0.42", "10"]], "no_dollars": []}}
            )
        return execution_wire(request)

    monkeypatch.setattr("tests.integration.shadow_history_fixture.execution_wire", one_sided)
    workspace = tmp_path / "controlled-missing-side"
    seed_sustained(workspace, count=1)
    build_snapshot(
        workspace / "runs/weather-datasets", sorted((workspace / "shadow").glob("*/*/public"))
    )
    result = local_execution_evidence(workspace, now=NOW)
    assert result["problems"] == []
    assert result["dataset_ids"]
    records, problems = inventory(workspace, Path(__file__).resolve().parents[3])
    assert problems == []
    assert not any(
        r.origin == "research_acquisition"
        and r.kind in {DataKind.DECISION_QUOTES, DataKind.ORDER_BOOK_DEPTH}
        for r in records
    )


def test_legacy_cache_protection_survives_fidelity_adapter_upgrade(
    source_snapshot: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = clone(source_snapshot, tmp_path / "legacy-cache")
    monkeypatch.setattr(LocalExecutionAdapter, "version", "1")
    previous = local_execution_evidence(workspace, now=NOW)
    assert previous["dataset_ids"]
    monkeypatch.setattr(LocalExecutionAdapter, "version", "2")
    upgraded = local_execution_evidence(workspace, now=NOW)
    assert upgraded["problems"] == []
    assert upgraded["dataset_ids"] != previous["dataset_ids"]
    assert upgraded["inherited_boundaries"] == previous["inherited_boundaries"]
    for identifier in upgraded["dataset_ids"]:
        parameters = json.loads(
            (
                workspace
                / "research/datasets"
                / identifier.replace("sha256:", "sha256-")
                / "parameters.json"
            ).read_text()
        )
        assert parameters["fidelity_by_kind"] == {
            "decision_quotes": "order_book",
            "order_book_depth": "order_book",
        }
    # Even removed source snapshots cannot erase the earlier verified protection.
    shutil.rmtree(workspace / "runs/weather-datasets")
    independent = local_execution_evidence(workspace, now=NOW, max_bytes=0)
    assert independent["inherited_boundaries"] == previous["inherited_boundaries"]


def test_source_mutation_during_copy_publishes_no_execution_dataset(
    source_snapshot: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = clone(source_snapshot, tmp_path / "changed-during-copy")
    original = local_evidence._collect

    def change(*args: Any, **kwargs: Any) -> Any:
        collected = original(*args, **kwargs)
        path = next((workspace / "runs/weather-datasets").glob("*/receipts/*/markets.jsonl"))
        path.write_bytes(path.read_bytes() + b"\n")
        return collected

    monkeypatch.setattr(local_evidence, "_collect", change)
    result = local_execution_evidence(workspace, now=NOW)
    assert not result["dataset_ids"]
    assert result["problems"]
    assert result["imported_bytes"] == 0
    assert not (workspace / "research/raw").exists()


def test_exact_local_serialization_cannot_exceed_import_byte_budget(
    source_snapshot: Path, tmp_path: Path
) -> None:
    measured = local_execution_evidence(clone(source_snapshot, tmp_path / "measured"), now=NOW)
    required = measured["imported_bytes"]
    assert required > 0
    exact = local_execution_evidence(
        clone(source_snapshot, tmp_path / "exact"), now=NOW, max_bytes=required
    )
    assert exact["problems"] == []
    assert exact["dataset_ids"] == measured["dataset_ids"]
    assert exact["imported_bytes"] == required
    workspace = clone(source_snapshot, tmp_path / "short")
    refused = local_execution_evidence(workspace, now=NOW, max_bytes=required - 1)
    assert refused["problems"]
    assert not refused["dataset_ids"]
    assert refused["imported_bytes"] == 0
    assert not (workspace / "research/raw").exists()
    assert not list((workspace / "research").glob(".local-stage-*"))
