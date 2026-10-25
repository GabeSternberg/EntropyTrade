"""Local formulation is bounded, idea-responsive and does not require a provider."""

from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from entropytrade.agents.templates import formulate_templates
from entropytrade.strategies.interpret import compile_strategy

if TYPE_CHECKING:
    from entropytrade.agents.evidence import ResearchEvidence

RUN_ID = "00000000-0000-4000-8000-000000000099"


def evidence(*, bitcoin: bool = False) -> "ResearchEvidence":
    names = (
        ("spot_usd", "spot_minus_floor_usd", "hours_to_close")
        if bitcoin
        else ("forecast_high_f", "revision_f", "model_disagreement_f", "hours_to_close")
    )
    return cast(
        "ResearchEvidence",
        SimpleNamespace(
            calls=[
                {"evidence_id": "retrieved-coverage"},
                {"evidence_id": "retrieved-markets"},
                {"evidence_id": "retrieved-features"},
            ],
            markets=[{"series": "KXBTC" if bitcoin else "KXHIGHPHIL"}],
            registered_names=names,
            registered_versions=dict.fromkeys(names, "1"),
            coverage={
                "data_kind": "real",
                "configured_source_kinds": ["kalshi", "coinbase"]
                if bitcoin
                else ["kalshi", "open-meteo"],
            },
            config=SimpleNamespace(
                model_families=("forward_only",) if bitcoin else ("ridge", "forecast_error")
            ),
        ),
    )


def test_literal_idea_changes_typed_entry_without_changing_risk_or_universe() -> None:
    _, hypotheses, candidates, critique = formulate_templates(
        "Test revision_f >= 1.25 and hours_to_close < 8",
        evidence(),
        RUN_ID,
    )
    assert len(hypotheses.hypotheses) == 2
    assert len(candidates.candidates) == 2
    spec = candidates.candidates[0].spec
    assert spec is not None
    assert spec.market_universe.series_tickers == ("KXHIGHPHIL",)
    assert [(p.feature, p.op.value, p.threshold) for p in spec.entry_rules.all_of] == [
        ("model_yes_probability", "gt", Decimal(".55")),
        ("revision_f", "ge", Decimal("1.25")),
        ("hours_to_close", "lt", Decimal(8)),
    ]
    assert spec.risk_overrides_allowed == "none"
    assert spec.position_sizing.contracts == 1
    assert spec.generation_run_id is not None
    assert str(spec.generation_run_id) == RUN_ID
    assert callable(compile_strategy(spec))
    assert critique.verdicts[0].accept_for_experiment
    _, _, changed, _ = formulate_templates("revision_f < -2", evidence(), RUN_ID)
    assert changed.candidates[0].spec is not None
    assert changed.candidates[0].spec.entry_rules != spec.entry_rules


def test_bitcoin_uses_actual_registered_family_and_no_weather_model() -> None:
    note, hypotheses, candidates, _ = formulate_templates(
        "Does Bitcoin spot relative to the actual strike help?",
        evidence(bitcoin=True),
        RUN_ID,
    )
    assert hypotheses.hypotheses[0].market_family == "KXBTC"
    assert candidates.candidates[0].model_family == "forward_only"
    assert candidates.candidates[0].required_sources == ("kalshi", "coinbase")
    assert candidates.candidates[0].required_features == ("spot_minus_floor_usd",)
    assert "No language model" in note.limitations[0]


@pytest.mark.parametrize(
    "idea",
    [
        "Forecast revision hedge with Kelly",
        "model_disagreement_f != 2",
        "revision_f > 1 or revision_f < -1",
        "revision_f > 1e5",
        "tomorrow_outcome > 0",
        "some arbitrary idea about elections",
    ],
)
def test_unsupported_ideas_remain_non_executable(idea: str) -> None:
    _, _, candidates, critique = formulate_templates(idea, evidence(), RUN_ID)
    assert all(c.spec is None and c.missing_capability for c in candidates.candidates)
    assert all(not v.accept_for_experiment for v in critique.verdicts)


@pytest.mark.parametrize(
    "connector",
    ["xor", "XOR", "unless", "or", "nor", "if", "when", "then", "plus", "&&", "||", "&", "^", ""],
)
def test_only_explicit_and_can_connect_comparisons(connector: str) -> None:
    note, _, candidates, critique = formulate_templates(
        f"revision_f >= 1.25 {connector} hours_to_close < 8", evidence(), RUN_ID
    )
    assert all(c.spec is None for c in candidates.candidates)
    assert all("complete conjunction" in c.missing_capability for c in candidates.candidates)
    assert all(not v.accept_for_experiment for v in critique.verdicts)
    assert any("complete conjunction" in reason for reason in note.limitations)


