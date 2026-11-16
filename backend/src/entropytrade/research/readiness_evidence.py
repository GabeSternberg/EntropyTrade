"""Read-only evidence for future readiness review; never authorizes money or trains.

Original observations stay unchanged. Reported diagnostics use declared precision;
restoration verifies stored facts and immutable references rather than refitting metrics.
"""

import json
import math
import sqlite3
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import Field

from entropytrade.api.jobs import Jobs, identifier
from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import Clock, UtcDatetime
from entropytrade.experiments.data import ExperimentData
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.research.paper import verify_paper_origin
from entropytrade.research.paper_models import verify_research_binding
from entropytrade.tracking.accounting import account_hash, summary
from entropytrade.tracking.alerts import settlement_expected
from entropytrade.tracking.history import verified_inputs
from entropytrade.tracking.prospective import report


class ReadinessPolicy(DomainModel):
    version: Literal["readiness-evidence-policy-v1"] = "readiness-evidence-policy-v1"
    min_events: int = Field(default=20, ge=20, le=1000)
    min_dates: int = Field(default=10, ge=10, le=365)
    bootstrap_samples: int = Field(default=1000, ge=1000, le=5000)
    seed: int = 17
    confidence: float = Field(default=0.95, ge=0.95, le=0.95)
    diagnostic_precision: Literal[12] = 12
    log_loss_clip: float = Field(default=1e-15, ge=1e-15, le=1e-15)
    minimum_brier_skill: float = Field(default=1e-6, ge=1e-6, allow_inf_nan=False)
    numerical_guard: float = Field(default=1e-12, ge=1e-12, le=1e-12)
    max_quote_age_seconds: Literal[60] = 60
    settlement_grace_seconds: Literal[3600] = 3600
    degradation_windows: Literal["all_complete_date_blocks_earliest_bad"] = (
        "all_complete_date_blocks_earliest_bad"
    )


class EvidenceCheck(DomainModel):
    name: str
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class ScoreFacts(DomainModel):
    status: Literal["insufficient", "evaluated"]
    observations: int
    independent_events: int
    independent_dates: int
    quoted_observations: int
    quote_coverage: float
    model: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None
    model_brier_interval: dict[str, Any] | None = None
    brier_skill_interval: dict[str, Any] | None = None
    log_loss_skill_interval: dict[str, Any] | None = None
    mean_brier_skill: float | None = None
    selection_adjusted: Literal[False] = False


class ReadinessFacts(DomainModel):
    schema_version: Literal["readiness-evidence-v1"] = "readiness-evidence-v1"
    policy: ReadinessPolicy
    evidence_as_of: UtcDatetime
    monitor_id: str
    source_refs: dict[str, Any]
    paper_prefix: tuple[dict[str, Any], ...]
    account: dict[str, Any]
    prospective: dict[str, Any]
    scores: ScoreFacts
    checks: tuple[EvidenceCheck, ...]
    eligible: bool
    evidence_hash: str
    limitations: tuple[str, ...] = (
        "This assessment cannot authorize live execution.",
        "Intervals are not adjusted for repeated strategy/model search.",
        "Quoted probabilities are benchmarks; paper fills remain simulations.",
        "Open positions and drawdown are valued at cost, not mark to market.",
    )
    submission_enabled: Literal[False] = False


class DegradationFacts(DomainModel):
    schema_version: Literal["readiness-degradation-v1"] = "readiness-degradation-v1"
    status: Literal["pending", "stable", "degraded", "blocked"]
    reference_hash: str
    evidence_hash: str
    window_id: str | None
    signals: tuple[dict[str, Any], ...]
    investigation_objective: str | None
    scores: ScoreFacts | None = None
    submission_enabled: Literal[False] = False


def verify_facts(value: ReadinessFacts | Mapping[str, Any]) -> ReadinessFacts:
    """Data-only restore validation. Never recomputes floating-point diagnostics."""
    facts = value if isinstance(value, ReadinessFacts) else ReadinessFacts.model_validate(value)
    if (
        scientific_hash(facts.model_dump(mode="json", exclude={"evidence_hash"}))
        != facts.evidence_hash
    ):
        raise ValueError("readiness facts hash mismatch")
    return facts


