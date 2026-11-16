"""Evidence-backed, owner-reviewed readiness records. There is no activation method."""

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from entropytrade.api.jobs import identifier
from entropytrade.api.owner import OwnerAuthError, OwnerPrincipal
from entropytrade.domain.runs import CapitalEnvelope
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore, select_fee
from entropytrade.features.registry import scientific_hash
from entropytrade.research.readiness_evidence import (
    ReadinessFacts,
    ReadinessPolicy,
    assess_degradation,
    assess_readiness,
    verify_facts,
    verify_frozen_evidence,
)
from entropytrade.research.store import reject_collector_chain
from entropytrade.tracking import alerts
from entropytrade.tracking.evaluate import shadow_limits
from entropytrade.tracking.readiness_store import ReadinessStore, enabled

if TYPE_CHECKING:
    from entropytrade.research.service import ResearchService
    from entropytrade.tracking.store import TrackingStore

POLICY = "readiness-review-v1"
MONITOR_RECHECK_SECONDS = 60
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
MONEY = re.compile(r"(?:0|[1-9][0-9]{0,3})(?:\.[0-9]{1,2})?\Z")


class ReadinessEligibilityError(ValueError):
    def __init__(self, checks: dict[str, Any]) -> None:
        super().__init__("Current evidence does not satisfy readiness review gates")
        self.checks = checks


class ReadinessConflictError(ValueError):
    """Current state changed after a reviewable proposal was prepared."""


@dataclass(frozen=True)
class PreparedReview:
    proposal_id: str
    decision: str
    revision: int
    epoch: int
    guard: dict[str, Any]
    note: str
    source_fingerprint: str
    material_refs: dict[str, Any]
    evidence_as_of: str


def proposal_identifier(value: object) -> str:
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        raise ValueError("invalid readiness proposal ID")
    return value


def _money(value: object, *, minimum: str, maximum: str) -> Decimal:
    if not isinstance(value, str) or MONEY.fullmatch(value) is None:
        raise ValueError("proposed money must be decimal text with at most two fractional digits")
    amount = Decimal(value)
    if not Decimal(minimum) <= amount <= Decimal(maximum):
        raise ValueError("proposed amount exceeds the fixed readiness bounds")
    return amount.quantize(Decimal("0.01"))


