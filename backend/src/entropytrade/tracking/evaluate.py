"""Deterministic shadow decisions using the replay view, typed DSL and existing risk engine."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from entropytrade.backtest.replay import DecisionView
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.observations import FeatureObservation
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.portfolio import PortfolioSnapshot, SnapshotSource
from entropytrade.domain.strategy import CalibrationMethod, StrategySpec
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.experiments.engine import FeePolicy
from entropytrade.features.registry import scientific_hash
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.strategies.interpret import compile_strategy


def shadow_limits() -> RiskLimits:
    # Same monetary caps as the experiment defaults. Browser/strategy cannot override them.
    return RiskLimits(
        bankroll=Decimal("1000"),
        per_trade=Decimal("25"),
        per_event=Decimal("100"),
        total_deployed=Decimal("500"),
        max_loss=Decimal("1000"),
        max_drawdown=Decimal("1000"),
        max_book_age_seconds=60,
        min_liquidity=Decimal("0.01"),
        max_spread=Decimal("0.10"),
        max_open_orders=100,
        config_version="shadow-v1",
    )


def protected_events(data: ExperimentData, bundle: PredictionBundle) -> frozenset[str]:
    """Honor both dataset and model boundaries before projecting any shadow evidence."""
    return data.protected_events | frozenset(
        (bundle.model_metadata.get("split") or {}).get("holdout", [])
    )


def evaluate(
    spec: StrategySpec,
    data: ExperimentData,
    bundle: PredictionBundle,
    *,
    fee: FeePolicy | None = None,
    reservations: tuple[dict[str, Any], ...] = (),
    acquisition_complete: bool = True,
) -> list[dict[str, Any]]:
    strategy = compile_strategy(spec)
    limits = shadow_limits()
    engine = RiskEngine(limits)
    held = [dict(r) for r in reservations]
    rows: list[dict[str, Any]] = []
    universe = spec.market_universe
    protected = protected_events(data, bundle)
    accepted_calibrations = (
        {"none", "uncalibrated baseline"}
        if spec.calibration is CalibrationMethod.NONE
        else {spec.calibration.value}
    )
    for sample in sorted(data.samples, key=lambda s: (s.decision_time, s.ticker)):
        if not (
            sample.ticker in universe.market_tickers
            or sample.event_id in universe.event_tickers
            or sample.family in universe.series_tickers
        ):
            continue
        if sample.event_id in protected:
            continue  # Never persist protected feature/target values in a monitoring projection.
        when = sample.decision_time
        predictions = [
            r
            for r in bundle.records
            if r.usable(sample)
            and r.feature_version == data.feature_version
            and r.partition != "holdout"
        ]
        prediction = predictions[0] if len(predictions) == 1 else None
        gates = {
            "complete_acquisition": acquisition_complete,
            "open_market": when < sample.close_time,
            "verified_rules": sample.rules_known,
            "available_features": sample.eligible,
            "strategy_features": all(
                f.name in sample.features
                and sample.features[f.name] is not None
                and (f.version is None or sample.versions.get(f.name) == f.version)
                for f in spec.features
            ),
            "required_sources": set(spec.required_sources) <= set(sample.sources),
            "point_in_time_prediction": prediction is not None,
            "sized_book": sample.book is not None and sample.fidelity == "order_book",
            "certified_fees": fee is not None
            and fee.certified
            and bool(fee.evidence_hash)
            and fee.available_at <= when
            and fee.effective_from <= when
            and (fee.effective_to is None or when < fee.effective_to),
        }
        if prediction is not None and prediction.calibration not in accepted_calibrations:
            # Add a refusal only on mismatch, preserving replay hashes for prior safe decisions.
            gates["requested_calibration"] = False
        row: dict[str, Any] = {
            "ticker": sample.ticker,
            "event_id": sample.event_id,
            "decision_time": when.isoformat(),
            "feature_hash": sample.feature_hash,
            "feature_version": data.feature_version,
            "source_versions": sample.versions,
            "sources": sample.sources,
            "features": {k: str(v) if v is not None else None for k, v in sample.features.items()},
            "prediction": prediction.model_dump(mode="json") if prediction else None,
            "quote": sample.book.model_dump(mode="json") if sample.book else None,
            "gates": gates,
            "intent": None,
            "risk": None,
            "status": "blocked",
            "reasons": [name for name, passed in gates.items() if not passed],
        }
        if all(gates.values()):
            assert prediction is not None  # noqa: S101
            assert fee is not None  # noqa: S101
            assert sample.book is not None  # noqa: S101
            records = [
                FeatureObservation(
                    source_id="pit-feature-matrix",
                    event_time=when,
                    available_at=sample.features_available_at,
                    ingested_at=when,
                    feature_name=name,
                    feature_version=sample.versions[name],
                    entity_id=sample.ticker,
                    value=value,
                    input_manifest_hash=data.feature_version,
                )
                for name, value in sample.features.items()
            ]
            records.append(
                FeatureObservation(
                    source_id=prediction.family,
                    event_time=when,
                    available_at=when,
                    ingested_at=when,
                    feature_name=spec.probability_feature or "model_yes_probability",
                    feature_version="r2-prediction-v1",
                    entity_id=sample.ticker,
                    value=prediction.probability_yes,
                    input_manifest_hash=prediction.model_hash,
                )
            )
            intents = [OrderIntent.model_validate(r["intent"]) for r in held]
            pending = {
                (i.contract.market_ticker, i.contract.side): sum(
                    (j.quantity for j in intents if j.contract == i.contract), ZERO
                )
                for i in intents
            }
            intent = strategy(
                DecisionView(
                    records,
                    when,
                    schedule=fee.schedule,
                    pending=pending,
                    target_date=sample.target_date,
                ),
                sample.book,
            )
            row["status"] = "no_signal"
            if intent is not None:
                collateral = sum(
                    (
                        i.max_cost + (i.edge.fee_per_contract * i.quantity if i.edge else ZERO)
                        for i in intents
                    ),
                    ZERO,
                )
                event_cost = sum(
                    (
                        i.max_cost + (i.edge.fee_per_contract * i.quantity if i.edge else ZERO)
                        for r, i in zip(held, intents, strict=True)
                        if r["event_id"] == sample.event_id
                    ),
                    ZERO,
                )
                decision = engine.evaluate(
                    intent,
                    portfolio=PortfolioSnapshot(
                        as_of=when,
                        source=SnapshotSource.PAPER,
                        cash_balance=limits.bankroll - collateral,
                        resting_order_collateral=collateral,
                    ),
                    book=sample.book,
                    now=when,
                    event_deployed=event_cost,
                    realized_pnl=ZERO,
                    peak_equity=limits.bankroll,
                    equity=limits.bankroll,
                    open_orders=len(held),
                    model_as_of=prediction.fitted_before,
                )
                decision = decision.revalidated(
                    decision_id=UUID(
                        scientific_hash(
                            {
                                "intent": intent.model_dump(mode="json"),
                                "checks": [c.model_dump() for c in decision.checks],
                            }
                        ).removeprefix("sha256:")[:32]
                    )
                )
                row["intent"], row["risk"] = (
                    intent.model_dump(mode="json", exclude_computed_fields=True),
                    decision.model_dump(mode="json"),
                )
                # Partial risk size is a refusal: never silently change the strategy's intention.
                intended_cost = intent.max_cost + (
                    intent.edge.fee_per_contract * intent.quantity if intent.edge else ZERO
                )
                affordable = (
                    intended_cost <= limits.per_trade
                    and intended_cost + event_cost <= limits.per_event
                    and intended_cost + collateral <= limits.total_deployed
                    and intended_cost + collateral <= limits.bankroll
                )
                eligible = (
                    decision.approved
                    and decision.approved_quantity == intent.quantity
                    and affordable
                )
                row["status"] = "shadow_eligible" if eligible else "risk_rejected"
                row["reasons"] = [c.check_name for c in decision.failed_checks]
                if decision.approved and decision.approved_quantity != intent.quantity:
                    row["reasons"].append("risk_size_below_intended_quantity")
                if not affordable:
                    row["reasons"].append("fee_inclusive_shadow_collateral")
                if eligible:
                    held.append({"intent": row["intent"], "event_id": sample.event_id})
        row["decision_hash"] = scientific_hash(row)
        rows.append(row)
    return rows
