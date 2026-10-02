"""Philadelphia research demo. TestModel only; the CLI label never enters the prompt."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.agents.fixture import LABEL_AT, RUN_ID, philadelphia_deps, scripted_models
from entropytrade.agents.guard import (
    openai_constructor_error,
    provider_requests_blocked,
    require_no_provider_request,
)
from entropytrade.agents.pipeline import PipelineError, run_philadelphia_demo, run_pipeline
from entropytrade.domain.runs import ResearchRunStatus, SampleSplit, SplitWindow


def test_provider_requests_stay_blocked() -> None:
    assert provider_requests_blocked()
    with pytest.raises(RuntimeError, match="ALLOW_MODEL_REQUESTS"):
        require_no_provider_request()
    message = openai_constructor_error()
    assert "OPENAI_API_KEY" in message
    assert message.startswith("UserError")


def test_demo_ranks_fixture_specs_and_hides_the_label() -> None:
    first = run_philadelphia_demo()
    second = run_philadelphia_demo()
    assert first.ranked_ids() == ("phl-probability-055", "phl-probability-090")
    traded = next(item for item in first.backtests if item.strategy_id == "phl-probability-055")
    quiet = next(item for item in first.backtests if item.strategy_id == "phl-probability-090")
    assert traded.ending_equity == Decimal("100.60")
    assert traded.fill_ids
    assert quiet.ending_equity == Decimal("100")
    assert quiet.fill_ids == ()
    assert first.run.status is ResearchRunStatus.COMPLETED
    assert first.run.report is not None
    assert len(first.run.strategy_spec_hashes) == 4
    reasons = {item.strategy_id: item.reason for item in first.rejected}
    assert "Duplicate" in reasons["phl-copy-rejected"]
    assert "fixed_contracts" in reasons["phl-kelly"]
    assert "phl-copy-rejected" not in first.ranked_ids()
    assert set(first.tool_log) == {"list_forecasts", "list_books"}
    rows = philadelphia_deps().forecast_rows()
    assert rows[0]["value"] == "90"
    blob = "\n".join((*first.prompts, *rows[0].values()))
    assert "91" not in blob
    assert traded.digest == second.backtests[0].digest
    summary = first.analyst_summary()
    assert "phl-probability-055 equity 100.60" in summary
    assert "rejected phl-copy-rejected" in summary
    assert "91" not in summary


def test_holdout_never_reaches_the_agents() -> None:
    window = SplitWindow(
        split=SampleSplit.HOLDOUT,
        start=datetime(2026, 10, 4, tzinfo=UTC),
        end=datetime(2026, 10, 5, tzinfo=UTC),
    )
    with pytest.raises(PipelineError, match="holdout"):
        run_pipeline(
            prompt="x",
            deps=philadelphia_deps(),
            records=(),
            books=(),
            settlements=(),
            window=window,
            models=scripted_models(),
            now=LABEL_AT,
            run_id=RUN_ID,
        )


def test_agents_do_not_name_an_order_tool() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "agents"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "submit_order" not in text
    assert "KalshiGateway" not in text
