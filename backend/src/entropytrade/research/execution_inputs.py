"""Verified acquired execution evidence to the existing weather replay adapter.

There is no fetcher, importer, model loader, or order transport here. Inputs are frozen
research dataset IDs and an in-memory model fitted by the same persistent job. Existing
post-settlement contract records remain insufficient for historical execution. A usable
record must retain typed receipt-clock market/rule evidence and typed sized market state.
"""

import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from entropytrade.data.schema import MarketEvidence, MarketState
from entropytrade.domain.enums import MarketResult, MarketStatus, MarketType
from entropytrade.domain.market import Market
from entropytrade.domain.market_data import OrderBook
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.experiments.data import (
    ContractSample,
    ExperimentData,
    PredictionBundle,
    ProbabilityRecord,
)
from entropytrade.experiments.engine import ExperimentConfig
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.evaluation import TemporalPlan
from entropytrade.ml.models import WeatherModel
from entropytrade.research.acquire import load_records
from entropytrade.research.backtesting import backtest_hypothesis
from entropytrade.research.families import weather_family
from entropytrade.research.model import HypothesisSpec
from entropytrade.research.registry import FeatureRegistry


def execution_locations() -> dict[str, dict[str, str]]:
    """Reviewed mappings already used by research and the canonical collector config."""
    family = weather_family(Path(__file__).resolve().parents[4])
    return {
        item.series: {"entity": item.entity, "timezone": item.timezone, "name": item.name}
        for item in family.entities
    }


