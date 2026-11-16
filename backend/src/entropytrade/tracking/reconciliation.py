"""Read-only proof for settlement-only paper cycles; no model, source fetch or order path.

Controls are frozen with the claim. Historical verification never consults today's HALT
state. The existing accountant receives the original ledger and no decision samples.
"""

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus, MarketType
from entropytrade.domain.market import Market
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.tracking.accounting import account_hash, reproduce

SCHEMA = "shadow-reconciliation-cycle-v1"
FEATURE_VERSION = "settlement-only-v1"
MAX_BYTES = 256_000_000
_UNSET = object()


def is_reconciliation(result: dict[str, Any]) -> bool:
    """Either marker selects strict verification; disagreeing markers never fall back."""
    return result.get("cycle_mode") == "reconcile_only" or result.get("schema") == SCHEMA


def terms(market: Market) -> dict[str, Any]:
    return {
        "ticker": market.ticker,
        "event": market.event_ticker,
        "series": market.series_ticker or market.ticker.split("-", 1)[0],
        "market_type": market.market_type.value,
        "settlement_basis": market.rules.settlement_basis,
        "settlement_target_date": market.rules.settlement_target_date.isoformat()
        if market.rules.settlement_target_date is not None
        else None,
        "settlement_sources": [
            source.model_dump(mode="json") for source in market.rules.settlement_sources
        ],
        "close": market.close_time.isoformat(),
        "strike": market.strike.model_dump(mode="json") if market.strike else None,
        "primary": market.rules.rules_primary,
        "secondary": market.rules.rules_secondary,
        "early_close": market.rules.early_close_condition,
    }


def same_frozen_terms(current: Market, frozen: Market) -> bool:
    """Keep the existing contextual normalization of optional legacy calendar metadata."""
    observed, original = terms(current), terms(frozen)
    observed_date = observed.pop("settlement_target_date")
    frozen_date = original.pop("settlement_target_date")
    if observed != original:
        return False
    if observed_date == frozen_date or current.rules.settlement_basis == "unresolved":
        return True
    return (
        observed_date is None
        and frozen_date is not None
        and ticker_target_date(current.ticker) is None
    )


def at(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value))


def validate_control(snapshot: dict[str, Any]) -> None:
    if (
        set(snapshot)
        != {
            "schema",
            "control_epoch",
            "cycle_mode",
            "halted",
            "event_hash",
            "execution_authorized",
        }
        or snapshot["schema"] != "shadow-cycle-control-v1"
        or type(snapshot["control_epoch"]) is not int
        or snapshot["control_epoch"] < 0
        or snapshot["cycle_mode"] not in {"paper", "reconcile_only"}
        or type(snapshot["halted"]) is not bool
        or snapshot["execution_authorized"] is not False
        or not isinstance(snapshot["event_hash"], str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot["event_hash"]) is None
    ):
        raise ValueError("invalid frozen cycle control snapshot")


def empty_inputs(
    spec: StrategySpec,
    before: dict[str, Any],
    contracts: list[dict[str, Any]],
    control: dict[str, Any],
) -> dict[str, Any]:
    """An explicit absence of predictions/features, retaining original account provenance."""
    validate_control(control)
    if control["cycle_mode"] != "reconcile_only":
        raise ValueError("settlement-only inputs require a reconciliation claim")
    if before.get("schema") != "shadow-paper-state-v1":
        raise ValueError("reconciliation requires an existing paper account")
    Ledger.load(before["ledger"])
    identity = {
        "schema": SCHEMA,
        "before_hash": account_hash(before),
        "contracts": contracts,
        "control_snapshot": control,
    }
    data = ExperimentData(
        dataset_version=scientific_hash(identity),
        feature_version=FEATURE_VERSION,
        data_kind=before["data_kind"],
        samples=(),
        feature_definitions={},
        provenance={"purpose": "settlement-only reconciliation; no forecast inputs"},
    )
    bundle = PredictionBundle(
        records=(),
        source_hash=scientific_hash({"purpose": "no predictions", **identity}),
        model_metadata={"purpose": "no model", "data_kind": before["data_kind"]},
    )
    return {
        "schema": "shadow-inputs-v1",
        "spec": spec.model_dump(mode="json"),
        "data": {
            **data.model_dump(mode="json", exclude_computed_fields=True),
            "protected_events": [],
        },
        "bundle": bundle.model_dump(mode="json", exclude_computed_fields=True),
        "reservations": [],
        "acquisition_complete": True,
        "fee": None,
        "fee_versions": [],
        "series_fees": [],
    }


