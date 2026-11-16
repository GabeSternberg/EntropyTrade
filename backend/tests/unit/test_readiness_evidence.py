"""Readiness uses genuine forward inputs; controlled wire evidence stays synthetic."""

import copy
import math
from datetime import date, timedelta
from typing import Any

import pytest

from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.models import WeatherModel
from entropytrade.research.readiness_evidence import (
    ReadinessFacts,
    assess_degradation,
    assess_readiness,
    degradation_from_observations,
    proper_score_facts,
    verify_facts,
    verify_frozen_evidence,
)
from tests.research_paper_forward_support import controlled_forward_environment
from tests.research_paper_support import PaperFixture
from tests.research_readiness_support import readiness_fixture


@pytest.fixture(scope="module")
def ready(tmp_path_factory: pytest.TempPathFactory) -> tuple[PaperFixture, ReadinessFacts]:
    return readiness_fixture(tmp_path_factory.mktemp("readiness-evidence") / "workspace")


def rows(count: int = 20, *, wrong: bool = False) -> list[dict[str, Any]]:
    result = []
    for i in range(count):
        day = (date(2027, 1, 1) + timedelta(days=i)).isoformat()
        outcome = i % 2
        probability = 0.9 if outcome else 0.1
        result.append(
            {
                "event_id": "CLIPHL:" + day,
                "target_date": day,
                "ticker": "SYNTHETIC-" + day,
                "outcome": outcome,
                "probability_yes": 1 - probability if wrong else probability,
                "baseline_probability": 0.5,
            }
        )
    return result


def monitor_for(fixture: PaperFixture) -> dict[str, Any]:
    monitor = fixture.tracking.get(fixture.tracking.history()[0]["id"], export=True)
    assert monitor is not None
    return monitor