def verify_frozen_evidence(
    workspace: Path, monitor: dict[str, Any], facts: ReadinessFacts | Mapping[str, Any]
) -> None:
    """Verify original proof references, permitting append-only later paper cycles.

    No scoring, bootstrap, calibration or model fit is repeated. Existing source-policy
    checks and immutable artifact hashes remain authoritative after an offline restore.
    """
    from entropytrade.api.recovery import check_artifacts
    from entropytrade.domain.strategy import StrategySpec

    facts = verify_facts(facts)
    monitor = dict(monitor)
    for key in ("spec", "source_ref", "model_binding"):
        if isinstance(monitor.get(key), str):
            monitor[key] = json.loads(monitor[key])
    if identifier(monitor["id"]) != facts.monitor_id:
        raise ValueError("readiness monitor reference mismatch")
    complete_source = facts.eligible or any(
        item.name == "source_integrity" and item.passed for item in facts.checks
    )
    binding = monitor.get("model_binding") or {}
    snapshot = binding.get("snapshot") or {}
    model_hash: str | None
    feature_hash: str | None
    if complete_source:
        verify_paper_origin(workspace, monitor)
        kind = facts.source_refs.get("data_kind")
        if kind not in {"real", "synthetic"}:
            raise ValueError("readiness evidence provenance missing")
        model = verify_research_binding(
            StrategySpec.model_validate(monitor["spec"]), binding, data_kind=kind
        )
        model_hash, feature_hash = model.model_hash, model.feature_schema_hash
    else:
        # A frozen refusal may deliberately have no valid model/source or prefix.
        # Restore its claimed references without upgrading the failed checks into
        # eligibility. Approval always requires a fresh complete assessment.
        model_hash, feature_hash = snapshot.get("model_hash"), snapshot.get("feature_schema_hash")
    material = {
        "spec_hash": monitor["spec_hash"],
        "deployment_key": monitor.get("deployment_key"),
        "model_hash": model_hash,
        "binding_hash": binding.get("binding_hash"),
        "feature_schema_hash": feature_hash,
        "paper_source_hash": (monitor.get("source_ref") or {}).get("source_hash"),
        "historical_report_hash": binding.get("report_hash"),
        "data_kind": snapshot.get("data_kind"),
    }
    if any(
        facts.source_refs.get(key) != value
        for key, value in material.items()
        if complete_source or key in facts.source_refs
    ):
        raise ValueError("readiness immutable model, strategy or source reference changed")
    previous_account: str | None = None
    account_seen = False
    with closing(
        sqlite3.connect((workspace / "jobs.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("BEGIN")
        for expected, frozen in enumerate(facts.paper_prefix, 1):
            if frozen["sequence"] != expected:
                raise ValueError("readiness paper prefix is not contiguous")
            record = db.execute(
                "SELECT * FROM shadow_cycles WHERE monitor_id=? AND sequence=?",
                (facts.monitor_id, expected),
            ).fetchone()
            if (
                record is None
                or any(
                    record[name] != frozen[name]
                    for name in ("sequence", "status", "digest", "finished_at")
                )
                or record["id"] != frozen["cycle_id"]
            ):
                raise ValueError("readiness frozen paper prefix changed or is missing")
            if record["result"] is None:
                if record["digest"] is not None:
                    raise ValueError("readiness unfinished cycle has a content digest")
                continue
            value = json.loads(record["result"])
            root = workspace / "shadow" / facts.monitor_id / identifier(record["id"])
            if (
                scientific_hash(value) != record["digest"]
                or json.loads((root / "result.json").read_text()) != value
                or value.get("submission_enabled") is not False
            ):
                raise ValueError("readiness original cycle body changed")
            check_artifacts(root, value["artifacts"])
            if value.get("paper") is not None:
                paper, inputs = value["paper"], value["paper_inputs"]
                if not account_seen and inputs["before"] is not None:
                    raise ValueError("readiness original paper account did not start empty")
                if account_seen and inputs["before_hash"] != previous_account:
                    raise ValueError("readiness original paper account chain changed")
                if (
                    account_hash(inputs["before"]) != inputs["before_hash"]
                    or account_hash(paper["state"]) != paper["state_hash"]
                ):
                    raise ValueError("readiness original paper account checksum changed")
                previous_account, account_seen = paper["state_hash"], True
        if account_seen and previous_account != facts.source_refs.get("account_state_hash"):
            raise ValueError("readiness frozen account reference mismatch")


def _round(value: float, policy: ReadinessPolicy) -> float:
    return round(value, policy.diagnostic_precision)


def _loss(probability: float, outcome: int, clip: float) -> tuple[float, float]:
    bounded = max(clip, min(1 - clip, probability))
    return (probability - outcome) ** 2, -math.log(bounded if outcome else 1 - bounded)


def _proper(rows: Sequence[Mapping[str, Any]], key: str, policy: ReadinessPolicy) -> dict[str, Any]:
    events: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        events[str(row["event_id"])].append(row)
    brier = loss = 0.0
    bins: dict[int, list[tuple[float, int, float]]] = defaultdict(list)
    for values in events.values():
        for row in values:
            probability = float(row[key])
            outcome = int(row["outcome"])
            weight = 1 / (len(events) * len(values))
            squared, logarithmic = _loss(probability, outcome, policy.log_loss_clip)
            brier += weight * squared
            loss += weight * logarithmic
            bins[min(9, int(probability * 10))].append((probability, outcome, weight))
    return {
        "brier": _round(brier, policy),
        "log_loss": _round(loss, policy),
        "reliability_bins": [
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "mean_probability": _round(
                    sum(p * w for p, _, w in values) / sum(w for _, _, w in values), policy
                ),
                "observed_yes_rate": _round(
                    sum(y * w for _, y, w in values) / sum(w for _, _, w in values), policy
                ),
                "contracts": len(values),
            }
            for index, values in sorted(bins.items())
        ],
    }


def proper_score_facts(
    observations: Sequence[Mapping[str, Any]], *, policy: ReadinessPolicy | None = None
) -> ScoreFacts:
    """Equal event weights, with complete event/date blocks resampled together."""
    policy = policy or ReadinessPolicy()
    rows = sorted(
        observations,
        key=lambda row: (str(row["target_date"]), str(row["event_id"]), str(row["ticker"])),
    )
    seen = set()
    event_dates: dict[str, str] = {}
    for row in rows:
        key = (row["event_id"], row["ticker"])
        if key in seen or row["outcome"] not in {0, 1}:
            raise ValueError("repeated contract/event or invalid binary outcome")
        seen.add(key)
        event, day = str(row["event_id"]), str(row["target_date"])
        if event in event_dates and event_dates[event] != day:
            raise ValueError("one independent event cannot span target dates")
        event_dates[event] = day
        for name in ("probability_yes", "baseline_probability"):
            value = row.get(name)
            if value is not None and (
                not math.isfinite(float(value)) or not 0 <= float(value) <= 1
            ):
                raise ValueError("invalid proper-score probability")
        if row.get("probability_yes") is None:
            raise ValueError("proper scores require an actual frozen prediction")
    events = {str(row["event_id"]) for row in rows}
    dates = {str(row["target_date"]) for row in rows}
    quoted = [row for row in rows if row.get("baseline_probability") is not None]
    result: dict[str, Any] = {
        "status": "insufficient",
        "observations": len(rows),
        "independent_events": len(events),
        "independent_dates": len(dates),
        "quoted_observations": len(quoted),
        "quote_coverage": len(quoted) / len(rows) if rows else 0.0,
        "model": _proper(rows, "probability_yes", policy) if rows else None,
        "baseline": _proper(quoted, "baseline_probability", policy) if quoted else None,
    }
    if len(events) < policy.min_events or len(dates) < policy.min_dates or len(quoted) != len(rows):
        return ScoreFacts.model_validate(result)
    # Aggregate each event before date-block resampling. Multiple strikes are never
    # independent observations, and differently sized date blocks retain event weights.
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["target_date"]), str(row["event_id"])].append(row)
    blocks: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for (day, _), values in sorted(grouped.items()):
        losses = []
        for row in values:
            model_brier, model_log = _loss(
                float(row["probability_yes"]), int(row["outcome"]), policy.log_loss_clip
            )
            base_brier, base_log = _loss(
                float(row["baseline_probability"]), int(row["outcome"]), policy.log_loss_clip
            )
            losses.append((model_brier, base_brier - model_brier, base_log - model_log))
        blocks[day].append(tuple(float(np.mean([v[i] for v in losses])) for i in range(3)))  # type: ignore[arg-type]
    ordered = [blocks[day] for day in sorted(blocks)]
    generator = np.random.default_rng(policy.seed)
    estimates: list[list[float]] = [[], [], []]
    for _ in range(policy.bootstrap_samples):
        selected = [
            event
            for index in generator.integers(0, len(ordered), size=len(ordered))
            for event in ordered[int(index)]
        ]
        for index in range(3):
            estimates[index].append(float(np.mean([event[index] for event in selected])))
    scale = 10**policy.diagnostic_precision

    def interval(values: list[float]) -> dict[str, Any]:
        return {
            "lower": math.floor(float(np.quantile(values, 0.025)) * scale) / scale,
            "upper": math.ceil(float(np.quantile(values, 0.975)) * scale) / scale,
            "method": "fixed-seed whole-date block bootstrap with equal event weights",
            "date_blocks": len(dates),
            "nominal_coverage": policy.confidence,
        }

    result.update(
        status="evaluated",
        model_brier_interval=interval(estimates[0]),
        brier_skill_interval=interval(estimates[1]),
        log_loss_skill_interval=interval(estimates[2]),
        mean_brier_skill=_round(float(np.mean([v[1] for block in ordered for v in block])), policy),
    )
    return ScoreFacts.model_validate(result)