def paper_inputs(
    inputs: dict[str, Any],
    before: dict[str, Any],
    contracts: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    as_of: datetime,
) -> dict[str, Any]:
    originals = {c["ticker"]: c for c in contracts}
    markets = {ticker: c["market"]["market"] for ticker, c in originals.items()}
    return {
        "schema": "shadow-paper-inputs-v2",
        "before": before,
        "before_hash": account_hash(before),
        "decision_inputs": inputs,
        "as_of": ensure_utc(as_of).isoformat(),
        "event_ids": {ticker: market["event_ticker"] for ticker, market in markets.items()},
        "close_times": {ticker: market["close_time"] for ticker, market in markets.items()},
        "outcomes": [o for o in outcomes if originals[o["ticker"]]["outcome"] is None],
        "execution_books": {},
        "execution_series_fees": [],
    }


def verify_transition(result: dict[str, Any]) -> dict[str, Any]:
    """Pure ledger/control proof, also usable inside the store's account transaction."""
    control = result["control_snapshot"]
    validate_control(control)
    if (
        result.get("schema") != SCHEMA
        or result.get("cycle_mode") != "reconcile_only"
        or control["cycle_mode"] != "reconcile_only"
        or result.get("control_epoch") != control["control_epoch"]
        or result.get("submission_enabled") is not False
        or any(result.get(name) for name in ("contracts", "decisions", "quotes", "fee_versions"))
        or any(
            result.get(name) is not None
            for name in (
                "capture",
                "execution",
                "paper_execution",
                "model_binding",
                "research_features",
            )
        )
        or result.get("model_refusals", {})
    ):
        raise ValueError("reconciliation contains a decision, model or execution path")
    frozen = result["reconciliation_contracts"]
    if not isinstance(frozen, list) or not 0 < len(frozen) <= 128:
        raise ValueError("reconciliation requires bounded frozen contracts")
    tickers = [c["ticker"] for c in frozen]
    if len(set(tickers)) != len(tickers):
        raise ValueError("reconciliation has duplicate frozen contracts")
    for contract in frozen:
        market = Market.model_validate(contract["market"]["market"])
        if (
            market.ticker != contract["ticker"]
            or market.market_type is not MarketType.BINARY
            or contract["market"]["ticker"] != contract["ticker"]
        ):
            raise ValueError("reconciliation frozen contract identity/payout mismatch")
    saved = result["paper_inputs"]
    before = saved["before"]
    if not isinstance(before, dict):
        raise ValueError("reconciliation cannot initialize or reset a paper account")
    end = at(saved["as_of"])
    started = at(result["cycle_started_at"])
    if not at(before["ledger"]["as_of"]) <= started <= end:
        raise ValueError("reconciliation clock precedes its original account or claim")
    spec = StrategySpec.model_validate(saved["decision_inputs"]["spec"])
    inputs = empty_inputs(spec, before, frozen, control)
    expected = paper_inputs(inputs, before, frozen, result["outcomes"], end)
    if saved != expected or result["data_kind"] != before["data_kind"]:
        raise ValueError("reconciliation inputs/provenance contain new economic inputs")
    actual = reproduce(saved)
    if result["paper"] != actual or actual["decisions"] or actual["executions"]:
        raise ValueError("reconciliation accounting differs or contains orders")
    after = actual["state"]
    for key in ("starting_cash", "fees_paid", "fills", "orders", "collateral"):
        if before["ledger"][key] != after["ledger"][key]:
            raise ValueError("reconciliation changed fills, orders, fees or reservations")
    if before["liquidity"] != after["liquidity"]:
        raise ValueError("reconciliation changed consumed order-book liquidity")
    if (
        result.get("dataset_version") != inputs["data"]["dataset_version"]
        or result.get("feature_version") != FEATURE_VERSION
    ):
        raise ValueError("reconciliation dataset identity mismatch")
    return inputs


def _official_outcome(
    body: dict[str, Any], receipt: dict[str, Any], original: Market
) -> dict[str, Any] | None:
    if receipt["status"] != 200:
        return None
    received = at(receipt["received_at"])
    try:
        raw = body["market"]
        market = market_from_body(raw, captured_at=received, series=original.series_ticker or "")
        if (
            not same_frozen_terms(market, original)
            or market.status is not MarketStatus.FINALIZED
            or market.result not in {MarketResult.YES, MarketResult.NO}
            or market.settlement_ts is None
            or not original.close_time <= market.settlement_ts <= received
            or market.settlement_value != (1 if market.result is MarketResult.YES else 0)
            or raw.get("is_provisional") not in {None, False}
        ):
            return None
        return {
            "ticker": original.ticker,
            "result": market.result.value,
            "settled_at": market.settlement_ts.isoformat(),
            "available_at": received.isoformat(),
            "receipt": receipt,
            "basis": "official binary result; no inferred scalar label",
        }
    except (ValueError, KeyError, TypeError, GatewayError):
        return None


