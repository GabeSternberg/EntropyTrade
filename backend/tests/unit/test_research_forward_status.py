"""Collection plans and sanitized summaries never prove active collection."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from entropytrade.features.registry import scientific_hash
from entropytrade.research.forward import decorate_forward
from entropytrade.research.inventory import COLLECTOR_STATUS_SCHEMA, inventory
from entropytrade.research.model import Assessment, AssessmentStatus, DataKind, DataRequirement

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[3]


def need() -> DataRequirement:
    return DataRequirement(
        requirement_id="quotes",
        kind=DataKind.DECISION_QUOTES,
        family="weather",
        entity="KXHIGHPHIL",
        series="KXHIGHPHIL",
        variable="yes_quotes",
        start=date(2026, 11, 1),
        end=date(2026, 11, 14),
        clock="receipt",
        fidelity="quote",
        min_events=14,
        blocking="execution",
        purpose="Original decision-time market quotes for simulation.",
    )


def request(requirement: DataRequirement) -> dict[str, Any]:
    return {
        "coverage_key": requirement.coverage_key,
        "collector_status": "covered",
        # A shared count may be stale or from a different job/window.
        "events_observed": 99,
        "events_required": 14,
        "status": "satisfied",
        "last_error": None,
    }


def test_repository_coverage_and_shared_counts_only_prove_a_plan() -> None:
    requirement = need()
    assessment = Assessment(
        requirement_id="quotes",
        status=AssessmentStatus.MISSING,
        events_available=0,
        events_required=14,
        assessed_at=NOW,
    )
    (row,) = decorate_forward([request(requirement)], [requirement], {"quotes": assessment}, NOW)
    assert row["operational_status"] == "planned"
    assert row["deployment_verified"] is False
    assert row["recent_receipts_verified"] is False
    assert "not been verified" in row["operational_detail"]


def test_sufficiency_uses_the_current_jobs_requirement_assessment() -> None:
    requirement = need()
    assessment = Assessment(
        requirement_id="quotes",
        status=AssessmentStatus.SATISFIED,
        events_available=14,
        events_required=14,
        datasets=("actual-retained-evidence",),
        assessed_at=NOW,
    )
    (row,) = decorate_forward([request(requirement)], [requirement], {"quotes": assessment}, NOW)
    assert row["operational_status"] == "sufficient"
    assert row["recent_receipts_verified"] is False  # sufficient history is not active collection


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"collector_status": "requires_collector_change"}, "blocked"),
        ({"last_error": "source unavailable"}, "stalled"),
        ({"last_error": "source unavailable", "status": "failed"}, "failed"),
    ],
)
def test_collection_block_and_failure_states(changes: dict[str, Any], expected: str) -> None:
    requirement = need()
    (row,) = decorate_forward([request(requirement) | changes], [requirement], {}, NOW)
    assert row["operational_status"] == expected


@pytest.mark.parametrize("damage", ["checksum", "timezone"])
def test_malformed_sanitized_status_is_reported_and_excluded(tmp_path: Path, damage: str) -> None:
    body: dict[str, Any] = {"slices": [], "problems": []}
    value = {
        "schema": COLLECTOR_STATUS_SCHEMA,
        "generated_at": NOW.isoformat(),
        "chain_head": scientific_hash(body),
        "source": "canonical_local_chain",
        **body,
    }
    if damage == "checksum":
        value["problems"] = [{"origin": "tampered", "error": "changed"}]
    else:
        value["generated_at"] = "2026-11-15T12:00:00"
    directory = tmp_path / "research" / "collector-status"
    directory.mkdir(parents=True)
    (directory / "summary.json").write_text(json.dumps(value))
    records, problems = inventory(tmp_path, REPO)
    assert not any(r.origin == "collector_status" for r in records)
    assert {"origin": "collector_status", "error": "ValueError"} in problems