class _PinnedConnection(sqlite3.Connection):
    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        # prospective.report begins a read transaction. Assessment already pins the
        # same read-only snapshot; a nested BEGIN must leave that snapshot intact.
        if sql.strip().upper() == "BEGIN" and self.in_transaction:
            return self.cursor()
        return super().execute(sql, parameters)


class _EvidenceJobs(Jobs):
    def __init__(self, workspace: Path, db: sqlite3.Connection) -> None:
        self.root, self.path, self._snapshot = workspace, workspace / "jobs.sqlite", db

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        yield self._snapshot


def _assess(
    workspace: Path,
    monitor: dict[str, Any],
    *,
    clock: Clock,
    expected_data_kind: Literal["real", "synthetic"],
    policy: ReadinessPolicy,
) -> tuple[ReadinessFacts, list[dict[str, Any]]]:
    monitor = dict(monitor)
    for field in ("spec", "source_ref", "model_binding"):
        if isinstance(monitor.get(field), str):
            monitor[field] = json.loads(monitor[field])
    checks = []

    def check(name: str, reason: str, *, passed: bool, **details: Any) -> None:
        checks.append(EvidenceCheck(name=name, passed=bool(passed), reason=reason, details=details))

    mid = identifier(monitor["id"])
    checks_payload: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    prefix: list[dict[str, Any]] = []
    account: dict[str, Any] = {"status": "not_started"}
    prospective: dict[str, Any] = {"counts": {}, "selected_observations": []}
    evidence_as_of = datetime.fromisoformat(monitor["created_at"])
    source_refs: dict[str, Any] = {
        "spec_hash": monitor["spec_hash"],
        "deployment_key": monitor.get("deployment_key"),
    }
    try:
        from entropytrade.domain.strategy import StrategySpec

        verify_paper_origin(workspace, monitor)
        spec = StrategySpec.model_validate(monitor["spec"])
        binding = monitor["model_binding"]
        source_refs["data_kind"] = binding["snapshot"]["data_kind"]
        source_refs["historical_report_hash"] = monitor["source_ref"]["eligibility"][
            "source_hashes"
        ]["report"]
        source_refs["search_trials"] = (
            monitor["source_ref"]["eligibility"].get("validation_summary", {}).get("search_trials")
        )
        check(
            "authentic_provenance",
            "Evidence provenance must match the server's real-data policy",
            passed=binding["snapshot"]["data_kind"] == expected_data_kind,
        )
        model = verify_research_binding(spec, binding, data_kind=expected_data_kind)
        source_refs.update(
            model_hash=model.model_hash,
            binding_hash=binding["binding_hash"],
            feature_schema_hash=model.feature_schema_hash,
            paper_source_hash=monitor["source_ref"]["source_hash"],
            data_kind=model.data_kind,
        )
        check(
            "source_integrity",
            "Frozen research, portable model and paper origin verified",
            passed=True,
        )
        with closing(
            sqlite3.connect(
                (workspace / "jobs.sqlite").resolve().as_uri() + "?mode=ro",
                uri=True,
                factory=_PinnedConnection,
            )
        ) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("BEGIN")
            cycles = [
                dict(value)
                for value in db.execute(
                    "SELECT * FROM shadow_cycles WHERE monitor_id=? "
                    "AND status!='running' ORDER BY sequence",
                    (mid,),
                )
            ]
            if cycles:
                evidence_as_of = datetime.fromisoformat(cycles[-1]["finished_at"])
            if evidence_as_of > clock.now():
                raise ValueError("committed evidence clock exceeds current clock")
            prefix = [
                {key: item[key] for key in ("sequence", "status", "digest", "finished_at")}
                | {"cycle_id": item["id"]}
                for item in cycles
            ]
            check(
                "contiguous_prefix",
                "The committed paper prefix must be contiguous",
                passed=[c["sequence"] for c in cycles] == list(range(1, len(cycles) + 1)),
            )
            value = report(_EvidenceJobs(workspace, db), mid, as_of=evidence_as_of)
            integrity = [failure for failure in value["cycle_failures"] if failure.get("integrity")]
            check(
                "prospective_integrity",
                "Forward receipt/model/account evidence must verify without integrity failures",
                passed=not integrity and value["historical_validation"] is False,
            )
            cycle_by_id = {item["id"]: item for item in cycles}
            cache: dict[str, ExperimentData] = {}
            selected = []
            overdue = 0
            for observation in value["observations"]:
                cycle = cycle_by_id.get(observation["cycle_id"])
                original_contract = (
                    next(
                        (
                            item["market"]
                            for item in json.loads(cycle["result"])["contracts"]
                            if item["ticker"] == observation["ticker"]
                        ),
                        None,
                    )
                    if cycle is not None
                    else None
                )
                expected = (
                    settlement_expected(original_contract)[0]
                    if original_contract is not None
                    else datetime.fromisoformat(observation["close_time"])
                )
                if (
                    observation["status"] == "pending"
                    and expected + timedelta(seconds=policy.settlement_grace_seconds)
                    < evidence_as_of
                ):
                    overdue += 1
                if observation["status"] != "matched":
                    continue
                if (
                    observation["data_kind"] != expected_data_kind
                    or observation["prediction"]["model_hash"] != model.model_hash
                ):
                    raise ValueError("mixed provenance/model in forward observations")
                cid = observation["cycle_id"]
                if cid not in cycle_by_id:
                    raise ValueError("observation outside frozen prefix")
                if cid not in cache:
                    root = workspace / "shadow" / mid / identifier(cid)
                    cache[cid] = ExperimentData.model_validate(verified_inputs(root)["data"])
                sample = next(
                    sample
                    for sample in cache[cid].samples
                    if sample.ticker == observation["ticker"]
                    and sample.decision_time.isoformat() == observation["decision_time"]
                )
                canonical = (
                    model.series_locations[sample.family]["entity"]
                    + ":"
                    + sample.target_date.isoformat()
                )
                quote = None
                if (
                    sample.book
                    and sample.book.midpoint is not None
                    and sample.book.best_bid
                    and sample.book.best_ask
                    and sample.book.best_bid.price < sample.book.best_ask.price
                    and sample.book.received_at <= sample.decision_time
                    and (sample.decision_time - sample.book.received_at).total_seconds()
                    <= policy.max_quote_age_seconds
                    and (
                        sample.book.exchange_ts is None
                        or sample.book.exchange_ts <= sample.decision_time
                    )
                ):
                    quote = float(sample.book.midpoint)
                rows.append(
                    {
                        "event_id": canonical,
                        "target_date": observation["target_date"],
                        "ticker": sample.ticker,
                        "probability_yes": float(observation["prediction"]["probability_yes"]),
                        "baseline_probability": quote,
                        "outcome": int(observation["outcome"]["result"] == "yes"),
                    }
                )
                selected.append(
                    {
                        key: observation[key]
                        for key in (
                            "ticker",
                            "event_id",
                            "target_date",
                            "decision_time",
                            "cycle_id",
                            "feature_hash",
                        )
                    }
                )
            prospective = {
                "counts": value["counts"],
                "pending_overdue": overdue,
                "integrity_failures": integrity,
                "selected_observations": selected,
            }
            source_refs["prospective_projection_hash"] = scientific_hash(prospective)
            check(
                "settlement_coverage",
                "No overdue or refused outcome may be dropped from the evidence",
                passed=not overdue and not value["counts"]["refused"],
            )
            for cycle in reversed(cycles):
                if cycle["result"]:
                    decoded = json.loads(cycle["result"])
                    if decoded.get("paper"):
                        state = decoded["paper"]["state"]
                        if account_hash(state) != decoded["paper"]["state_hash"]:
                            raise ValueError("frozen paper account hash mismatch")
                        account = summary(state)
                        ledger = Ledger.load(state["ledger"])
                        account.update(
                            drawdown_at_cost=str(ledger.drawdown()),
                            open_positions=len(ledger.positions),
                        )
                        source_refs["account_state_hash"] = account_hash(state)
                        break
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, StopIteration) as exc:
        check(
            "verified_evidence",
            "Source, immutable paper prefix or forward evidence failed verification",
            passed=False,
            error_type=type(exc).__name__,
        )
    scores = proper_score_facts(rows, policy=policy)
    check(
        "independent_outcomes",
        "At least twenty independent forward events on ten dates are required",
        passed=scores.independent_events >= policy.min_events
        and scores.independent_dates >= policy.min_dates,
        events=scores.independent_events,
        dates=scores.independent_dates,
    )
    check(
        "quoted_baseline",
        "Every matched forecast requires a genuine decision-time two-sided quote",
        passed=bool(rows) and scores.quoted_observations == scores.observations,
    )
    lower = scores.brier_skill_interval["lower"] if scores.brier_skill_interval else None
    check(
        "positive_brier_skill",
        "The date-block lower Brier skill bound must exceed the declared meaningful margin",
        passed=lower is not None and lower > policy.minimum_brier_skill + policy.numerical_guard,
    )
    check(
        "paper_account",
        "A verified committed paper account is required; open positions remain valued at cost",
        passed=account.get("data_kind") == expected_data_kind,
    )
    checks_payload.update(
        policy=policy,
        evidence_as_of=evidence_as_of,
        monitor_id=mid,
        source_refs=source_refs,
        paper_prefix=prefix,
        account=account,
        prospective=prospective,
        scores=scores,
        checks=tuple(checks),
        eligible=all(item.passed for item in checks),
        submission_enabled=False,
    )
    facts = ReadinessFacts(**checks_payload, evidence_hash="")
    facts = facts.revalidated(
        evidence_hash=scientific_hash(facts.model_dump(mode="json", exclude={"evidence_hash"}))
    )
    return facts, rows