def test_actual_twenty_three_wire_cycles_establish_controlled_evidence_only(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    _, facts = ready
    assert facts.eligible
    assert facts.source_refs["data_kind"] == "synthetic"
    assert len(facts.paper_prefix) == 23
    assert facts.scores.independent_events == 21
    assert facts.scores.independent_dates == 21
    assert facts.scores.quote_coverage == 1
    assert facts.scores.baseline is not None
    assert facts.scores.baseline["brier"] == pytest.approx((0.325 - 1) ** 2)
    assert facts.account["fill_count"] == 23
    assert facts.account["settlement_count"] == 21
    assert facts.account["open_positions"] == 2
    assert facts.prospective["pending_overdue"] == 0
    assert "valued at cost" in facts.account["limitation"]
    assert facts.submission_enabled is False
    assert verify_facts(facts.model_dump(mode="json")) == facts


def test_refresh_clock_never_changes_frozen_evidence_or_source_bytes(
    ready: tuple[PaperFixture, ReadinessFacts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, facts = ready
    before = {
        p.relative_to(fixture.jobs.root).as_posix(): file_hash(p)
        for p in fixture.jobs.root.rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("readiness must not fit a model")

    monkeypatch.setattr(WeatherModel, "fit", forbidden)
    clock = SimulatedClock(facts.evidence_as_of + timedelta(hours=2))
    with controlled_forward_environment(clock):
        refreshed = assess_readiness(
            fixture.jobs.root, monitor_for(fixture), clock=clock, expected_data_kind="synthetic"
        )
    assert refreshed == facts
    assert before == {
        p.relative_to(fixture.jobs.root).as_posix(): file_hash(p)
        for p in fixture.jobs.root.rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }


def test_production_policy_cannot_accept_controlled_paper_evidence(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    fixture, facts = ready
    clock = SimulatedClock(facts.evidence_as_of)
    with controlled_forward_environment(clock):
        result = assess_readiness(fixture.jobs.root, monitor_for(fixture), clock=clock)
    assert not result.eligible
    assert any(not check.passed for check in result.checks)
    assert result.paper_prefix == ()
    assert result.scores.model is None
    assert "model_hash" not in result.source_refs
    verify_frozen_evidence(fixture.jobs.root, monitor_for(fixture), result)


def test_partial_source_refusal_restores_without_a_model(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    fixture, facts = ready
    monitor = monitor_for(fixture)
    monitor["model_binding"] = None
    clock = SimulatedClock(facts.evidence_as_of)
    with controlled_forward_environment(clock):
        refused = assess_readiness(fixture.jobs.root, monitor, clock=clock)
    assert not refused.eligible
    assert set(refused.source_refs) == {"spec_hash", "deployment_key"}
    assert refused.paper_prefix == ()
    verify_frozen_evidence(fixture.jobs.root, monitor, refused)


def test_no_new_complete_independent_window_is_pending_not_recovery(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    fixture, facts = ready
    clock = SimulatedClock(facts.evidence_as_of)
    with controlled_forward_environment(clock):
        value = assess_degradation(
            fixture.jobs.root,
            monitor_for(fixture),
            clock=clock,
            reference=facts,
            expected_data_kind="synthetic",
        )
    assert value.status == "pending"
    assert value.window_id is None
    assert not value.signals


def test_proper_scores_and_block_intervals_are_seeded_and_correct() -> None:
    first, second = proper_score_facts(rows()), proper_score_facts(list(reversed(rows())))
    assert first == second
    assert first.status == "evaluated"
    assert first.model is not None
    assert first.baseline is not None
    assert first.model["brier"] == 0.01
    assert first.model["log_loss"] == pytest.approx(-math.log(0.9))
    assert first.baseline["brier"] == 0.25
    assert first.brier_skill_interval is not None
    assert first.brier_skill_interval["lower"] == pytest.approx(0.24)
    assert first.selection_adjusted is False


def test_contracts_and_ticks_cannot_inflate_independent_events() -> None:
    repeated = rows()
    for i, row in enumerate(repeated):
        row.update(
            event_id="CLIPHL:2027-01-01", target_date="2027-01-01", ticker=f"SYNTHETIC-STRIKE-{i}"
        )
    value = proper_score_facts(repeated)
    assert value.status == "insufficient"
    assert value.independent_events == value.independent_dates == 1
    assert value.brier_skill_interval is None


@pytest.mark.parametrize("failure", ["too_few_events", "too_few_dates", "missing_quote"])
def test_incomplete_evidence_never_gets_a_skill_interval(failure: str) -> None:
    observations = rows(19 if failure == "too_few_events" else 20)
    if failure == "too_few_dates":
        for i, row in enumerate(observations):
            row["target_date"] = f"2027-01-{i % 9 + 1:02}"
    if failure == "missing_quote":
        observations[-1]["baseline_probability"] = None
    value = proper_score_facts(observations)
    assert value.status == "insufficient"
    assert value.brier_skill_interval is None


@pytest.mark.parametrize("failure", ["nan", "future_probability", "duplicate", "wrong_outcome"])
def test_invalid_observations_refuse(failure: str) -> None:
    observations = rows()
    if failure == "nan":
        observations[0]["probability_yes"] = float("nan")
    elif failure == "future_probability":
        observations[0]["baseline_probability"] = 1.1
    elif failure == "duplicate":
        observations.append(observations[0])
    else:
        observations[0]["outcome"] = 0.5
    with pytest.raises(ValueError, match=r"invalid|repeated"):
        proper_score_facts(observations)


def test_frozen_fact_restore_validates_hash_without_refitting_calibration(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    original = ready[1].model_dump(mode="json")
    changed = copy.deepcopy(original)
    changed["scores"]["model"]["brier"] += 1e-8
    with pytest.raises(ValueError, match="facts hash"):
        verify_facts(changed)
    assert verify_facts(original).evidence_hash == ready[1].evidence_hash


def test_frozen_source_prefix_restore_does_not_recompute_metrics(
    ready: tuple[PaperFixture, ReadinessFacts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, facts = ready

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("restore must not refit or rescore readiness metrics")

    monkeypatch.setattr("entropytrade.research.readiness_evidence.proper_score_facts", forbidden)
    verify_frozen_evidence(fixture.jobs.root, monitor_for(fixture), facts)


def test_append_only_later_cycle_does_not_invalidate_a_frozen_prefix(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    from uuid import uuid4

    fixture, facts = ready
    cid = str(uuid4())
    when = (facts.evidence_as_of + timedelta(days=1)).isoformat()
    with fixture.jobs.connect() as db:
        db.execute(
            "INSERT INTO shadow_cycles(id,monitor_id,sequence,status,started_at,finished_at,"
            "detail,result,digest) VALUES (?,?,?,'interrupted',?,?,'CONTROLLED later "
            "interrupted cycle',NULL,NULL)",
            (cid, facts.monitor_id, len(facts.paper_prefix) + 1, when, when),
        )
    try:
        verify_frozen_evidence(fixture.jobs.root, monitor_for(fixture), facts)
    finally:
        with fixture.jobs.connect() as db:
            db.execute("DELETE FROM shadow_cycles WHERE id=?", (cid,))


def test_new_nonoverlapping_bad_window_degrades_and_good_window_is_stable(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    facts = ready[1]
    bad = degradation_from_observations(facts, facts, rows(wrong=True))
    assert bad.status == "degraded"
    assert bad.signals[0]["kind"] == "forecast_degradation"
    assert bad.investigation_objective
    assert bad.submission_enabled is False
    assert degradation_from_observations(facts, facts, rows()).status == "stable"
    assert degradation_from_observations(facts, facts, rows(19, wrong=True)).status == "pending"


def test_all_complete_windows_are_checked_and_later_good_cannot_clear_earlier_bad(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    facts = ready[1]

    def shifted(values: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
        shifted_rows = copy.deepcopy(values)
        for row in shifted_rows:
            day = (date.fromisoformat(row["target_date"]) + timedelta(days=days)).isoformat()
            row.update(event_id="CLIPHL:" + day, target_date=day, ticker="SYNTHETIC-" + day)
        return shifted_rows

    first = rows()
    bad = shifted(rows(wrong=True), 20)
    later_good = shifted(rows(), 40)
    initial = degradation_from_observations(facts, facts, first)
    assert initial.status == "stable"
    degraded = degradation_from_observations(facts, facts, first + bad)
    assert degraded.status == "degraded"
    assert degraded.window_id != initial.window_id
    retained = degradation_from_observations(facts, facts, first + bad + later_good)
    assert retained.status == "degraded"
    assert retained.window_id == degraded.window_id
    assert degradation_from_observations(facts, facts, list(reversed(first + bad))).window_id == (
        degraded.window_id
    )
    latest_stable = degradation_from_observations(facts, facts, first + shifted(rows(), 20))
    assert latest_stable.status == "stable"
    assert latest_stable.window_id != initial.window_id
    assert degradation_from_observations(facts, facts, first + bad[:19]).window_id == (
        initial.window_id
    )


def test_changed_model_reference_is_blocked_not_labeled_performance_degradation(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    facts = ready[1]
    changed = facts.revalidated(
        source_refs={**facts.source_refs, "model_hash": "sha256:" + "a" * 64}
    )
    changed = changed.revalidated(
        evidence_hash=scientific_hash(changed.model_dump(mode="json", exclude={"evidence_hash"}))
    )
    value = degradation_from_observations(facts, changed, rows())
    assert value.status == "blocked"
    assert value.signals[0]["kind"] == "evidence_integrity"


def test_corrupt_genuine_receipt_blocks_evidence_instead_of_dropping_a_loser(
    ready: tuple[PaperFixture, ReadinessFacts],
) -> None:
    fixture, facts = ready
    first = facts.paper_prefix[0]["cycle_id"]
    monitor = monitor_for(fixture)
    root = fixture.jobs.root / "shadow" / monitor["id"] / first
    target = next((root / "execution").glob("*.json"))
    original = target.read_bytes()
    target.write_bytes(b"CONTROLLED corrupted receipt")
    try:
        clock = SimulatedClock(facts.evidence_as_of)
        with controlled_forward_environment(clock):
            refused = assess_readiness(
                fixture.jobs.root, monitor, clock=clock, expected_data_kind="synthetic"
            )
        assert not refused.eligible
        assert refused.prospective["integrity_failures"]
    finally:
        target.write_bytes(original)
