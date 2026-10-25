"""Candidate gates independent of LLM opinions. No backtests or lifecycle promotion."""

import re
from typing import Any

from entropytrade.agents.evidence import ResearchEvidence
from entropytrade.agents.outputs import CandidateBatch, HypothesisBatch, ResearchCritique
from entropytrade.domain.strategy import ModelKind
from entropytrade.features.registry import FEATURE_NAMES, scientific_hash
from entropytrade.strategies.interpret import UnsupportedSpecError, compile_strategy


def hypothesis_signature(mechanism: str, variables: tuple[str, ...]) -> str:
    return scientific_hash(
        {
            "mechanism": " ".join(re.sub(r"\d+(?:\.\d+)?", "#", mechanism.casefold()).split()),
            "variables": sorted(variables),
        }
    )


def validate_candidates(
    candidates: CandidateBatch,
    hypotheses: HypothesisBatch,
    critique: ResearchCritique,
    evidence: ResearchEvidence,
    *,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    known = {h.hypothesis_id: h for h in hypotheses.hypotheses}
    if len(known) != len(hypotheses.hypotheses):
        raise ValueError("duplicate hypothesis IDs")
    ids = {c.candidate_id for c in candidates.candidates}
    verdicts = {v.candidate_id: v for v in critique.verdicts}
    if (
        len(ids) != len(candidates.candidates)
        or len(verdicts) != len(critique.verdicts)
        or ids != set(verdicts)
    ):
        raise ValueError("critic must provide exactly one verdict per unique candidate")
    seen_evidence = {c["evidence_id"] for c in evidence.calls}
    markets = {r["market_ticker"] for r in evidence.markets}
    events = {r["event_id"] for r in evidence.markets}
    series = {r["series"] for r in evidence.markets}
    prior = {
        hypothesis_signature(h["mechanism"], tuple(h["variables"]))
        for run in evidence.history
        for h in run.get("hypotheses", [])
    }
    results = []
    signatures: set[str] = set()
    for candidate in candidates.candidates:
        invalid: list[str] = []
        unsupported: list[str] = []
        missing: list[str] = []
        hypothesis = known.get(candidate.hypothesis_id)
        if hypothesis is None:
            invalid.append("unknown hypothesis reference")
        signature = ""
        if hypothesis:
            signature = hypothesis_signature(hypothesis.mechanism, hypothesis.variables)
            references = set(hypothesis.evidence_ids) | set(candidate.evidence_ids)
            if not references <= seen_evidence:
                invalid.append("citation was not retrieved through the evidence tools")
            if signature in signatures:
                invalid.append("duplicate hypothesis within this search")
            signatures.add(signature)
            if hypothesis.market_family not in series:
                invalid.append("hypothesis market family is absent from the permitted universe")
        required = set(candidate.required_features)
        if hypothesis:
            required.update(hypothesis.variables)
        spec = candidate.spec
        if spec:
            required.update(f.name for f in spec.features)
            required.update(p.feature for p in spec.entry_rules.all_of)
            universe = spec.market_universe
            if (
                not set(universe.market_tickers) <= markets
                or not set(universe.event_tickers) <= events
                or not set(universe.series_tickers) <= series
            ):
                invalid.append("hallucinated or protected market universe")
            if (
                hypothesis
                and universe.series_tickers
                and hypothesis.market_family not in universe.series_tickers
            ):
                invalid.append("spec universe contradicts hypothesis")
            if run_id and (
                str(spec.generation_run_id) != run_id or spec.generated_by.kind.value != "agent"
            ):
                invalid.append("spec must identify the current agent research run")
            # StrategySpec validates the Literal["none"] risk boundary during parsing.
            if any(
                f.version
                not in (
                    {None, "r2-prediction-v1"} if f.name == "model_yes_probability" else {None, "1"}
                )
                for f in spec.features
            ):
                invalid.append("unknown feature version")
            if spec.citations and any(
                c.source not in seen_evidence or c.url is not None for c in spec.citations
            ):
                invalid.append(
                    "spec citation must reference retrieved evidence IDs without invented URLs"
                )
            try:
                compile_strategy(spec)  # Validate only; never invoke the returned replay callable.
            except UnsupportedSpecError as exc:
                unsupported.append(str(exc))
            if spec.execution.max_spread is not None:
                unsupported.append("per-spec spread enforcement requires R4")
            if (
                spec.position_sizing.dollars is not None
                or spec.position_sizing.kelly_fraction is not None
            ):
                unsupported.append(
                    "extra sizing fields are not enforced by the fixed-contract interpreter"
                )
            if spec.hedging_rules or spec.maximum_holding_period_seconds is not None:
                unsupported.append("hedging/holding-period enforcement requires R4")
            # The legacy interpreter ignores exit predicates; only the explicit settlement
            # marker is safe.
            if any(
                p.feature != "settlement" or p.op.value != "eq" or p.threshold != 1
                for p in spec.exit_rules.all_of
            ):
                unsupported.append("exit predicates are not implemented")
            if spec.model_kind is not ModelKind.NONE and candidate.model_family == "none":
                invalid.append("spec requires a model but candidate supplies none")
            if set(spec.required_sources) != set(candidate.required_sources):
                invalid.append("spec/candidate source requirements disagree")
        else:
            unsupported.append(
                candidate.missing_capability or "proposal has no faithful StrategySpec"
            )
        if spec and candidate.missing_capability:
            unsupported.append(candidate.missing_capability)
        if required - set(FEATURE_NAMES) - {"model_yes_probability"}:
            invalid.append(
                "unknown feature references: "
                + ", ".join(sorted(required - set(FEATURE_NAMES) - {"model_yes_probability"}))
            )
        scoped_coverage = evidence.coverage["by_series"].get(
            hypothesis.market_family if hypothesis else "", {}
        )
        missing.extend(
            "no point-in-time observations for " + name
            for name in sorted(required & set(FEATURE_NAMES))
            if scoped_coverage.get("features", {}).get(name, 0) == 0
        )
        if candidate.model_family not in {
            "none",
            "climatology",
            "raw_forecast",
            "forecast_error",
            "ridge",
            "boosting",
        }:
            invalid.append("unknown model family")
        elif candidate.model_family != "none" or "model_yes_probability" in required:
            diagnostic = evidence.models.get("models", {}).get(candidate.model_family, {})
            if not diagnostic.get("artifact_available"):
                missing.append("required real fitted probability artifact is unavailable")
            if not diagnostic.get("validation_is_permitted"):
                missing.append("model validation coverage is not permitted by the research cutoff")
            if evidence.models.get("data_kind") != "real":
                missing.append("synthetic diagnostics cannot substantiate real candidates")
        missing.extend(
            "no certified decision-time coverage for source " + source
            for source in candidate.required_sources
            if source not in {"kalshi", "weather-company", "nws-cli"}
            and scoped_coverage.get("source_counts", {}).get(source, 0) == 0
        )
        if set(candidate.required_sources) - {
            "kalshi",
            "open-meteo",
            "nws",
            "weather-company",
            "nws-cli",
        }:
            invalid.append("unknown source adapter")
        scoped = [
            r for r in evidence.markets if hypothesis and r["series"] == hypothesis.market_family
        ]
        if not scoped or any(not r["rules_known"] for r in scoped):
            missing.append("historical rules and settlement semantics are not certified")
        if any(r["rules"].get("settlement_basis") != "contract_text" for r in scoped):
            missing.append("settlement authority is not established by contract text")
        if (
            scoped_coverage.get("eligible_events", 0) < 60
            or scoped_coverage.get("scalar_label_events", 0) < 60
        ):
            missing.append("insufficient independent eligible events/source-matched scalar labels")
        if not any(r["execution_fidelity"] == "order_book" for r in scoped):
            missing.append("no executable historical depth; candles/prints cannot establish fills")
        verdict = verdicts[candidate.candidate_id]
        status = (
            "REJECTED"
            if invalid
            else "UNSUPPORTED"
            if unsupported
            else "REJECTED"
            if not verdict.accept_for_experiment
            else "INSUFFICIENT_DATA"
            if missing
            else "READY_FOR_EXPERIMENT"
        )
        results.append(
            {
                "candidate_id": candidate.candidate_id,
                "status": status,
                "structurally_valid": not invalid and not unsupported,
                "reasons": invalid + unsupported + missing,
                "critic": verdict.model_dump(mode="json"),
                "hypothesis_signature": signature,
                "previously_searched": signature in prior,
                "spec_hash": spec.spec_hash() if spec else None,
                "scope": "research eligibility only; no trading approval or proven edge",
            }
        )
    return results


def analyst_report(run: dict[str, Any]) -> str:
    """Factual report from deterministic evidence/gates; agent prose stays labeled hypothesis."""
    coverage = run["coverage"]
    lines = [
        "# Agent research report",
        "",
        f"Mode: {run['mode']}; run: {run['run_id']}",
        f"Question: {run['prompt']}",
        "",
        "Known data (protected dates excluded):",
        f"{coverage['independent_events']} city/day events across {coverage['date_blocks']} dates; "
        f"{coverage['contracts']} contracts; "
        f"{coverage['eligible_events']} eligible forecast events; "
        f"{coverage['scalar_label_events']} source-matched scalar-label events.",
        "No backtest was run. No predictive or trading edge is established.",
        "",
        "Candidate hypotheses (unverified agent proposals):",
    ]
    hypotheses = {h["hypothesis_id"]: h for h in run["hypotheses"]}
    for candidate, decision in zip(run["candidates"], run["decisions"], strict=True):
        hypothesis = hypotheses.get(candidate["hypothesis_id"], {})
        lines += [
            "",
            f"{candidate['candidate_id']}: {decision['status']}",
            hypothesis.get("mechanism", "unknown hypothesis"),
            "Falsification: " + hypothesis.get("falsification", "unspecified"),
            "Reasons: " + "; ".join(decision["reasons"]),
            "Critic: " + decision["critic"]["reason"],
            "Previously searched: " + str(decision["previously_searched"]),
        ]
    lines += [
        "",
        "Next experiments: collect certified decision-time forecast vintages and actual rule "
        "snapshots; obtain the contract's named scalar settlement source; accumulate independent "
        "events; fit/calibrate with R2 temporal gates before R4 execution experiments.",
        "Candidate readiness does not imply profitability, validation or permission to trade.",
    ]
    return "\n".join(lines) + "\n"