def assess_readiness(
    workspace: Path,
    monitor: dict[str, Any],
    *,
    clock: Clock,
    expected_data_kind: Literal["real", "synthetic"] = "real",
    policy: ReadinessPolicy | None = None,
) -> ReadinessFacts:
    return _assess(
        workspace,
        monitor,
        clock=clock,
        expected_data_kind=expected_data_kind,
        policy=policy or ReadinessPolicy(),
    )[0]


def assess_degradation(
    workspace: Path,
    monitor: dict[str, Any],
    *,
    clock: Clock,
    reference: ReadinessFacts,
    expected_data_kind: Literal["real", "synthetic"] = "real",
    policy: ReadinessPolicy | None = None,
) -> DegradationFacts:
    reference = verify_facts(reference)
    policy = policy or reference.policy
    current, rows = _assess(
        workspace, monitor, clock=clock, expected_data_kind=expected_data_kind, policy=policy
    )
    return degradation_from_observations(reference, current, rows, policy=policy)


def degradation_from_observations(
    reference: ReadinessFacts,
    current: ReadinessFacts,
    observations: Sequence[Mapping[str, Any]],
    *,
    policy: ReadinessPolicy | None = None,
) -> DegradationFacts:
    """Assess every nonoverlapping complete post-reference date block.

    An earlier bad block remains authoritative even after later good observations.
    Otherwise the latest completed block is stable (no significant deterioration),
    which is not a new skill claim or authorization. An incomplete tail cannot
    replace a completed block. Only a separately reviewed reference resets history.
    """
    reference, current = verify_facts(reference), verify_facts(current)
    policy = policy or reference.policy
    rows = [dict(value) for value in observations]
    safety = any(
        not item.passed
        and item.name
        in {
            "source_integrity",
            "verified_evidence",
            "contiguous_prefix",
            "prospective_integrity",
            "settlement_coverage",
        }
        for item in current.checks
    )
    safety = (
        safety
        or reference.monitor_id != current.monitor_id
        or policy != reference.policy
        or any(
            reference.source_refs.get(key) != current.source_refs.get(key)
            for key in (
                "spec_hash",
                "model_hash",
                "binding_hash",
                "feature_schema_hash",
                "deployment_key",
                "paper_source_hash",
                "historical_report_hash",
            )
        )
    )
    reference_days = [
        str(row["target_date"]) for row in reference.prospective.get("selected_observations", [])
    ]
    after = max(reference_days, default="9999-12-31")
    new = sorted(
        (row for row in rows if str(row["target_date"]) > after),
        key=lambda row: (str(row["target_date"]), str(row["event_id"]), str(row["ticker"])),
    )
    window: list[dict[str, Any]] = []
    completed: list[tuple[list[dict[str, Any]], ScoreFacts]] = []
    missing_quotes = False
    for day in sorted({str(row["target_date"]) for row in new}):
        window.extend(row for row in new if row["target_date"] == day)
        if (
            len({r["event_id"] for r in window}) >= policy.min_events
            and len({r["target_date"] for r in window}) >= policy.min_dates
        ):
            score = proper_score_facts(window, policy=policy)
            missing_quotes = missing_quotes or score.status != "evaluated"
            completed.append((window, score))
            window = []
    chosen = completed[-1] if completed else (window, proper_score_facts(window, policy=policy))
    for candidate in completed:
        interval = candidate[1].brier_skill_interval
        if interval and interval["upper"] < -policy.minimum_brier_skill - policy.numerical_guard:
            chosen = candidate
            break
    window, scores = chosen
    signals = []
    status: Literal["pending", "stable", "degraded", "blocked"] = "pending"
    window_id = scientific_hash(window) if scores.status == "evaluated" else None
    if safety or missing_quotes:
        status = "blocked"
        signals.append(
            {
                "kind": "evidence_integrity",
                "severity": "critical",
                "recommended_action": "suspend",
                "reason": "A complete date block lacks verified quoted-baseline coverage"
                if missing_quotes
                else "Frozen source or prospective coverage failed verification",
                "evidence_refs": [current.evidence_hash],
            }
        )
    elif scores.brier_skill_interval:
        upper = scores.brier_skill_interval["upper"]
        if upper < -policy.minimum_brier_skill - policy.numerical_guard:
            status = "degraded"
            signals.append(
                {
                    "kind": "forecast_degradation",
                    "severity": "warning",
                    "recommended_action": "suspend_and_investigate",
                    "reason": "A new independent window is worse than genuine quoted probabilities",
                    "evidence_refs": [current.evidence_hash, *([window_id] if window_id else [])],
                }
            )
        else:
            status = "stable"
    return DegradationFacts(
        status=status,
        reference_hash=reference.evidence_hash,
        evidence_hash=current.evidence_hash,
        window_id=window_id,
        signals=tuple(signals),
        scores=scores,
        investigation_objective="Investigate deterioration using verified paper evidence"
        if signals
        else None,
    )
