"""Deterministic research-to-paper promotion. No browser-supplied model or risk policy."""

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore, select_fee
from entropytrade.features.registry import scientific_hash
from entropytrade.research.modeling import _path, _read_result
from entropytrade.research.paper_models import load_research_binding, verify_research_binding
from entropytrade.research.store import job_identifier, reject_collector_chain
from entropytrade.tracking.evaluate import shadow_limits

if TYPE_CHECKING:
    from entropytrade.tracking.store import TrackingStore

SCHEMA = "research-paper-eligibility-v1"
POLICY = "research-paper-gates-v1"


def validate_paper_policy(eligibility: dict[str, Any]) -> None:
    """Reject policy drift before a worker can use different monetary controls."""
    if eligibility.get("policy_version") != POLICY:
        raise ValueError("paper eligibility policy changed; new validation is required")
    if eligibility.get("risk_limits") != shadow_limits().model_dump(mode="json"):
        raise ValueError("paper deterministic risk configuration changed")


class PaperEligibilityError(ValueError):
    def __init__(self, proposal: dict[str, Any]) -> None:
        super().__init__("Research evidence does not satisfy paper deployment gates")
        self.proposal = proposal


def _rows(workspace: Path, job_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = workspace / "research"
    reject_collector_chain(root)
    path = root / "research.sqlite"
    if not path.is_file() or path.is_symlink():
        raise KeyError("research job not found")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA trusted_schema=OFF")
        row = db.execute(
            "SELECT id,status,request FROM research_jobs WHERE id=?", (job_identifier(job_id),)
        ).fetchone()
        if row is None:
            raise KeyError("research job not found")
        experiments = [
            dict(r)
            for r in db.execute(
                "SELECT id,hypothesis_id,status,result FROM research_experiments "
                "WHERE job_id=? ORDER BY created_at,rowid",
                (job_id,),
            )
        ]
    for entry in experiments:
        entry["result"] = json.loads(entry["result"]) if entry["result"] else None
    job = dict(row)
    job["request"] = json.loads(job["request"])
    return job, experiments


def _source(
    workspace: Path, job_id: str, experiment_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    job, rows = _rows(workspace, job_id)
    row = next((r for r in rows if r["id"] == experiment_id), None)
    if row is None or row["status"] != "completed" or not row["result"]:
        raise ValueError("select a completed immutable research experiment")
    result = _read_result(_path(workspace / "research", "experiments", experiment_id))
    if result != row["result"] or result.get("experiment_id") != experiment_id:
        raise ValueError("research report differs from its persisted experiment")
    spec = result["provenance"]["identity"]["spec"]
    if spec["hypothesis_id"] != row["hypothesis_id"]:
        raise ValueError("research hypothesis/experiment reference mismatch")
    return job, result


class ResearchPaperService:
    def __init__(
        self,
        workspace: Path,
        tracking: "TrackingStore",
        *,
        clock: Clock | None = None,
        expected_data_kind: Literal["real", "synthetic"] = "real",
    ) -> None:
        self.workspace, self.tracking = workspace, tracking
        self.clock = clock or SystemClock()
        # Only controlled test fixtures inject synthetic evidence. No API/CLI selects this.
        self.expected_data_kind = expected_data_kind

    def proposals(self, job_id: str) -> dict[str, Any]:
        try:
            _, rows = _rows(self.workspace, job_id)
        except sqlite3.Error as exc:
            raise ValueError("research paper source metadata failed verification") from exc
        proposals = []
        for row in rows:
            if row["status"] != "completed" or not row["result"]:
                continue
            for family in sorted(row["result"].get("models", {})):
                proposal, _, _ = self.evaluate(job_id, row["id"], family)
                proposals.append(proposal)
        return {"job_id": job_id, "proposals": proposals, "submission_enabled": False}

    def evaluate(
        self, job_id: str, experiment_id: str, model_family: str
    ) -> tuple[dict[str, Any], StrategySpec | None, dict[str, Any] | None]:
        checks: list[dict[str, Any]] = []
        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "policy_version": POLICY,
            "research_job_id": job_id,
            "experiment_id": experiment_id,
            "model_family": model_family,
            "eligible": False,
            "checks": checks,
            "reasons": [],
            "source_hashes": {},
            "validation_summary": {},
            "submission_enabled": False,
            "risk_limits": shadow_limits().model_dump(mode="json"),
        }
        spec: StrategySpec | None = None
        binding: dict[str, Any] | None = None

        def check(name: str, reason: str, *, passed: bool) -> None:
            checks.append({"name": name, "passed": bool(passed), "reason": reason})

        try:
            job, result = _source(self.workspace, job_id, experiment_id)
            entry = result["models"].get(model_family)
            if not entry:
                raise ValueError("select a fitted model from this experiment")
            backtest = entry.get("backtest", {})
            performance = backtest.get("performance") or {}
            payload.update(
                hypothesis_id=result["provenance"]["identity"]["spec"]["hypothesis_id"],
                model_hash=entry["artifact_hash"],
                data_kind=result["data_kind"],
            )
            check(
                "job_active",
                "The originating research job must retain a valid scientific result",
                passed=job["status"] not in {"failed", "cancelled"},
            )
            check(
                "paper_preference",
                "This research request must permit paper deployment",
                passed=job["request"].get("paper_preference", "never") != "never",
            )
            check(
                "authentic_evidence",
                (
                    "Production paper deployments require authentic "
                    "evidence; synthetic demonstrations cannot be promoted"
                ),
                passed=result["data_kind"] == self.expected_data_kind,
            )
            validation = result["validation"]
            check(
                "temporal_validation",
                (
                    "Independent chronological validation must be "
                    "evaluated with the protected holdout untouched"
                ),
                passed=validation.get("status") == "evaluated"
                and validation.get("holdout_evaluated") is False,
            )
            metrics = performance.get("forecast_metrics") or {}
            check(
                "independent_events",
                "At least twenty independent contract validation events are required",
                passed=metrics.get("status") == "evaluated"
                and metrics.get("independent_events", 0) >= 20,
            )
            accepted = performance.get("status") == (
                "PROMISING_FOR_FURTHER_VALIDATION"
                if self.expected_data_kind == "real"
                else "BACKTESTED"
            )
            check(
                "accepted_backtest",
                (
                    "Replay must pass statistical and execution robustness "
                    "gates; rejected or incomplete results cannot promote"
                ),
                passed=bool(backtest.get("eligible"))
                and performance.get("tested") is True
                and accepted,
            )
            scenarios = performance.get("scenarios") or []
            required_scenarios = {"optimistic", "base", "conservative"}
            check(
                "execution_fidelity",
                "Paper promotion requires sized-book replay in all three execution scenarios",
                passed=backtest.get("execution_fidelity") == "order_book_simulation"
                and len(scenarios) == 3
                and {s.get("scenario") for s in scenarios} == required_scenarios
                and all(
                    s.get("execution_fidelity") == "sized_snapshot_taker_simulation"
                    for s in scenarios
                ),
            )
            check(
                "settled_scenarios",
                "Every replay scenario must have complete settlement accounting",
                passed=bool(scenarios)
                and all(
                    not s.get("unsettled_positions") and s.get("net_pnl") is not None
                    for s in scenarios
                ),
            )
            if self.expected_data_kind == "real":
                check(
                    "recorded_execution_coverage",
                    "Orders require recorded post-decision receipts available at execution",
                    passed=bool(scenarios)
                    and all(
                        s.get("execution_clock_mode") == "recorded_post_decision_receipts"
                        and s.get("execution_evidence_complete") is True
                        for s in scenarios
                    ),
                )

                def positive_interval(value: object) -> bool:
                    if not isinstance(value, dict):
                        return False
                    try:
                        lower, upper = float(value["lower"]), float(value["upper"])
                    except (ValueError, TypeError, KeyError):
                        return False
                    return math.isfinite(lower) and math.isfinite(upper) and 0 < lower <= upper

                check(
                    "robust_validation",
                    "Independent Brier skill and each execution scenario need positive "
                    "date-block uncertainty bounds",
                    passed=positive_interval(performance.get("brier_improvement_interval"))
                    and all(
                        positive_interval(s.get("mean_date_pnl_interval"))
                        and s.get("fill_count", 0) >= 10
                        for s in scenarios
                    ),
                )
            raw_spec = performance.get("executed_spec") or backtest.get("strategy")
            if not raw_spec:
                raise ValueError("No executed typed strategy is frozen for this model")
            spec = StrategySpec.model_validate(raw_spec)
            check(
                "executed_strategy",
                "Strategy, model and executed hashes must match exactly",
                passed=performance.get("executed_spec_hash") == spec.spec_hash()
                and spec.model_ref is not None
                and (spec.model_ref.family == model_family)
                and (spec.model_ref.version == entry["artifact_hash"]),
            )
            binding = load_research_binding(
                self.workspace / "research",
                experiment_id,
                model_family,
                expected_model_hash=entry["artifact_hash"],
                data_kind=self.expected_data_kind,
            )
            model = verify_research_binding(spec, binding, data_kind=self.expected_data_kind)
            check(
                "portable_model",
                "Checksum-verified data-only model; no executable model loading",
                passed=True,
            )
            check(
                "model_available",
                "The fitted artifact must actually exist before deployment",
                passed=model.available_at <= self.clock.now(),
            )
            supported = {"nws_pfm_max_f", "nws_pfm_revision_f", "nws_cli_bias_f"}
            check(
                "forward_features",
                (
                    "Forward execution requires reviewed exact "
                    "PFM/CLI definitions and Philadelphia source mapping"
                ),
                passed=set(model.feature_names) <= supported
                and all(item["entity"] == "CLIPHL" for item in model.series_locations.values()),
            )
            fees = FeeEvidenceStore(self.workspace).snapshot()
            selected = {}
            for series in spec.market_universe.series_tickers:
                policy, audit = select_fee(
                    fees, series=series, when=self.clock.now(), data_kind=self.expected_data_kind
                )
                selected[series] = audit["version"]
                check(
                    "current_fees:" + series,
                    (
                        "A unique current certified fee version is "
                        "required; fees are checked again at each decision"
                    ),
                    passed=policy is not None,
                )
            payload.update(
                strategy_hash=spec.spec_hash(),
                binding_hash=binding["binding_hash"],
                feature_definitions_hash=model.feature_schema_hash,
                binding_summary={
                    "kind": binding["kind"],
                    "feature_names": list(model.feature_names),
                    "selected_schedule": model.selected_schedule.model_dump(mode="json"),
                    "available_at": model.available_at.isoformat(),
                },
                source_hashes={
                    "report": binding["report_hash"],
                    "portable": binding["artifact"]["sha256"],
                    "job_request": scientific_hash(job["request"]),
                    "current_fee_versions": selected,
                },
                validation_summary={
                    "metrics": metrics,
                    "status": performance.get("status"),
                    "prospective": False,
                    "holdout_evaluated": False,
                    "search_trials": result.get("requested_trial_count"),
                    "selection_adjusted": False,
                    "scope": "Historical evidence; paper starts at deployment",
                },
            )
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
            check(
                "verified_source",
                (
                    "Frozen model, strategy or source evidence is "
                    "unavailable or failed verification; rerun compatible modeling"
                ),
                passed=False,
            )
        payload["eligible"] = bool(checks) and all(c["passed"] for c in checks)
        payload["reasons"] = [c["reason"] for c in checks if not c["passed"]]
        payload["proposal_hash"] = scientific_hash(payload)
        if binding is not None and spec is not None:
            from entropytrade.tracking.store import research_deployment_key

            key = research_deployment_key(
                {
                    "research_job_id": job_id,
                    "experiment_id": experiment_id,
                    "spec_hash": spec.spec_hash(),
                    "binding_hash": binding["binding_hash"],
                    "eligibility": payload,
                }
            )
            existing = next(
                (m for m in self.tracking.history() if m.get("deployment_key") == key), None
            )
            if existing:
                payload = payload | {
                    "existing_deployment": {"id": existing["id"], "status": existing["status"]}
                }
        return payload, spec, binding

    def create(self, job_id: str, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {
            "experiment_id",
            "model_family",
            "interval_seconds",
        }:
            raise ValueError("provide experiment_id, model_family and interval_seconds only")
        if not isinstance(value["experiment_id"], str) or not isinstance(
            value["model_family"], str
        ):
            raise ValueError("experiment/model references must be strings")
        proposal, spec, binding = self.evaluate(
            job_id, value["experiment_id"], value["model_family"]
        )
        if not proposal["eligible"] or spec is None or binding is None:
            raise PaperEligibilityError(proposal)
        eligibility = {k: v for k, v in proposal.items() if k != "existing_deployment"}
        monitor_id = self.tracking.create_research(
            research_job_id=job_id,
            experiment_id=value["experiment_id"],
            hypothesis_id=proposal["hypothesis_id"],
            spec=spec,
            binding=binding,
            eligibility=eligibility,
            interval_seconds=value["interval_seconds"],
        )
        return {
            "id": monitor_id,
            "created": "existing_deployment" not in proposal,
            "deployment": self.tracking.get(monitor_id),
            "submission_enabled": False,
        }


def verify_paper_origin(workspace: Path, monitor: dict[str, Any]) -> None:
    """Verify immutable historical promotion proof without repricing or fitting anything."""
    from entropytrade.tracking.store import validate_research_source

    source = validate_research_source(monitor)
    eligibility = source["eligibility"]
    validate_paper_policy(eligibility)
    if (
        scientific_hash({k: v for k, v in eligibility.items() if k != "proposal_hash"})
        != eligibility["proposal_hash"]
    ):
        raise ValueError("paper eligibility proof hash mismatch")
    job, result = _source(workspace, source["research_job_id"], source["experiment_id"])
    if eligibility["source_hashes"]["job_request"] != scientific_hash(job["request"]):
        raise ValueError("paper request changed")
    fee_store = FeeEvidenceStore(workspace)
    for version in eligibility["source_hashes"]["current_fee_versions"].values():
        if not isinstance(version, str):
            raise ValueError("paper promotion fee reference is missing")
        fee_store.get(version)
    kind = eligibility["data_kind"]
    if kind not in {"real", "synthetic"}:
        raise ValueError("invalid paper source provenance")
    family = eligibility["model_family"]
    spec = (
        StrategySpec.model_validate_json(monitor["spec"])
        if isinstance(monitor["spec"], str)
        else StrategySpec.model_validate(monitor["spec"])
    )
    binding = (
        json.loads(monitor["model_binding"])
        if isinstance(monitor["model_binding"], str)
        else monitor["model_binding"]
    )
    loaded = load_research_binding(
        workspace / "research",
        source["experiment_id"],
        family,
        expected_model_hash=eligibility["model_hash"],
        data_kind=kind,
    )
    if loaded != binding or spec.spec_hash() != source["spec_hash"]:
        raise ValueError("paper origin artifact or executed strategy changed")
    entry = result["models"][family]
    executed = entry["backtest"]["performance"]["executed_spec"]
    if StrategySpec.model_validate(executed) != spec or result["data_kind"] != kind:
        raise ValueError("paper deployment differs from its validated experiment")
    verify_research_binding(spec, binding, data_kind=kind)