def _note(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        raise ValueError("provide a review reason containing 1-1000 characters")
    return value.strip()


class ResearchReadinessService:
    def __init__(
        self,
        workspace: Path,
        tracking: "TrackingStore",
        research: "ResearchService | None" = None,
        *,
        clock: Clock | None = None,
        expected_data_kind: Literal["real", "synthetic"] = "real",
    ) -> None:
        self.workspace, self.tracking, self.research = workspace, tracking, research
        self._guard_workspace()
        self.clock = clock or SystemClock()
        self.expected_data_kind = expected_data_kind  # internal controlled fixtures only
        self.store = ReadinessStore(tracking.jobs, clock=self.clock)
        self.evidence_policy = ReadinessPolicy()
        self._monitor_lock = threading.RLock()
        self._evaluations: dict[str, tuple[str, dict[str, Any]]] = {}
        self._evaluation_times: dict[str, float] = {}
        self._monitor_cursor = 0

    def _guard_workspace(self) -> None:
        reject_collector_chain(self.workspace)
        reject_collector_chain(self.tracking.jobs.root)
        if self.workspace.resolve() != self.tracking.jobs.root.resolve():
            raise ValueError("readiness and paper stores must share a workspace")

    def _monitor(self, monitor_id: str) -> dict[str, Any]:
        """Read source metadata even when invalid, so a refusal remains inspectable."""
        with self.tracking.jobs.connect() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT * FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                raise KeyError("paper deployment not found")
            monitor = dict(row)
            for key in ("spec", "model_binding", "source_ref"):
                monitor[key] = json.loads(monitor[key]) if monitor[key] else None
            monitor["events"] = [
                dict(item)
                for item in db.execute(
                    "SELECT at,action FROM shadow_events WHERE monitor_id=? ORDER BY sequence",
                    (monitor_id,),
                )
            ]
        return monitor

    def _build(
        self,
        monitor_id: str,
        capital: Decimal,
        loss: Decimal,
        *,
        rollback: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], ReadinessFacts]:
        self._guard_workspace()
        with self.tracking.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            alerts.refresh(db, self.clock.now().isoformat())
        # Pin the current commit/account/alert state before evidence I/O; publication and
        # review CAS it again. A normal new cycle can refresh this guard without changing
        # the immutable proposal's model, policy or already verified evidence prefix.
        control = self.store.status()
        guard = self.store.snapshot_guard(monitor_id)
        monitor = self._monitor(monitor_id)
        facts = assess_readiness(
            self.workspace,
            monitor,
            clock=self.clock,
            expected_data_kind=self.expected_data_kind,
            policy=self.evidence_policy,
        )
        checks = [item.model_dump(mode="json") for item in facts.checks]

        def check(name: str, reason: str, *, passed: bool) -> None:
            checks.append({"name": name, "passed": bool(passed), "reason": reason})

        proposed = shadow_limits().revalidated(
            bankroll=capital,
            per_trade=min(Decimal("5"), capital),
            per_event=min(Decimal("25"), capital),
            total_deployed=min(Decimal("50"), capital),
            max_loss=loss,
            max_drawdown=loss,
            max_open_orders=10,
            config_version="readiness-proposed-v1",
        )
        envelope = CapitalEnvelope(max_dollars=capital, max_contracts=Decimal("100"))
        check(
            "paper_active",
            "The reviewed paper deployment must be active",
            passed=monitor["status"] == "active",
        )
        check(
            "workspace_enabled",
            "The workspace halt must be cleared by its owner",
            passed=not control["halted"],
        )
        check(
            "operational_health",
            "Open operational incidents require investigation",
            passed=not guard["alerts"],
        )
        selected: dict[str, str | None] = {}
        try:
            spec = StrategySpec.model_validate(monitor["spec"])
            fees = FeeEvidenceStore(self.workspace).snapshot()
            for series in spec.market_universe.series_tickers:
                policy, audit = select_fee(
                    fees, series=series, when=self.clock.now(), data_kind=self.expected_data_kind
                )
                selected[series] = audit["version"]
                check(
                    "current_fees:" + series,
                    "A unique current certified fee policy is required",
                    passed=policy is not None,
                )
        except (ValueError, OSError, KeyError, TypeError):
            check("current_fees", "Current strategy and fee evidence must verify", passed=False)
        account = facts.account
        at_cost_loss = max(
            Decimal(0),
            Decimal(str(account.get("starting_cash", "0")))
            - Decimal(str(account.get("equity_at_cost", "0"))),
        )
        exposure = sum(
            (Decimal(str(item["total_cost"])) for item in account.get("positions", [])),
            Decimal(0),
        )
        check(
            "loss_limits_at_cost",
            "Current at-cost loss and drawdown must fit the proposed loss limits",
            passed=account.get("status") == "simulated"
            and at_cost_loss <= loss
            and Decimal(str(account.get("drawdown_at_cost", "Infinity"))) <= loss,
        )
        check(
            "exposure_at_cost",
            "Current positions at cost must fit the proposed exposure envelope",
            passed=account.get("status") == "simulated" and exposure <= proposed.total_deployed,
        )
        material = {
            "policy": POLICY,
            "evidence_policy": self.evidence_policy.model_dump(mode="json"),
            "spec_hash": monitor["spec_hash"],
            "binding_hash": (monitor["model_binding"] or {}).get("binding_hash"),
            "source_hash": (monitor["source_ref"] or {}).get("source_hash"),
            "deployment_key": monitor.get("deployment_key"),
            "monitor_events_hash": guard.get("monitor_events_hash"),
            "fee_versions": selected,
            "paper_risk_limits": shadow_limits().model_dump(mode="json"),
            "proposed_limits": proposed.model_dump(mode="json"),
            "capital_envelope": envelope.model_dump(mode="json"),
            "control_epoch": control["epoch"],
        }
        payload = {
            "schema_version": "readiness-proposal-v1",
            "policy_hash": scientific_hash(
                {"review": POLICY, "evidence": facts.policy.model_dump(mode="json")}
            ),
            "monitor_id": monitor_id,
            "control_epoch": control["epoch"],
            "source_fingerprint": scientific_hash(material),
            "facts": facts.model_dump(mode="json"),
            "capital_envelope": envelope.model_dump(mode="json"),
            "risk_limits": proposed.model_dump(mode="json"),
            "material_refs": material,
            "checks": checks,
            "reasons": [item["reason"] for item in checks if not item["passed"]],
            "eligible": all(item["passed"] for item in checks),
            "execution_authorized": False,
            "submission_enabled": False,
            "scope": (
                "Future readiness review only; proposed capital is not allocated. "
                "No live activation or orders."
            ),
        }
        if rollback is not None:
            payload["rollback"] = rollback
        return payload, guard, facts

    def proposals(self, monitor_id: str) -> dict[str, Any]:
        payload, _, _ = self._build(monitor_id, Decimal("100.00"), Decimal("10.00"))
        return {
            "monitor_id": monitor_id,
            "preview": {**payload, "proposal_hash": scientific_hash(payload)},
            "proposals": self.store.listing(monitor_id),
            "control": self.store.status(),
            "submission_enabled": False,
        }

    def create(self, monitor_id: str, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {"capital_dollars", "max_loss_dollars"}:
            raise ValueError("provide capital_dollars and max_loss_dollars only")
        capital = _money(value["capital_dollars"], minimum="10", maximum="1000")
        loss = _money(
            value["max_loss_dollars"], minimum="0.01", maximum=str(min(capital, Decimal("50")))
        )
        payload, guard, _ = self._build(monitor_id, capital, loss)
        try:
            record = self.store.publish(
                payload,
                monitor_id=monitor_id,
                source_fingerprint=payload["source_fingerprint"],
                guard=guard,
            )
        except ValueError as exc:
            raise ReadinessConflictError(str(exc)) from exc
        return {"id": record["id"], "proposal": record, "submission_enabled": False}

    def detail(self, proposal_id: str) -> dict[str, Any]:
        record = self.store.get(proposal_identifier(proposal_id))
        if record is None:
            raise KeyError("readiness proposal not found")
        payload = record["payload"]
        frozen = verify_facts(payload["facts"])
        frozen_valid = True
        try:
            verify_frozen_evidence(self.workspace, self._monitor(record["monitor_id"]), frozen)
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
            frozen_valid = False
        current, guard, facts = self._build(
            record["monitor_id"],
            Decimal(payload["capital_envelope"]["max_dollars"]),
            Decimal(payload["risk_limits"]["max_loss"]),
        )
        checks = list(current["checks"])
        same_material = current["source_fingerprint"] == record["source_fingerprint"]
        prefix_valid = frozen_valid and list(
            facts.paper_prefix[: len(frozen.paper_prefix)]
        ) == list(frozen.paper_prefix)
        checks.extend(
            [
                {
                    "name": "unchanged_material_refs",
                    "passed": same_material,
                    "reason": (
                        "Model, strategy, source, fees, risk policy, governance and "
                        "control epoch must remain unchanged"
                    ),
                },
                {
                    "name": "immutable_paper_prefix",
                    "passed": prefix_valid,
                    "reason": "The reviewed paper evidence prefix must remain intact",
                },
            ]
        )
        if not same_material or not prefix_valid:
            record = self.store.invalidate(
                proposal_id, "Material source, policy or reviewed prefix changed"
            )
        return {
            **record,
            "current_checks": {
                "eligible": all(item["passed"] for item in checks),
                "checks": checks,
                "reasons": [item["reason"] for item in checks if not item["passed"]],
                "observed_guard_hash": scientific_hash(guard),
            },
            "current_guard": guard,
            "submission_enabled": False,
        }

    def prepare_review(self, proposal_id: str, value: object) -> PreparedReview:
        if not isinstance(value, dict) or set(value) != {"decision", "expected_revision", "note"}:
            raise ValueError("provide decision, expected_revision and note only")
        if (
            not isinstance(value["decision"], str)
            or value["decision"] not in {"approve", "reject"}
            or type(value["expected_revision"]) is not int
        ):
            raise ValueError("select approve/reject and an exact revision")
        note = _note(value["note"])
        if value["decision"] == "approve":
            existing = self.store.get(proposal_identifier(proposal_id))
            if existing is None:
                raise KeyError("readiness proposal not found")
            self.monitoring(existing["monitor_id"])
        record = self.detail(proposal_id)
        if value["decision"] == "approve" and not record["current_checks"]["eligible"]:
            raise ReadinessEligibilityError(record["current_checks"])
        return PreparedReview(
            proposal_id,
            value["decision"],
            value["expected_revision"],
            record["payload"]["control_epoch"],
            record["current_guard"],
            note,
            record["source_fingerprint"],
            record["payload"]["material_refs"],
            record["payload"]["facts"]["evidence_as_of"],
        )

    def commit_review(self, prepared: PreparedReview, principal: OwnerPrincipal) -> dict[str, Any]:
        if not isinstance(principal, OwnerPrincipal):
            raise OwnerAuthError("an authenticated owner session is required")

        def before_commit() -> None:
            principal.require_current()
            if prepared.decision != "approve":
                return
            refs = prepared.material_refs
            if (
                refs["policy"] != POLICY
                or refs["paper_risk_limits"] != shadow_limits().model_dump(mode="json")
                or datetime.fromisoformat(prepared.evidence_as_of) > self.clock.now()
            ):
                raise ReadinessConflictError("Risk policy or evidence clock changed before commit")
            fees = FeeEvidenceStore(self.workspace).snapshot()
            for series, version in refs["fee_versions"].items():
                policy, audit = select_fee(
                    fees, series=series, when=self.clock.now(), data_kind=self.expected_data_kind
                )
                if policy is None or audit["version"] != version:
                    raise ReadinessConflictError(
                        "Current certified fee evidence changed before commit"
                    )
            principal.require_current()

        try:
            result = self.store.review(
                prepared.proposal_id,
                decision=prepared.decision,
                expected_revision=prepared.revision,
                expected_epoch=prepared.epoch,
                expected_guard=prepared.guard,
                expected_source_fingerprint=prepared.source_fingerprint,
                actor=principal.actor(),
                reason=prepared.note,
                before_commit=before_commit,
            )
        except OwnerAuthError:
            raise
        except ValueError as exc:
            raise ReadinessConflictError(str(exc)) from exc
        return {**result, "submission_enabled": False}

    def revoke(self, proposal_id: str, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {"reason"}:
            raise ValueError("provide a revocation reason only")
        return self.store.invalidate(
            proposal_identifier(proposal_id), _note(value["reason"]), revoke=True
        )

    def rollback(
        self, proposal_id: str, value: object, principal: OwnerPrincipal
    ) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {"target_proposal_id", "reason"}:
            raise ValueError("select a prior proposal and a rollback reason only")
        principal.require_current()
        target = self.store.get(proposal_identifier(value["target_proposal_id"]))
        source = self.store.get(proposal_identifier(proposal_id))
        if target is None or source is None or target["monitor_id"] != source["monitor_id"]:
            raise ValueError("rollback requires a prior review of the same deployment")
        if target["created_at"] > source["created_at"] or target["id"] == source["id"]:
            raise ValueError("rollback requires an earlier distinct proposal")
        reason = _note(value["reason"])
        payload, guard, _ = self._build(
            source["monitor_id"],
            Decimal(target["payload"]["capital_envelope"]["max_dollars"]),
            Decimal(target["payload"]["risk_limits"]["max_loss"]),
            rollback={"from": proposal_id, "target": target["id"], "reason": reason},
        )
        principal.require_current()
        created = self.store.publish(
            payload,
            monitor_id=source["monitor_id"],
            source_fingerprint=payload["source_fingerprint"],
            guard=guard,
            before_commit=principal.require_current,
        )
        self.store.invalidate(
            proposal_id,
            reason,
            actor=principal.actor(),
            revoke=True,
            before_commit=principal.require_current,
        )
        return {"id": created["id"], "proposal": created, "submission_enabled": False}

    def monitoring(self, monitor_id: str) -> dict[str, Any]:
        self._guard_workspace()
        with self._monitor_lock:
            try:
                return self._evaluate_monitor(monitor_id)
            except ReadinessConflictError:
                raise
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                return self._monitor_failure(monitor_id, type(exc).__name__)

    def _incident_history(self, monitor_id: str) -> list[dict[str, Any]]:
        with self.tracking.jobs.connect() as db:
            return alerts.history(db, identifier(monitor_id))

    def _monitor_failure(self, monitor_id: str, error_type: str) -> dict[str, Any]:
        self._guard_workspace()
        signal = {
            "kind": "readiness_integrity",
            "severity": "critical",
            "recommended_action": "suspend",
            "reason": "Current source, evidence or monitoring state failed verification",
        }
        with self.tracking.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status,source_kind FROM monitors WHERE id=?", (identifier(monitor_id),)
            ).fetchone()
            if row is None:
                raise KeyError("paper deployment not found")
            alerts.observe_condition(
                db,
                monitor_id,
                "readiness_integrity",
                active=True,
                evidence={"error_type": error_type, "signals": [signal]},
                now=self.clock.now().isoformat(),
            )
            suspend = row["source_kind"] == "autonomous_research" and row["status"] in {
                "active",
                "paused",
            }
        if suspend:
            self.tracking.control(monitor_id, "suspend")
        result = {
            "monitor_id": monitor_id,
            "evaluation": {
                "status": "blocked",
                "evidence_as_of": None,
                "checks": [],
                "signals": [signal],
            },
            "incidents": self._incident_history(monitor_id),
            "investigations": self._investigations(monitor_id),
            "submission_enabled": False,
        }
        self._evaluations[monitor_id] = ("error:" + error_type, result)
        self._evaluation_times[monitor_id] = self.clock.now().timestamp()
        return result

    def _investigations(self, monitor_id: str) -> list[dict[str, Any]]:
        with self.tracking.jobs.connect() as db:
            if not enabled(db):
                return []
            return [
                {
                    **dict(row),
                    "status": "linked" if row["research_job_id"] else "pending",
                    "budget": {"ai_usd": "0"},
                }
                for row in db.execute(
                    "SELECT * FROM readiness_investigations WHERE monitor_id=? "
                    "ORDER BY created_at,id",
                    (monitor_id,),
                )
            ]

    def _evaluate_monitor(self, monitor_id: str) -> dict[str, Any]:
        monitor = self._monitor(monitor_id)
        records = self.store.listing(monitor_id)
        reviewed = [
            row
            for row in records
            if any(event["action"] == "approved" for event in row["events"])
            and row["payload"]["facts"]["source_refs"].get("spec_hash") == monitor["spec_hash"]
            and row["payload"]["facts"]["source_refs"].get("binding_hash")
            == (monitor["model_binding"] or {}).get("binding_hash")
        ]
        reviewed.sort(
            key=lambda row: max(
                event["sequence"] for event in row["events"] if event["action"] == "approved"
            ),
            reverse=True,
        )
        approved = reviewed[0] if reviewed else None
        capital, loss = (
            (
                Decimal(approved["payload"]["capital_envelope"]["max_dollars"]),
                Decimal(approved["payload"]["risk_limits"]["max_loss"]),
            )
            if approved
            else (Decimal("100.00"), Decimal("10.00"))
        )
        payload, guard, facts = self._build(monitor_id, capital, loss)
        reference = None
        references = reviewed + [row for row in records if row not in reviewed]
        for record in references:
            previous = verify_facts(record["payload"]["facts"])
            if previous.eligible and all(
                previous.source_refs.get(key) == facts.source_refs.get(key)
                for key in (
                    "spec_hash",
                    "model_hash",
                    "binding_hash",
                    "feature_schema_hash",
                    "deployment_key",
                )
            ):
                reference = previous
                break
        # Freeze one scientific monitoring reference automatically. It is a proposal,
        # never an approval; even blocked operational/capital checks remain visible.
        if (
            reference is None
            and facts.eligible
            and monitor.get("source_kind") == "autonomous_research"
        ):
            try:
                self.store.publish(
                    payload,
                    monitor_id=monitor_id,
                    source_fingerprint=payload["source_fingerprint"],
                    guard=guard,
                )
            except ValueError as exc:
                if self.store.snapshot_guard(monitor_id) != guard:
                    raise ReadinessConflictError(
                        "Paper evidence advanced during monitoring; retry"
                    ) from exc
                raise
            reference = facts
        signals: list[dict[str, Any]] = []
        state = "pending"
        window_id = None
        if reference is not None:
            degraded = assess_degradation(
                self.workspace,
                monitor,
                clock=self.clock,
                reference=reference,
                expected_data_kind=self.expected_data_kind,
                policy=self.evidence_policy,
            )
            state, window_id = degraded.status, degraded.window_id
            signals = [dict(signal) for signal in degraded.signals]
            for signal in signals:
                if signal["kind"] == "evidence_integrity":
                    signal["kind"] = "readiness_integrity"
        else:
            integrity = [
                item
                for item in facts.checks
                if not item.passed
                and item.name
                in {
                    "source_integrity",
                    "verified_evidence",
                    "prospective_integrity",
                    "contiguous_prefix",
                }
            ]
            if integrity and monitor.get("source_kind") == "autonomous_research":
                state = "blocked"
                signals.append(
                    {
                        "kind": "readiness_integrity",
                        "severity": "critical",
                        "recommended_action": "suspend",
                        "reason": (
                            "Frozen source or prospective receipt integrity failed verification"
                        ),
                        "evidence_refs": [facts.evidence_hash],
                    }
                )
        risk = [
            item
            for item in payload["checks"]
            if item["name"] in {"loss_limits_at_cost", "exposure_at_cost"} and not item["passed"]
        ]
        risk_breach = bool(risk) and facts.account.get("status") == "simulated"
        if risk_breach:
            signals.append(
                {
                    "kind": "risk_limit_breach",
                    "severity": "critical",
                    "recommended_action": "suspend",
                    "reason": (
                        "Verified at-cost loss, drawdown or exposure exceeds the "
                        "proposed readiness bounds"
                    ),
                    "evidence_refs": [facts.source_refs.get("account_state_hash")],
                }
            )
            state = "degraded"
        now = self.clock.now().isoformat()
        evidence = {
            "policy_hash": payload["policy_hash"],
            "facts_hash": facts.evidence_hash,
            "window_id": window_id,
            "signals": signals,
        }
        if self.store.snapshot_guard(monitor_id) != guard:
            raise ReadinessConflictError("Paper evidence advanced during monitoring; retry")
        active = {str(signal["kind"]) for signal in signals}
        with self.tracking.jobs.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for kind in alerts.READINESS_KINDS:
                condition: bool | None = kind in active
                if (
                    kind == "forecast_degradation"
                    and state in {"pending", "blocked"}
                    and kind not in active
                ):
                    condition = None  # unavailable/incomplete labels cannot resolve an episode
                alerts.observe_condition(
                    db, monitor_id, kind, active=condition, evidence=evidence, now=now
                )
        if any(
            signal["recommended_action"] in {"suspend", "suspend_and_investigate"}
            for signal in signals
        ) and monitor["status"] in {"active", "paused"}:
            self.tracking.control(monitor_id, "suspend")
        own_incidents = self._incident_history(monitor_id)
        if self.research is not None and monitor.get("source_kind") == "autonomous_research":
            from entropytrade.research.investigations import enqueue_investigation

            for incident in own_incidents:
                if incident["resolved_at"] is not None:
                    continue
                try:
                    enqueue_investigation(
                        self.research,
                        self.store,
                        monitor,
                        incident["id"],
                        policy_hash=payload["policy_hash"],
                        objective="Inspect the retained "
                        + incident["kind"]
                        + " episode using frozen model, strategy and receipt references. "
                        "This is a bounded offline diagnostic, never a trading approval.",
                    )
                except (ValueError, OSError, KeyError, sqlite3.Error):
                    # Preserve a pending durable outbox even when corrupt scope or a full
                    # research queue prevents a safe destination; never broaden scope.
                    self.store.investigate(monitor_id, incident["id"], payload["policy_hash"])
        result = {
            "monitor_id": monitor_id,
            "evaluation": {
                "status": state,
                "evidence_as_of": facts.evidence_as_of.isoformat(),
                "evidence_hash": facts.evidence_hash,
                "window_id": window_id,
                "checks": payload["checks"],
                "signals": signals,
                "reference_review_id": approved["id"] if approved else None,
                "reference_review_status": approved["status"] if approved else None,
            },
            "incidents": own_incidents,
            "investigations": self._investigations(monitor_id),
            "submission_enabled": False,
        }
        self._evaluations[monitor_id] = (
            scientific_hash(self.store.snapshot_guard(monitor_id)),
            result,
        )
        self._evaluation_times[monitor_id] = self.clock.now().timestamp()
        return result

    def refresh_monitoring(self) -> None:
        """Existing runner callback: assess at most one changed deployment per check."""
        self._guard_workspace()
        if not self._monitor_lock.acquire(blocking=False):
            return
        try:
            now = self.clock.now()
            with self.tracking.jobs.connect() as db:
                # Reserve capacity for approaching trained points. A short legacy polling
                # interval must not suppress all background research monitoring forever.
                from datetime import timedelta

                if db.execute(
                    "SELECT 1 FROM monitors WHERE status='active' "
                    "AND source_kind='autonomous_research' AND next_at<=? LIMIT 1",
                    ((now + timedelta(seconds=240)).isoformat(),),
                ).fetchone():
                    return
                monitors = [
                    row[0]
                    for row in db.execute(
                        "SELECT id FROM monitors WHERE source_kind='autonomous_research' "
                        "ORDER BY id"
                    )
                ]
            count = len(monitors)
            ordered = monitors[self._monitor_cursor :] + monitors[: self._monitor_cursor]
            for offset, monitor_id in enumerate(ordered):
                age = now.timestamp() - self._evaluation_times.get(monitor_id, float("-inf"))
                try:
                    key = scientific_hash(self.store.snapshot_guard(monitor_id))
                    age = now.timestamp() - self._evaluation_times.get(monitor_id, float("-inf"))
                    if (
                        monitor_id not in self._evaluations
                        or self._evaluations[monitor_id][0] != key
                        or not 0 <= age < MONITOR_RECHECK_SECONDS
                    ):
                        self._monitor_cursor = (self._monitor_cursor + offset + 1) % count
                        self._evaluate_monitor(monitor_id)
                        break
                except ReadinessConflictError:
                    break  # ordinary concurrent progress is a retry, not corrupt evidence
                except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    if (
                        self._evaluations.get(monitor_id, (None,))[0]
                        == "error:" + type(exc).__name__
                        and 0 <= age < MONITOR_RECHECK_SECONDS
                    ):
                        continue
                    self._monitor_cursor = (self._monitor_cursor + offset + 1) % count
                    self._monitor_failure(monitor_id, type(exc).__name__)
                    break
        finally:
            self._monitor_lock.release()
