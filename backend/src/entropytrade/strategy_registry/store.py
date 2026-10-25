"""SQLite lineage for strategy specs. Re-inserting a hash does not create a version."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.agents.pipeline import PipelineResult
from entropytrade.domain.enums import ActorKind
from entropytrade.domain.lifecycle import (
    Actor,
    HumanApproval,
    LifecycleState,
    LifecycleTransition,
)
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import ensure_utc

_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_experiments (
    experiment_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
    trials INTEGER NOT NULL, data_kind TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS agent_hypotheses (
    signature TEXT NOT NULL, run_id TEXT NOT NULL, PRIMARY KEY(signature, run_id));
CREATE TABLE IF NOT EXISTS agent_research_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS probability_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS probability_models (model_hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS probability_predictions (
    prediction_id TEXT PRIMARY KEY, model_hash TEXT NOT NULL, event_id TEXT NOT NULL,
    decision_time TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS specs (
    spec_hash TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    parent_hash TEXT,
    hypothesis TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE (strategy_id, version)
);
CREATE TABLE IF NOT EXISTS states (
    strategy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    state TEXT NOT NULL,
    PRIMARY KEY (strategy_id, version)
);
CREATE TABLE IF NOT EXISTS verdicts (
    spec_hash TEXT PRIMARY KEY,
    accepted INTEGER NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backtests (
    spec_hash TEXT PRIMARY KEY,
    digest TEXT NOT NULL,
    ending_equity TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transitions (
    transition_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload TEXT NOT NULL
);
"""


class RegistryError(ValueError):
    """The registry refused a write that would break lineage or promotion."""


@dataclass(frozen=True)
class RegistryRow:
    strategy_id: str
    version: int
    spec_hash: str
    hypothesis: str
    state: str
    verdict: str
    reason: str
    ending_equity: str
    digest: str