def verify_reconciliation(
    root: Path,
    result: dict[str, Any],
    *,
    expected_before: object = _UNSET,
    expected_control: dict[str, Any] | None = None,
    expected_contracts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify immutable local receipts, empty inputs and exact settlement-only accounting.

    Callers with a database transaction additionally bind the previous account, original
    contracts and claim snapshot. No current control file or model is read here.
    """
    inputs = verify_transition(result)
    if result.get("cycle_id") != root.name:
        raise ValueError("reconciliation cycle identity differs from its retained directory")
    if expected_before is not _UNSET and result["paper_inputs"]["before"] != expected_before:
        raise ValueError("reconciliation previous account differs from committed ledger")
    if expected_control is not None:
        snapshot = expected_control.get("control_snapshot", expected_control)
        if result["control_snapshot"] != snapshot:
            raise ValueError("reconciliation frozen control differs from its claim")
        if (
            "started_at" in expected_control
            and result["cycle_started_at"] != expected_control["started_at"]
        ):
            raise ValueError("reconciliation start differs from its claim")
    if expected_contracts is not None and result["reconciliation_contracts"] != expected_contracts:
        raise ValueError("reconciliation contracts differ from original frozen terms")
    artifacts = {}
    budget = 0
    for artifact in result["artifacts"]:
        name = artifact["path"]
        relative = PurePosixPath(name)
        path = root / name
        if (
            name in artifacts
            or relative.is_absolute()
            or str(relative) != name
            or any(part in {".", ".."} for part in relative.parts)
            or any(parent.is_symlink() for parent in (path, *path.parents))
            or not path.resolve().is_relative_to(root.resolve())
            or not path.is_file()
            or path.stat().st_size != artifact["bytes"]
            or file_hash(path) != artifact["sha256"]
        ):
            raise ValueError("reconciliation artifact checksum/path mismatch")
        budget += artifact["bytes"]
        if budget > MAX_BYTES:
            raise ValueError("reconciliation evidence exceeds bounded size")
        artifacts[name] = artifact["sha256"]
    summary = json.loads((root / "outcomes/summary.json").read_text())
    if any(result.get(key) != value for key, value in summary.items()):
        raise ValueError("reconciliation outcome summary differs from retained result")
    receipts = summary["outcome_receipts"]
    if len(receipts) > 20:
        raise ValueError("reconciliation outcome receipt budget exceeded")
    refs = [receipt["raw_ref"] for receipt in receipts]
    if len(set(refs)) != len(refs) or set(artifacts) != {
        "decision-inputs.json",
        "paper-inputs.json",
        "outcomes/summary.json",
        *refs,
    }:
        raise ValueError("reconciliation contains unbound forecast or execution artifacts")
    if (
        json.loads((root / "decision-inputs.json").read_text()) != inputs
        or json.loads((root / "paper-inputs.json").read_text()) != result["paper_inputs"]
    ):
        raise ValueError("reconciliation retained accounting inputs differ")
    originals = {
        c["ticker"]: Market.model_validate(c["market"]["market"])
        for c in result["reconciliation_contracts"]
    }
    paths = {
        path: original
        for ticker, original in originals.items()
        for path in (
            f"/trade-api/v2/markets/{ticker}",
            f"/trade-api/v2/historical/markets/{ticker}",
        )
    }
    observed = []
    start, end = at(result["cycle_started_at"]), at(result["paper_inputs"]["as_of"])
    for receipt in receipts:
        ref = receipt["raw_ref"]
        if (
            PurePosixPath(ref).parent.as_posix() != "outcomes"
            or receipt["sha256"] != artifacts[ref]
            or receipt["path"] not in paths
            or not start <= at(receipt["received_at"]) <= end
        ):
            raise ValueError("reconciliation outcome lacks its original fresh GET receipt")
        try:
            body = json.loads((root / ref).read_bytes())
        except (ValueError, UnicodeError):
            body = {}
        outcome = _official_outcome(body, receipt, paths[receipt["path"]])
        if outcome is not None:
            observed.append(outcome)
    if observed != result["outcomes"]:
        raise ValueError("reconciliation outcome differs from official frozen-term receipt")
    return inputs