@pytest.mark.parametrize(
    "idea",
    [
        "unless revision_f >= 1.25",
        "not revision_f >= 1.25",
        "revision_f >= 1.25 and not hours_to_close < 8",
        "revision_f >= 1.25 and hours_to_close < 8 unless bias improves",
        "revision_f >= 1.25 and",
        "and revision_f >= 1.25",
        "(revision_f >= 1.25 and hours_to_close < 8)",
        "revision_f >= 1.25, hours_to_close < 8",
        "Test revision_f >= 1.25 with hours_to_close < 8",
        "Please trade revision_f >= 1.25",
        "revision_f = 1.25",
        "revision_f => 1.25",
        "revision_f >= 1.25 < 8",
    ],
)
def test_full_comparison_expression_must_be_consumed(idea: str) -> None:
    _, _, candidates, critique = formulate_templates(idea, evidence(), RUN_ID)
    assert all(c.spec is None and c.missing_capability for c in candidates.candidates)
    assert all(not v.accept_for_experiment for v in critique.verdicts)


@pytest.mark.parametrize("idea", ["Weather XOR revision", "Weather unless revision", "not weather"])
def test_unsupported_logic_in_prose_remains_non_executable(idea: str) -> None:
    _, _, candidates, critique = formulate_templates(idea, evidence(), RUN_ID)
    assert all(c.spec is None for c in candidates.candidates)
    assert all(not v.accept_for_experiment for v in critique.verdicts)


@pytest.mark.parametrize("prefix", ["", "Test ", "Research "])
def test_conjunction_whitespace_case_and_decimal_representation(prefix: str) -> None:
    _, _, candidates, critique = formulate_templates(
        f"  {prefix}revision_f >= -1.250000 \n AND\t hours_to_close < 8  ",
        evidence(),
        RUN_ID,
    )
    for candidate in candidates.candidates:
        assert candidate.spec is not None
        first, second = candidate.spec.entry_rules.all_of[1:]
        assert first.threshold.as_tuple() == Decimal("-1.250000").as_tuple()
        assert second.threshold.as_tuple() == Decimal("8").as_tuple()
    assert all(v.accept_for_experiment for v in critique.verdicts)


@pytest.mark.parametrize(
    "token",
    [
        "1.2345678",
        "-0.0000001",
        "1.2e3",
        "1.2e-3",
        "-1.2E+3",
        "1,000",
        "1,000.25",
        "1_000",
        "1.25usd",
        "1.25.3",
    ],
)
def test_entire_numeric_token_is_rejected_without_executable_prefix(token: str) -> None:
    note, _, candidates, critique = formulate_templates(
        f"revision_f >= {token} and hours_to_close < 8", evidence(), RUN_ID
    )
    assert all(c.spec is None for c in candidates.candidates)
    assert all(
        "complete plain decimal tokens" in c.missing_capability for c in candidates.candidates
    )
    assert all(not v.accept_for_experiment for v in critique.verdicts)
    assert any("complete plain decimal tokens" in reason for reason in note.limitations)


@pytest.mark.parametrize("token", ["1.234567", "-0.000001", "1000", "1000.25"])
def test_supported_complete_numeric_token_preserves_exact_decimal(token: str) -> None:
    _, _, candidates, critique = formulate_templates(
        f"revision_f >= {token} and hours_to_close < 8", evidence(), RUN_ID
    )
    for candidate in candidates.candidates:
        assert candidate.spec is not None
        assert candidate.spec.entry_rules.all_of[1].threshold == Decimal(token)
        assert candidate.spec.entry_rules.all_of[2].threshold == Decimal(8)
    assert all(v.accept_for_experiment for v in critique.verdicts)


def test_prose_signal_selection_never_guesses_a_numerical_entry_threshold() -> None:
    _, hypotheses, candidates, _ = formulate_templates(
        "Research forecast disagreement in weather",
        evidence(),
        RUN_ID,
    )
    assert hypotheses.hypotheses[0].variables == ("model_disagreement_f",)
    spec = candidates.candidates[0].spec
    assert spec is not None
    assert len(spec.entry_rules.all_of) == 1
    assert spec.entry_rules.all_of[0].feature == "model_yes_probability"