def _clock(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("execution evidence requires timezone-aware receipt clocks")
    return result


def _records(
    root: Path,
    identifiers: tuple[str, ...],
    data_kind: Literal["real", "synthetic"],
    excluded_dates: frozenset[date] = frozenset(),
    included_dates: frozenset[date] | None = None,
) -> tuple[
    list[tuple[MarketEvidence, datetime]],
    list[tuple[MarketState, datetime]],
    int,
    list[dict[str, str]],
]:
    # Reuse the exact immutable dataset/raw-byte verifier used for model inputs. Importing
    # at execution time avoids a module dependency cycle with the modeling orchestrator.
    from entropytrade.research.modeling import _dataset

    markets = []
    states = []
    reduced = 0
    protected_identities = []
    for identifier in sorted(set(identifiers)):
        _dataset(root, identifier, data_kind)
        directory = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
        receipts: dict[str, set[datetime]] = defaultdict(set)
        for line in (directory / "receipts.jsonl").read_text().splitlines():
            raw = json.loads(line)
            if raw.get("received_at") is not None:
                at = _clock(raw["received_at"])
                digest = raw["sha256"]
                receipts[digest].add(at)
        for raw in load_records(root, identifier):
            kind = raw.get("record_type")
            ticker = str(
                (raw.get("market") or {}).get("ticker")
                or raw.get("market_ticker")
                or raw.get("ticker")
                or ""
            )
            if included_dates is not None and ticker_target_date(ticker) not in included_dates:
                continue
            if kind == "protected_identity":
                target = ticker_target_date(ticker)
                if (
                    set(raw)
                    - {
                        "record_type",
                        "ticker",
                        "series",
                        "target_date",
                        "close_time",
                        "raw_hash",
                        "raw_ref",
                    }
                    or target is None
                    or raw.get("target_date") != target.isoformat()
                    or raw.get("series") != ticker.split("-", 1)[0]
                    or raw.get("raw_hash") not in receipts
                ):
                    raise ValueError("protected contract identity lacks verified source binding")
                _clock(raw["close_time"])
                if target not in excluded_dates:
                    raise ValueError("source-protected identity overlaps the modeling partition")
                protected_identities.append(
                    {
                        key: str(raw[key])
                        for key in ("ticker", "series", "target_date", "close_time")
                    }
                )
                continue
            if ticker_target_date(ticker) in excluded_dates:
                # Preserve actual contract identity/close clocks for the engine's existing
                # temporal cutoff, without deserializing any protected rule/outcome value.
                if kind == "market_evidence" and raw.get("raw_hash") in receipts:
                    market_identity = raw["market"]
                    protected_identities.append(
                        {
                            "ticker": ticker,
                            "series": str(market_identity.get("series_ticker", "")),
                            "target_date": str(ticker_target_date(ticker)),
                            "close_time": str(market_identity["close_time"]),
                        }
                    )
                continue
            if kind == "contract":
                # The A/B adapter explicitly records retrieval_after_settlement. Never
                # upgrade those terms to known-at-decision evidence from their target date.
                reduced += 1
                continue
            if kind not in {"market_evidence", "market_state"}:
                continue
            value = {k: v for k, v in raw.items() if k != "record_type"}
            digest = value.get("raw_hash")
            if digest not in receipts:
                raise ValueError("execution record lacks its preserved raw receipt clock")
            received = min(receipts[digest])
            if kind == "market_evidence":
                evidence = MarketEvidence.model_validate(value)
                if (
                    evidence.capture_basis != "receipt"
                    or evidence.market.rules.captured_at < received
                ):
                    raise ValueError("market/rule availability precedes its actual raw receipt")
                markets.append((evidence, received))
            else:
                state = MarketState.model_validate(value)
                # Content-addressed raw bytes can have several genuine HTTP receipts.
                # Bind this normalized state to its exact retained receipt when present;
                # an unchanged response after decision still proves a later observation.
                # Unmatched legacy clocks retain the earliest conservative boundary and
                # cannot promote processing time into new post-decision evidence.
                if state.received_at is not None and state.received_at in receipts[digest]:
                    received = state.received_at
                if state.available_at is None or state.available_at < received:
                    raise ValueError("market-state availability precedes its actual raw receipt")
                states.append((state, received))
    return markets, states, reduced, protected_identities


def _known_rules(evidence: MarketEvidence | Market, *, entity: str, name: str) -> bool:
    market = evidence.market if isinstance(evidence, MarketEvidence) else evidence
    rules = market.rules
    text = (rules.rules_primary + " " + rules.rules_secondary).casefold()
    authorities = " ".join(source.name.casefold() for source in rules.settlement_sources)
    return (
        rules.market_ticker == market.ticker
        and rules.settlement_basis == "contract_text"
        and "weather company" in authorities
        and "weather company" in text
        and "national weather service" not in authorities
        and "nws" not in authorities
        and ("fahrenheit" in text or "°f" in text)
        and (entity.casefold() in text or name.casefold() in text)
        and market.strike is not None
        and market.strike.is_evaluable
    )


def acquired_backtest(
    *,
    root: Path,
    registry: FeatureRegistry,
    spec: HypothesisSpec,
    rows: list[dict[str, Any]],
    model: WeatherModel,
    model_hash: str,
    plan: TemporalPlan,
    execution_datasets: tuple[str, ...] = (),
    fee_versions: tuple[FeeVersion, ...] = (),
    data_kind: Literal["real", "synthetic"] = "real",
    config: ExperimentConfig | None = None,
    fitted_thresholds: Mapping[str, Decimal] | None = None,
    asof: datetime | None = None,
) -> dict[str, Any]:
    """Assemble actual contract probabilities, then invoke the existing deterministic engine.

    Protected event outcomes never enter samples or probability records. Final exchange
    results require a later original receipt and agreement with earlier strike/rule versions;
    scalar labels are checked against them rather than used to manufacture exchange results.
    """
    config = (config or ExperimentConfig()).revalidated(fee_policy=None, fee_versions=fee_versions)
    provenance: dict[str, Any] = {
        "dataset_versions": sorted(set(execution_datasets)),
        "fee_versions": [version.version for version in fee_versions],
        "locations": execution_locations(),
        "threshold_method": "training-only median; no validation threshold search",
        "fitted_thresholds": {
            name: str(value) for name, value in (fitted_thresholds or {}).items()
        },
    }
    refusal = backtest_hypothesis(spec=spec, registry=registry, config=config)
    refusal["execution_input_provenance"] = provenance
    if not execution_datasets:
        return refusal
    excluded_dates = frozenset(
        date.fromisoformat(row["target_date"]) for row in rows if row["event_id"] in plan.holdout
    )
    markets, states, reduced, protected_identities = _records(
        root,
        execution_datasets,
        data_kind,
        excluded_dates,
        frozenset(date.fromisoformat(row["target_date"]) for row in rows),
    )
    provenance.update(
        market_evidence_records=len(markets),
        market_state_records=len(states),
        postsettlement_contract_records=reduced,
    )
    if not markets:
        refusal["reasons"].append(
            "Acquired settled contract metadata cannot establish "
            "rules known at historical decisions."
        )
        return refusal
    locations = execution_locations()
    for series in spec.universe:
        if series not in locations:
            raise ValueError("unreviewed series/station mapping for acquired execution evidence")
    if registry.resolve(spec.label.name).feature_id != "settlement_high_f":
        raise ValueError("execution adapter requires the registered settlement-authority high")
    by_ticker: dict[str, list[tuple[MarketEvidence, datetime]]] = defaultdict(list)
    for market_evidence, received in markets:
        by_ticker[market_evidence.market.ticker].append((market_evidence, received))
    books: dict[str, list[tuple[MarketState, datetime]]] = defaultdict(list)
    for state, received in states:
        books[state.market_ticker].append((state, received))
    definitions = [
        registry.get(str(registry.resolve(need.name).feature_id)) for need in spec.features
    ]
    feature_schema = {
        "features": [
            {
                "name": d.feature_id,
                "version": d.version,
                "unit": d.unit,
                "dtype": d.dtype,
                "definition_hash": d.definition_hash,
            }
            for d in definitions
        ]
    }
    if model.feature_names != tuple(d.feature_id for d in definitions):
        raise ValueError("fitted model feature definitions differ from the frozen hypothesis")
    feature_version = scientific_hash(
        {
            "schema": feature_schema,
            "rows": [
                {k: row[k] for k in ("event_id", "decision_time", "features")} for row in rows
            ],
        }
    )
    dataset_version = scientific_hash(
        {"execution_datasets": sorted(set(execution_datasets)), "feature_version": feature_version}
    )
    samples: list[ContractSample] = []
    predictions = []
    protected = frozenset(plan.holdout)
    protected_rows = [row for row in rows if row["event_id"] in protected]
    cutoff = min((_clock(row["decision_time"]) for row in protected_rows), default=None)
    provenance["evaluation_cutoff"] = cutoff.isoformat() if cutoff else None
    identities = {identity["ticker"]: identity for identity in protected_identities}
    protected_shells = []
    for row in protected_rows:
        for identity in identities.values():
            series = identity["series"]
            if (
                series not in spec.universe
                or locations[series]["entity"] != row["entity"]
                or identity["target_date"] != row["target_date"]
            ):
                continue
            at = _clock(row["decision_time"])
            protected_shells.append(
                ContractSample(
                    event_id=row["event_id"],
                    ticker=identity["ticker"],
                    family=series,
                    target_date=date.fromisoformat(row["target_date"]),
                    decision_time=at,
                    close_time=_clock(identity["close_time"]),
                    features_available_at=at,
                    features={},
                    versions={},
                    feature_hash=scientific_hash(identity),
                    rules_known=False,
                    eligible=False,
                    fidelity="missing",
                )
            )
    if cutoff is not None and not any(shell.decision_time == cutoff for shell in protected_shells):
        refusal["reasons"] = [
            "Actual protected contract identity is unavailable at the frozen evaluation boundary."
        ]
        return refusal
    provenance["protected_identity_shells"] = len(protected_shells)
    source = "synthetic-kalshi" if data_kind == "synthetic" else "kalshi"
    refusals: dict[str, int] = defaultdict(int)
    incomplete_outcomes: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["event_id"] in protected or row["event_id"] not in plan.validation:
            continue
        if any(row["features"].get(d.feature_id) is None for d in definitions):
            refusals["missing decision-time predictive features"] += 1
            continue
        decision = _clock(row["decision_time"])
        if (
            model.fit_asof is None
            or model.fit_asof > decision
            or (model.calibration.fit_asof is not None and model.calibration.fit_asof > decision)
        ):
            raise ValueError("fitted/calibrated model is unavailable at contract decision")
        target_date = date.fromisoformat(row["target_date"])
        for ticker, versions in by_ticker.items():
            series = ticker.split("-", 1)[0]
            if series not in spec.universe or locations[series]["entity"] != row["entity"]:
                continue
            if ticker_target_date(ticker) != target_date:
                continue
            known = [
                evidence
                for evidence, received in versions
                if evidence.market.rules.captured_at <= decision
                and received <= decision
                and evidence.market.open_time <= decision
                and evidence.created_at is not None
                and evidence.created_at <= decision
            ]
            if not known:
                refusals["no contract/rule receipt available by decision"] += 1
                continue
            first = max(known, key=lambda evidence: evidence.market.rules.captured_at)
            tied = [
                item
                for item in known
                if item.market.rules.captured_at == first.market.rules.captured_at
            ]
            if len({scientific_hash(item.market.model_dump(mode="json")) for item in tied}) > 1:
                raise ValueError(
                    "conflicting decision-time contract snapshots at one receipt clock"
                )
            market = first.market
            if (
                market.market_type is not MarketType.BINARY
                or market.series_ticker != series
                or market.event_ticker != series + "-" + target_date.strftime("%y%b%d").upper()
                or market.close_time <= decision
                or market.status is not MarketStatus.ACTIVE
                or market.rules.settlement_target_date not in {None, target_date}
                or not _known_rules(first, entity=row["entity"], name=locations[series]["name"])
            ):
                refusals[
                    "unverified authority, Fahrenheit units, station, terms or open contract"
                ] += 1
                continue
            # The scheduled close is known in the decision-time rule snapshot. This
            # predeclared window gate cannot select trades using eventual publication.
            if cutoff is not None and market.close_time >= cutoff:
                refusals["scheduled contract close is outside the frozen evaluation window"] += 1
                continue
            if row["target"] is None or row["label_available_at"] is None:
                incomplete_outcomes["source-matched scalar label unavailable"] += 1
                continue
            final = [
                (evidence, received)
                for evidence, received in versions
                if evidence.market.status is MarketStatus.FINALIZED
                and evidence.market.result in {MarketResult.YES, MarketResult.NO}
            ]
            if not final:
                incomplete_outcomes["official finalized exchange outcome receipt unavailable"] += 1
                continue
            evidence, received = max(final, key=lambda item: item[0].market.rules.captured_at)
            tied = [
                item
                for item, _ in final
                if item.market.rules.captured_at == evidence.market.rules.captured_at
            ]
            if len({scientific_hash(item.market.model_dump(mode="json")) for item in tied}) > 1:
                raise ValueError("conflicting finalized contract snapshots at one receipt clock")
            if (
                evidence.market.market_type is not MarketType.BINARY
                or evidence.market.rules.rules_hash != market.rules.rules_hash
                or evidence.market.strike != market.strike
                or evidence.market.close_time != market.close_time
                or evidence.market.series_ticker != market.series_ticker
                or evidence.market.event_ticker != market.event_ticker
                or evidence.market.rules.settlement_basis != market.rules.settlement_basis
                or evidence.market.rules.settlement_target_date
                != market.rules.settlement_target_date
                or not _known_rules(evidence, entity=row["entity"], name=locations[series]["name"])
            ):
                raise ValueError("decision/finalized contract rule or strike version mismatch")
            outcome_at = max(received, evidence.market.rules.captured_at)
            if asof is not None and outcome_at > asof:
                raise ValueError("finalized exchange outcome receipt is in the future")
            target_end = datetime.combine(
                target_date + timedelta(days=1),
                datetime.min.time(),
                ZoneInfo(locations[series]["timezone"]),
            )
            if outcome_at < target_end or _clock(row["label_available_at"]) < target_end:
                raise ValueError(
                    "final outcome or scalar label became available before target day ended"
                )
            strike = market.strike
            if strike is None:
                raise ValueError("contract strike disappeared after validation")
            target = Decimal(str(row["target"]))
            if target != target.to_integral_value():
                raise ValueError("settlement-authority label must be an integer Fahrenheit high")
            actual = MarketResult.YES if strike.resolves_yes(target) else MarketResult.NO
            if actual is not evidence.market.result:
                raise ValueError(
                    "source-matched scalar label and finalized exchange outcome disagree"
                )
            candidates = []
            execution_candidates: dict[datetime, OrderBook] = {}
            for state, state_receipt in books[ticker]:
                if state.fidelity != "order_book" or state.available_at is None:
                    continue
                raw_book = dict(state.payload)
                # Outer availability is the actual receipt boundary, even if a payload
                # carries an earlier exchange-side clock. Never backdate it to decision.
                original_book = OrderBook.model_validate(raw_book)
                raw_book["received_at"] = max(
                    original_book.received_at, state.available_at, state_receipt
                ).isoformat()
                parsed_book = OrderBook.model_validate(raw_book)
                if parsed_book.market_ticker != ticker:
                    raise ValueError("market-state ticker differs from its sized book")
                if parsed_book.received_at > decision:
                    # Processing or payload clocks cannot turn an earlier HTTP response
                    # into a newly observed post-decision book.
                    if state_receipt <= decision:
                        refusals["later book clock lacks a post-decision raw receipt"] += 1
                        continue
                    if parsed_book.received_at >= market.close_time or (
                        asof is not None and parsed_book.received_at > asof
                    ):
                        continue
                    if (
                        parsed_book.exchange_ts is not None
                        and parsed_book.exchange_ts > parsed_book.received_at
                    ):
                        raise ValueError(
                            "execution book exchange clock is after its original receipt"
                        )
                    previous = execution_candidates.get(parsed_book.received_at)
                    if previous is not None and previous != parsed_book:
                        raise ValueError("conflicting execution books at one receipt clock")
                    execution_candidates[parsed_book.received_at] = parsed_book
                    if len(execution_candidates) > 1024:
                        raise ValueError("execution book history exceeds bounded replay limit")
                    continue
                if decision - parsed_book.received_at > timedelta(
                    seconds=config.max_book_age_seconds
                ):
                    continue
                if parsed_book.exchange_ts is not None and parsed_book.exchange_ts > decision:
                    continue
                candidates.append(parsed_book)
            book = max(candidates, key=lambda item: item.received_at) if candidates else None
            if book is not None:
                tied_books = [item for item in candidates if item.received_at == book.received_at]
                if len({scientific_hash(item.model_dump(mode="json")) for item in tied_books}) > 1:
                    raise ValueError("conflicting sized books at one receipt clock")
            if book is None:
                refusals["historical decision-time sized book unavailable"] += 1
            features: dict[str, Decimal | None] = {
                d.feature_id: Decimal(str(row["features"][d.feature_id])) for d in definitions
            }
            feature_hash = scientific_hash({name: str(value) for name, value in features.items()})
            sample = ContractSample(
                event_id=row["event_id"],
                ticker=ticker,
                family=series,
                target_date=target_date,
                decision_time=decision,
                close_time=market.close_time,
                features_available_at=_clock(row["features_available_at"]),
                features=features,
                versions={d.feature_id: d.version for d in definitions},
                feature_hash=feature_hash,
                sources=(source, "verified-research-features"),
                rules_known=True,
                eligible=True,
                outcome=actual,
                outcome_available_at=outcome_at,
                book=book,
                execution_books=tuple(
                    execution_candidates[key] for key in sorted(execution_candidates)
                ),
                fidelity="order_book" if book is not None else "missing",
            )
            samples.append(sample)
            probability = model.predict_proba(row["features"], strike, unit="degF")
            prediction_identity = {
                "event_id": row["event_id"],
                "ticker": ticker,
                "decision_time": decision.isoformat(),
                "model_hash": model_hash,
                "feature_hash": feature_hash,
                "probability_yes": probability,
            }
            predictions.append(
                ProbabilityRecord(
                    event_id=row["event_id"],
                    ticker=ticker,
                    decision_time=decision,
                    family=model.kind,
                    model_hash=model_hash,
                    feature_hash=feature_hash,
                    feature_version=feature_version,
                    fitted_before=model.fit_asof,
                    calibrated_before=model.calibration.fit_asof,
                    calibration=model.calibration.method,
                    probability_yes=Decimal(str(probability)),
                    partition="validation",
                    prediction_id=scientific_hash(prediction_identity),
                )
            )
    provenance["refusals"] = dict(refusals)
    provenance["incomplete_outcomes"] = dict(incomplete_outcomes)
    if incomplete_outcomes:
        refusal["reasons"] = [
            "Executable returns refused for the entire decision-eligible universe: " + reason
            for reason in incomplete_outcomes
        ]
        return refusal
    if not samples:
        refusal["reasons"] = [
            "No verified validation contract samples: " + reason for reason in refusals
        ]
        if not refusal["reasons"]:
            refusal["reasons"] = [
                "No acquired contracts match this station/date/validation partition."
            ]
        return refusal
    data = ExperimentData(
        dataset_version=dataset_version,
        feature_version=feature_version,
        data_kind=data_kind,
        samples=(*samples, *protected_shells),
        protected_events=protected,
        feature_definitions=feature_schema,
        provenance=provenance,
    )
    bundle = PredictionBundle(
        records=tuple(predictions),
        source_hash=scientific_hash([p.model_dump(mode="json") for p in predictions]),
        model_metadata={
            "data_kind": data_kind,
            "dataset_version": dataset_version,
            "split": {"holdout": sorted(protected)},
            "prospective": False,
        },
    )
    result = backtest_hypothesis(
        spec=spec,
        registry=registry,
        data=data,
        bundle=bundle,
        config=config,
        model_hash=model_hash,
        model_family=model.kind,
        fitted_thresholds=fitted_thresholds,
        required_sources=(source, "verified-research-features"),
    )
    result["execution_input_provenance"] = provenance
    return result