class Registry:
    """One SQLite file. Specs are immutable. State moves only through transitions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def record_experiment(
        self, experiment_id: str, payload: str, trials: int, data_kind: str
    ) -> None:
        with self._db:
            previous = self._db.execute(
                "SELECT payload FROM strategy_experiments WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
            if previous is not None and previous[0] != payload:
                raise RegistryError("experiment identity reused with different content")
            self._db.execute(
                "INSERT OR IGNORE INTO strategy_experiments VALUES (?, ?, ?, ?)",
                (experiment_id, payload, trials, data_kind),
            )

    def experiment_trials(self, data_kind: str) -> int:
        return int(
            self._db.execute(
                "SELECT COALESCE(SUM(trials),0) FROM strategy_experiments WHERE data_kind=?",
                (data_kind,),
            ).fetchone()[0]
        )

    def agent_run(self, run_id: str) -> str | None:
        row = self._db.execute(
            "SELECT payload FROM agent_research_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return None if row is None else str(row[0])

    def hypothesis_count(self, signature: str) -> int:
        return int(
            self._db.execute(
                "SELECT COUNT(*) FROM agent_hypotheses WHERE signature=?", (signature,)
            ).fetchone()[0]
        )

    def record_agent_run(self, run_id: str, payload: str) -> None:
        """Completed and failed operational research attempts are immutable."""
        import json

        from entropytrade.agents.validation import hypothesis_signature

        with self._db:
            previous = self._db.execute(
                "SELECT payload FROM agent_research_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if previous is not None and previous[0] != payload:
                raise RegistryError("research run identity reused with different content")
            self._db.execute(
                "INSERT OR IGNORE INTO agent_research_runs VALUES (?, ?)", (run_id, payload)
            )
            for hypothesis in json.loads(payload).get("hypotheses", []):
                signature = hypothesis_signature(
                    hypothesis["mechanism"], tuple(hypothesis["variables"])
                )
                self._db.execute(
                    "INSERT OR IGNORE INTO agent_hypotheses VALUES (?, ?)", (signature, run_id)
                )

    def record_probability_run(
        self,
        run_id: str,
        payload: str,
        models: dict[str, str],
        predictions: list[dict[str, object]],
    ) -> None:
        import json

        with self._db:
            old = self._db.execute(
                "SELECT payload FROM probability_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if old is not None and old[0] != payload:
                raise RegistryError("probability run identity reused with different content")
            self._db.execute(
                "INSERT OR IGNORE INTO probability_runs VALUES (?, ?)", (run_id, payload)
            )
            for digest, model_payload in models.items():
                self._db.execute(
                    "INSERT OR IGNORE INTO probability_models VALUES (?, ?)",
                    (digest, model_payload),
                )
            for record in predictions:
                self._db.execute(
                    "INSERT OR IGNORE INTO probability_predictions VALUES (?, ?, ?, ?, ?)",
                    (
                        record["prediction_id"],
                        record["model_hash"],
                        record["event_id"],
                        record["decision_time"],
                        json.dumps(record, sort_keys=True),
                    ),
                )

    def register(self, spec: StrategySpec, *, parent_hash: str | None = None) -> str:
        """Insert ``spec`` once. A second call with the same hash is a no-op."""
        digest = spec.spec_hash()
        if self._spec_exists(digest):
            return digest
        if spec.version == 1 and parent_hash is not None:
            raise RegistryError("version 1 has no parent")
        if spec.version > 1 and parent_hash is None:
            raise RegistryError("versions after 1 must name their parent spec")
        if parent_hash is not None and not self._spec_exists(parent_hash):
            raise RegistryError("parent spec is not in the registry")
        try:
            self._db.execute(
                """
                INSERT INTO specs
                    (spec_hash, strategy_id, version, parent_hash, hypothesis, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    digest,
                    spec.strategy_id,
                    spec.version,
                    parent_hash,
                    spec.hypothesis,
                    spec.model_dump_json(),
                ),
            )
            self._db.execute(
                """
                INSERT INTO states (strategy_id, version, state) VALUES (?, ?, ?)
                """,
                (spec.strategy_id, spec.version, LifecycleState.DRAFT.value),
            )
            self._db.commit()
        except sqlite3.IntegrityError as exc:
            self._db.rollback()
            raise RegistryError("strategy version already exists") from exc
        return digest

    def state(self, strategy_id: str, version: int) -> LifecycleState:
        row = self._db.execute(
            "SELECT state FROM states WHERE strategy_id = ? AND version = ?",
            (strategy_id, version),
        ).fetchone()
        if row is None:
            raise RegistryError(f"no state for {strategy_id} version {version}")
        return LifecycleState(row[0])

    def apply(self, transition: LifecycleTransition) -> None:
        """Persist a transition the domain model has already accepted."""
        current = self.state(transition.strategy_id, transition.strategy_version)
        if current is not transition.from_state:
            message = f"current state is {current}, not {transition.from_state}"
            raise RegistryError(message)
        self._db.execute(
            """
            INSERT INTO transitions (transition_id, strategy_id, version, payload)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(transition.transition_id),
                transition.strategy_id,
                transition.strategy_version,
                transition.model_dump_json(),
            ),
        )
        self._db.execute(
            """
            UPDATE states SET state = ? WHERE strategy_id = ? AND version = ?
            """,
            (transition.to_state.value, transition.strategy_id, transition.strategy_version),
        )
        self._db.commit()

    def record_research(
        self,
        result: PipelineResult,
        specs: tuple[StrategySpec, ...],
        *,
        now: datetime,
    ) -> None:
        """Store one pipeline result. Running it twice does not add versions."""
        by_id = {spec.strategy_id: spec for spec in specs}
        rejected = {item.strategy_id: item.reason for item in result.rejected}
        backtests = {item.strategy_id: item for item in result.backtests}
        for spec in specs:
            self.register(spec)
            if spec.strategy_id in backtests:
                self._move(spec, LifecycleState.RESEARCH, "research run finished", now)
                self._move(spec, LifecycleState.BACKTESTED, "replay finished", now)
            elif spec.strategy_id in rejected:
                self._move(spec, LifecycleState.RESEARCH, "research run finished", now)
            else:
                raise RegistryError(f"{spec.strategy_id} was neither backtested nor rejected")
        for strategy_id, reason in rejected.items():
            self._verdict(by_id[strategy_id].spec_hash(), accepted=False, reason=reason)
        for strategy_id, item in backtests.items():
            digest = by_id[strategy_id].spec_hash()
            self._verdict(digest, accepted=True, reason="critic accepted and the interpreter ran")
            self._backtest(digest, digest_text=item.digest, equity=item.ending_equity)

    def rows(self) -> tuple[RegistryRow, ...]:
        db = sqlite3.connect(self.path)
        try:
            found = db.execute(
                """
            SELECT specs.strategy_id, specs.version, specs.spec_hash, specs.hypothesis,
                   states.state, verdicts.accepted, verdicts.reason,
                   backtests.ending_equity, backtests.digest
            FROM specs
            JOIN states ON states.strategy_id = specs.strategy_id AND states.version = specs.version
            LEFT JOIN verdicts ON verdicts.spec_hash = specs.spec_hash
            LEFT JOIN backtests ON backtests.spec_hash = specs.spec_hash
            ORDER BY specs.strategy_id
            """
            ).fetchall()
        finally:
            db.close()
        return tuple(_row(item) for item in found)

    def _move(self, spec: StrategySpec, target: LifecycleState, reason: str, now: datetime) -> None:
        current = self.state(spec.strategy_id, spec.version)
        if current is target:
            return
        if target is LifecycleState.RESEARCH and current is not LifecycleState.DRAFT:
            return
        if target is LifecycleState.BACKTESTED and current is not LifecycleState.RESEARCH:
            return
        self.apply(
            LifecycleTransition(
                strategy_id=spec.strategy_id,
                strategy_version=spec.version,
                from_state=current,
                to_state=target,
                actor=Actor(kind=ActorKind.AGENT, actor_id="research"),
                reason=reason,
                occurred_at=ensure_utc(now),
            )
        )

    def _verdict(self, spec_hash: str, *, accepted: bool, reason: str) -> None:
        self._db.execute(
            """
            INSERT INTO verdicts (spec_hash, accepted, reason) VALUES (?, ?, ?)
            ON CONFLICT(spec_hash) DO NOTHING
            """,
            (spec_hash, 1 if accepted else 0, reason),
        )
        self._db.commit()

    def _backtest(self, spec_hash: str, *, digest_text: str, equity: Decimal) -> None:
        self._db.execute(
            """
            INSERT INTO backtests (spec_hash, digest, ending_equity) VALUES (?, ?, ?)
            ON CONFLICT(spec_hash) DO NOTHING
            """,
            (spec_hash, digest_text, format(equity, "f")),
        )
        self._db.commit()

    def _spec_exists(self, spec_hash: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM specs WHERE spec_hash = ?",
            (spec_hash,),
        ).fetchone()
        return row is not None


def _row(item: tuple[object, ...]) -> RegistryRow:
    accepted, reason, equity, digest = item[5], item[6], item[7], item[8]
    if accepted is None:
        verdict = "unreviewed"
        reason_text = ""
    elif accepted == 1:
        verdict = "accepted"
        reason_text = str(reason)
    else:
        verdict = "rejected"
        reason_text = str(reason)
    return RegistryRow(
        strategy_id=str(item[0]),
        version=int(str(item[1])),
        spec_hash=str(item[2]),
        hypothesis=str(item[3]),
        state=str(item[4]),
        verdict=verdict,
        reason=reason_text,
        ending_equity="" if equity is None else str(equity),
        digest="" if digest is None else str(digest),
    )


def load_philadelphia(path: Path) -> Registry:
    """Record the scripted Philadelphia run. Used by the local registry page."""
    from entropytrade.agents.fixture import WHEN, demo_specs
    from entropytrade.agents.pipeline import run_philadelphia_demo

    registry = Registry(path)
    registry.record_research(run_philadelphia_demo(), demo_specs(), now=WHEN)
    return registry


def human_approval(approver_id: str, *, when: datetime, note: str) -> HumanApproval:
    return HumanApproval(approver_id=approver_id, approved_at=ensure_utc(when), note=note)
