"""Actual controlled multi-day paper wire evidence; never authentic prospective skill."""

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from entropytrade.domain.time import SimulatedClock
from entropytrade.research.readiness_evidence import ReadinessFacts, assess_readiness
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
)
from tests.research_paper_support import PaperFixture, paper_fixture


def readiness_fixture(workspace: Path, *, cycles: int = 23) -> tuple[PaperFixture, ReadinessFacts]:
    fixture = paper_fixture(workspace)
    deployed = MODEL_NOW + timedelta(minutes=1)
    with patch("entropytrade.tracking.store.timestamp", return_value=deployed.isoformat()):
        created = fixture.service.create(fixture.job_id, fixture.request)
    clock = SimulatedClock(MODEL_NOW.replace(hour=23, minute=0, second=5))
    for offset in range(cycles):
        when = MODEL_NOW.replace(hour=23, minute=0, second=5) + timedelta(days=offset)
        result = commit_controlled_cycle(fixture, when, clock=clock)
        if (
            result["outcome_failures"]
            or result["model_refusals"]
            or result["research_features"]["failures"]
        ):
            raise AssertionError(
                f"controlled day {offset}: outcomes={result['outcome_failures']} "
                f"model={result['model_refusals']} "
                f"features={result['research_features']['failures']}"
            )
    monitor = fixture.tracking.get(created["id"], export=True)
    assert monitor is not None
    with controlled_forward_environment(clock):
        facts = assess_readiness(workspace, monitor, clock=clock, expected_data_kind="synthetic")
    return fixture, facts
