"""Explicit CONTROLLED follow-up book receipts: causal decisions, no invented liquidity."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropytrade.backtest.replay import DecisionView, ReplayError, run_replay
from entropytrade.domain.enums import FeeType, MarketResult
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.domain.strategy import StrategySpec
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.experiments.data import ContractSample, ExperimentData, RecordedPredictions
from entropytrade.experiments.engine import ExperimentConfig, evaluate_candidate, run_experiments
from entropytrade.experiments.fee_replay import reproduce
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine
from tests.fee_support import controlled_fee
from tests.r4_support import nonweather
from tests.unit.test_replay import TICKER, TRAIN_START, _book, _feature, _intent, _limits


def observed(sample: ContractSample, *, delay: float = 0.5) -> ContractSample:
    assert sample.book is not None
    return sample.revalidated(
        book=sample.book.revalidated(received_at=sample.decision_time - timedelta(seconds=0.5)),
        execution_books=(
            sample.book.revalidated(received_at=sample.decision_time + timedelta(seconds=delay)),
        ),
    )


def test_empty_execution_extension_preserves_legacy_serialization() -> None:
    data, _, _, _ = nonweather()
    encoded = data.model_dump_json()
    assert "execution_books" not in encoded
    assert all("execution_books" not in s.model_dump(mode="json") for s in data.samples)
    before = json.loads(encoded)
    after = json.loads(ExperimentData.model_validate_json(encoded).model_dump_json())
    before["protected_events"] = sorted(before["protected_events"])
    after["protected_events"] = sorted(after["protected_events"])
    assert after == before
    assert all(
        ContractSample.model_validate_json(sample.model_dump_json()).model_dump_json()
        == sample.model_dump_json()
        for sample in data.samples
    )
    assert (
        data.samples[0].revalidated(execution_books=()).model_dump_json()
        == data.samples[0].model_dump_json()
    )


def test_execution_policy_is_versioned_and_legacy_value_keeps_old_config_shape() -> None:
    default = ExperimentConfig()
    assert default.model_dump(mode="json")["execution_policy"] == "recorded_receipts"
    legacy = default.revalidated(execution_policy="legacy_snapshot_sensitivity")
    assert "execution_policy" not in legacy.model_dump(mode="json")
    assert legacy.revalidated(latency_seconds=2).execution_policy == "legacy_snapshot_sensitivity"
    assert (
        legacy.revalidated(execution_policy="recorded_receipts").execution_policy
        == "recorded_receipts"
    )


def controlled_real_inputs(
    *, drift: bool
) -> tuple[dict[str, Any], ExperimentData, RecordedPredictions, ExperimentConfig]:
    """CONTROLLED real tag exercises routing; the fee flag is not an authentic certificate."""
    data, provider, research, config = nonweather()
    assert config.fee_policy is not None
    data = data.revalidated(
        data_kind="real",
        samples=tuple(
            sample.revalidated(
                book=sample.book.revalidated(
                    received_at=sample.decision_time - timedelta(seconds=0.5)
                )
            )
            if drift and sample.book is not None
            else sample
            for sample in data.samples
        ),
    )
    provider = RecordedPredictions(
        provider.bundle.revalidated(
            model_metadata={**provider.bundle.model_metadata, "data_kind": "real"}
        )
    )
    config = config.revalidated(fee_policy=config.fee_policy.revalidated(certified=True))
    spec = StrategySpec.model_validate(research["candidates"][0]["spec"])
    encoded = config.model_dump(mode="json")
    encoded.pop("execution_policy")
    inputs = {
        "schema": "experiment-replay-v1",
        "data": data.model_dump(mode="json"),
        "config": encoded,
        "research": research,
        "predictions": {
            str(("provided-frequency", spec.spec_hash())): provider.bundle.model_dump(mode="json")
        },
    }
    return inputs, data, provider, config


def test_new_real_exact_clock_quotes_cannot_supply_unobserved_delayed_execution() -> None:
    inputs, data, provider, config = controlled_real_inputs(drift=False)
    result = evaluate_candidate(
        inputs["research"]["candidates"][0], inputs["research"], data, provider, config
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    scenario = result["scenarios"][0]
    assert scenario["fill_count"] == 0
    assert scenario["missing_execution_receipts"] == 20
    assert scenario["net_pnl"] is None


def test_official_replay_loader_retains_old_real_book_clock_sensitivity() -> None:
    inputs, _, _, _ = controlled_real_inputs(drift=True)
    assert "execution_policy" not in inputs["config"]
    result = reproduce(inputs)
    assert result[0]["status"] == "REJECTED"
    assert result[0]["scenarios"][0]["fill_count"] == 0
    assert "execution_clock_mode" not in result[0]["scenarios"][0]
    # Golden hash generated by the actual pre-D C code (8ed8246), not an expected
    # value recalculated using this implementation. This is controlled simulation.
    assert scientific_hash(result) == (
        "sha256:8a2bd11b719adc7d6b1a154ed0ecca7f0fd710fee2e279632fa69c119b1438e8"
    )


@pytest.mark.parametrize("fault", ["same_clock", "close", "ticker", "future_exchange", "conflict"])
def test_followup_book_identity_and_original_clocks_are_validated(fault: str) -> None:
    sample = nonweather()[0].samples[0]
    assert sample.book is not None
    future = sample.book.revalidated(received_at=sample.decision_time + timedelta(seconds=0.5))
    books: tuple[OrderBook, ...] = (future,)
    if fault == "same_clock":
        books = (future.revalidated(received_at=sample.decision_time),)
    elif fault == "close":
        books = (future.revalidated(received_at=sample.close_time),)
    elif fault == "ticker":
        books = (future.revalidated(market_ticker="ANOTHER-CONTRACT"),)
    elif fault == "future_exchange":
        books = (future.revalidated(exchange_ts=future.received_at + timedelta(seconds=1)),)
    elif fault == "conflict":
        books = (future, future.revalidated(asks=()))
    with pytest.raises(ValueError, match=r"execution books|conflicting"):
        sample.revalidated(execution_books=books)


def test_actual_followup_books_reach_shared_engine_at_declared_decisions() -> None:
    data, provider, research, config = nonweather()
    changed = data.revalidated(samples=tuple(observed(s) for s in data.samples))
    result = evaluate_candidate(research["candidates"][0], research, changed, provider, config)
    assert result["tested"]
    scenario = result["scenarios"][0]
    assert scenario["execution_clock_mode"] == "recorded_post_decision_receipts"
    assert scenario["fill_count"] == 20
    assert scenario["execution_evidence_complete"] is True
    assert len(scenario["audit"]) == 20
    expected_decisions = {s.decision_time.isoformat() for s in changed.samples[50:70]}
    assert {a["decision_time"] for a in scenario["audit"]} == expected_decisions
    assert all(a["decision_time"] != a["time"] for a in scenario["audit"])


@pytest.mark.parametrize("followup", [False, True])
def test_absent_or_late_execution_receipts_cannot_fill_the_original_book(followup: bool) -> None:
    data, provider, research, config = nonweather()
    samples = []
    for sample in data.samples:
        modified = observed(sample, delay=2)
        if not followup:
            modified = modified.revalidated(execution_books=())
        samples.append(modified)
    changed = data.revalidated(samples=tuple(samples))
    result = evaluate_candidate(research["candidates"][0], research, changed, provider, config)
    assert result["tested"]
    scenario = result["scenarios"][0]
    assert scenario["fill_count"] == 0
    assert len(scenario["audit"]) == 20
    assert result["status"] == "INSUFFICIENT_DATA"
    assert scenario["execution_evidence_complete"] is False
    assert scenario["missing_execution_receipts"] == 20
    assert scenario["net_pnl"] is None
    assert all(a["status"] == "execution_evidence_missing" for a in scenario["audit"])


def test_missing_loser_execution_receipts_cannot_establish_subset_profitability() -> None:
    data, provider, research, config = nonweather()
    samples = tuple(
        observed(s).revalidated(execution_books=()) if s.outcome is MarketResult.NO else observed(s)
        for s in data.samples
    )
    result = evaluate_candidate(
        research["candidates"][0], research, data.revalidated(samples=samples), provider, config
    )
    scenario = result["scenarios"][0]
    assert scenario["fill_count"] == 15
    assert scenario["missing_execution_receipts"] == 5
    assert scenario["execution_evidence_complete"] is False
    assert result["status"] == "INSUFFICIENT_DATA"
    assert scenario["net_pnl"] is None
    assert scenario["drawdown_at_cost"] is None
    assert scenario["mean_date_pnl_interval"] is None


def test_missing_receipts_for_causal_abstentions_do_not_require_unsubmitted_execution() -> None:
    data, provider, research, config = nonweather()
    no_tickers = {s.ticker for s in data.samples if s.outcome is MarketResult.NO}
    samples = tuple(
        observed(s).revalidated(execution_books=()) if s.ticker in no_tickers else observed(s)
        for s in data.samples
    )
    provider = RecordedPredictions(
        provider.bundle.revalidated(
            records=tuple(
                p.revalidated(probability_yes=Decimal(".4")) if p.ticker in no_tickers else p
                for p in provider.bundle.records
            )
        )
    )
    result = evaluate_candidate(
        research["candidates"][0], research, data.revalidated(samples=samples), provider, config
    )
    scenario = result["scenarios"][0]
    assert scenario["fill_count"] == 15
    assert scenario["missing_execution_receipts"] == 0
    assert scenario["execution_evidence_complete"] is True
    assert result["status"] == "BACKTESTED"


@pytest.mark.parametrize("explicit", [False, True])
def test_zero_latency_requires_post_decision_evidence_only_in_explicit_mode(explicit: bool) -> None:
    data, provider, research, config = nonweather()
    if explicit:
        data = data.revalidated(samples=tuple(observed(s) for s in data.samples))
    result = evaluate_candidate(
        research["candidates"][0], research, data, provider, config.revalidated(latency_seconds=0)
    )
    scenario = result["scenarios"][0]
    assert scenario["fill_count"] == (0 if explicit else 20)
    if explicit:
        assert scenario["missing_execution_receipts"] == 20
    else:
        assert "execution_clock_mode" not in scenario


def test_future_book_events_do_not_trigger_strategies_or_reveal_future_features() -> None:
    when = TRAIN_START
    original = _book(10, ask="0.5000").revalidated(received_at=when - timedelta(seconds=0.5))
    later = original.revalidated(
        received_at=when + timedelta(seconds=0.5), asks=(_book(10, ask="0.4900").asks[0],)
    )
    seen: list[tuple[Any, Any, Any]] = []

    def strategy(view: DecisionView, book: OrderBook) -> OrderIntent:
        seen.append((view.decision_time, book.received_at, view.feature("settled_value", TICKER)))
        return _intent(view.decision_time)

    ledger = Ledger(Decimal(100), as_of=when)
    broker = PaperBroker(
        ledger,
        FeeSchedule(
            fee_type=FeeType.QUADRATIC,
            fee_multiplier=Decimal(1),
            maker_pays=False,
            quadratic_coefficient=Decimal(0),
        ),
    )
    run_replay(
        books=(original, later),
        decision_points=((when, original),),
        records=(
            _feature(10, "1").revalidated(
                available_at=when + timedelta(seconds=0.1),
                ingested_at=when + timedelta(seconds=0.1),
            ),
        ),
        strategy=strategy,
        ledger=ledger,
        broker=broker,
        engine=RiskEngine(_limits()),
        latency=timedelta(seconds=1),
        window=SplitWindow(
            split=SampleSplit.VALIDATION, start=when, end=when + timedelta(seconds=5)
        ),
    )
    assert seen == [(when, original.received_at, None)]
    assert len(ledger.fills()) == 1
    assert ledger.fills()[0].yes_price == Decimal(".5")  # later price improvement stays clamped


def test_explicit_replay_rejects_future_decision_books() -> None:
    when = TRAIN_START
    ledger = Ledger(Decimal(100), as_of=when)
    book = _book(10, ask=".5").revalidated(received_at=when + timedelta(seconds=1))
    with pytest.raises(ReplayError, match="causal"):
        run_replay(
            books=(book,),
            decision_points=((when, book),),
            records=(),
            strategy=lambda v, b: None,
            ledger=ledger,
            broker=PaperBroker(
                ledger,
                FeeSchedule(
                    fee_type=FeeType.QUADRATIC,
                    fee_multiplier=Decimal(1),
                    maker_pays=False,
                    quadratic_coefficient=Decimal(0),
                ),
            ),
            engine=RiskEngine(_limits()),
            latency=timedelta(seconds=1),
            window=SplitWindow(
                split=SampleSplit.VALIDATION, start=when, end=when + timedelta(seconds=5)
            ),
        )


def test_execution_fee_checks_use_declared_decision_and_execution_times() -> None:
    data, provider, research, config = nonweather()
    samples = tuple(observed(s) for s in data.samples)
    when = samples[50].decision_time
    fee = controlled_fee()
    assert fee.policy is not None
    known = when - timedelta(seconds=0.25)
    fee = fee.revalidated(reviewed_at=known, policy=fee.policy.revalidated(available_at=known))
    config = config.revalidated(fee_policy=None, fee_versions=(fee,))
    result = evaluate_candidate(
        research["candidates"][0], research, data.revalidated(samples=samples), provider, config
    )
    assert result["tested"]
    clocks = {a["decision_time"] for a in result["execution_fee_evidence"]}
    assert when.isoformat() in clocks
    assert (when - timedelta(seconds=0.5)).isoformat() not in clocks
    assert (when + timedelta(seconds=1)).isoformat() in clocks


def test_portable_protected_projection_withholds_future_execution_books(tmp_path: Path) -> None:
    data, provider, research, config = nonweather()
    data = data.revalidated(samples=tuple(observed(s) for s in data.samples))
    config = config.revalidated(fee_policy=None, fee_versions=(controlled_fee(),))
    result = run_experiments(
        research=research,
        data=data,
        provider=provider,
        config=config,
        registry_path=tmp_path / "registry.sqlite",
        output=tmp_path / "runs",
        tracking=tmp_path / "mlflow",
    )
    directory = tmp_path / "runs" / result["experiment_id"].removeprefix("sha256:")
    exported = json.loads((directory / "replay-inputs.json").read_text())
    protected = set(exported["data"]["protected_events"])
    for sample in exported["data"]["samples"]:
        if sample["event_id"] in protected:
            assert "execution_books" not in sample
            assert sample["book"] is None
        elif sample["execution_books"]:
            assert datetime.fromisoformat(
                sample["execution_books"][0]["received_at"]
            ) > datetime.fromisoformat(sample["decision_time"])
