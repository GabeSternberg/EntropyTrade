"""One bounded credential-free shadow cycle. Only existing public GET adapters are used."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from entropytrade.api.jobs import Jobs, identifier
from entropytrade.api.server import workspace_path
from entropytrade.data.schema import MarketEvidence
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import KalshiEnvironment, MarketResult, MarketStatus
from entropytrade.domain.market import Market
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.execution.fee_evidence import FeeEvidenceStore, FeeVersion
from entropytrade.families.bitcoin_history import OutcomeTransport
from entropytrade.families.weather_capture import capture_public
from entropytrade.ml.forward import FrozenWeather
from entropytrade.research.paper_models import PortableResearchModel, paper_window
from entropytrade.tracking.accounting import account_hash
from entropytrade.tracking.accounting import reproduce as reproduce_paper
from entropytrade.tracking.evaluate import evaluate, shadow_limits
from entropytrade.tracking.market_data import capture_execution
from entropytrade.tracking.models import score
from entropytrade.tracking.replay import decision_inputs
from entropytrade.tracking.research_features import (
    acquire_research_features,
    materialize_research_features,
)
from entropytrade.tracking.store import TrackingStore
from entropytrade.weather.collection import WeatherConfig


def terms(market: Market) -> dict[str, Any]:
    return {
        "ticker": market.ticker,
        "event": market.event_ticker,
        # Individual-market responses omit series_ticker; the frozen full ticker still
        # carries its venue series prefix. An explicit contradictory series remains distinct.
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
    """Compare payout terms while retaining the frozen context of optional parsed dates.

    Calendar metadata is deliberately cleared by the unsupported Bitcoin adapter. Its
    official binary result may still be observed without upgrading those unverified rules.
    An opaque legacy contract may retain its originally supplied calendar when the final
    decoder cannot derive one. Neither case permits a change to text, payout type, source,
    basis, ticker/event/series, close or strike, or an explicit conflicting verified date.
    """
    observed, original = terms(current), terms(frozen)
    observed_date = observed.pop("settlement_target_date")
    frozen_date = original.pop("settlement_target_date")
    if observed != original:
        return False
    if observed_date == frozen_date:
        return True
    if current.rules.settlement_basis == "unresolved":
        return True
    return (
        observed_date is None
        and frozen_date is not None
        and ticker_target_date(current.ticker) is None
    )


async def outcomes(
    root: Path,
    contracts: list[dict[str, Any]],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    now = (clock or SystemClock()).now
    root.mkdir()
    closed = [
        c for c in contracts if Market.model_validate(c["market"]["market"]).close_time <= now()
    ]
    closed.sort(key=lambda c: (c["last_attempt"], c["ticker"]))
    pending = [c for c in closed if c["outcome"] is None]
    finalized = [c for c in closed if c["outcome"] is not None]
    # Reserve revision capacity without starving unresolved contracts. Accounting still
    # freezes its first settlement; subsequent official observations are monitoring only.
    selected = pending[:5] + finalized[:5]
    selected += [c for c in closed if c not in selected][: 10 - len(selected)]
    receipts: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "outcomes": [],
        "outcome_attempts": [],
        "outcome_failures": [],
        "outcome_deferred": max(0, len(closed) - 10),
        "outcome_receipts": receipts,
    }

    def retain(raw: RawCapture) -> None:
        name = f"{len(receipts):04d}.json"
        (root / name).write_bytes(raw.body)
        receipts.append(
            {
                "raw_ref": "outcomes/" + name,
                "sha256": file_hash(root / name),
                "path": raw.path,
                "received_at": raw.received_at.isoformat(),
                "status": raw.status,
            }
        )

    gateway = KalshiGateway(
        environment=KalshiEnvironment.PRODUCTION,
        environ={},
        clock=clock,
        capture=retain,
        transport=OutcomeTransport([c["ticker"] for c in selected], transport),
    )
    try:
        async with asyncio.timeout(90):
            for contract in selected:
                ticker = contract["ticker"]
                result["outcome_attempts"].append({"ticker": ticker, "at": now().isoformat()})
                try:
                    try:
                        market = await gateway.get_market(ticker)
                    except GatewayError:
                        if not gateway.last_capture or gateway.last_capture.status != 404:
                            raise
                        market = await gateway.get_archived_market(ticker)
                    original = Market.model_validate(contract["market"]["market"])
                    if not same_frozen_terms(market, original):
                        raise ValueError("FrozenContractTermsChanged")
                    raw = gateway.last_capture
                    if raw is None:
                        raise ValueError("MissingRawReceipt")
                    provisional = json.loads(raw.body)["market"].get("is_provisional")
                    if (
                        market.status is MarketStatus.FINALIZED
                        and market.result in {MarketResult.YES, MarketResult.NO}
                        and market.settlement_ts is not None
                        and original.close_time <= market.settlement_ts <= raw.received_at
                        and market.settlement_value
                        == (1 if market.result is MarketResult.YES else 0)
                        and provisional in {None, False}
                    ):
                        result["outcomes"].append(
                            {
                                "ticker": ticker,
                                "result": market.result.value,
                                "settled_at": market.settlement_ts.isoformat(),
                                "available_at": raw.received_at.isoformat(),
                                "receipt": receipts[-1],
                                "basis": "official binary result; no inferred scalar label",
                            }
                        )
                except (GatewayError, httpx.HTTPError, ValueError, KeyError) as exc:
                    result["outcome_failures"].append(
                        {
                            "ticker": ticker,
                            "failure": str(exc)
                            if isinstance(exc, ValueError)
                            else type(exc).__name__,
                            "at": now().isoformat(),
                        }
                    )
    except TimeoutError:
        result["outcome_failures"].append(
            {"failure": "TimeBudgetExceeded", "at": now().isoformat()}
        )
    finally:
        await gateway.aclose()
    (root / "summary.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    return result


def reservations(monitor: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    resolved = {c["ticker"] for c in monitor["contracts"] if c["outcome"] is not None}
    return tuple(
        row
        for cycle in reversed(monitor["cycles"])
        if cycle["status"] in {"completed", "failed"} and cycle["result"]
        for row in cycle["result"].get("decisions", [])
        if row["status"] == "shadow_eligible" and row["ticker"] not in resolved
    )


async def collect(
    monitor: dict[str, Any],
    repo: Path,
    root: Path,
    *,
    kalshi_transport: httpx.AsyncBaseTransport | None = None,
    source_transport: httpx.AsyncBaseTransport | None = None,
    execution_transport: httpx.AsyncBaseTransport | None = None,
    outcome_transport: httpx.AsyncBaseTransport | None = None,
    research_transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
    fee_versions: tuple[FeeVersion, ...] = (),
) -> dict[str, Any]:
    implementation = {
        name: file_hash(repo / name)
        for name in (
            "uv.lock",
            "pyproject.toml",
            "backend/src/entropytrade/execution/fee_evidence.py",
            "backend/src/entropytrade/execution/fee_policy.py",
            "backend/src/entropytrade/execution/fees.py",
            "backend/src/entropytrade/tracking/evaluate.py",
            "backend/src/entropytrade/tracking/worker.py",
            "backend/src/entropytrade/tracking/replay.py",
            "backend/src/entropytrade/tracking/models.py",
            "backend/src/entropytrade/tracking/research_features.py",
            "backend/src/entropytrade/research/paper_models.py",
            "backend/src/entropytrade/research/materialize.py",
            "backend/src/entropytrade/research/registry.py",
            "backend/src/entropytrade/research/acquire.py",
            "configs/research/sources.json",
            "backend/src/entropytrade/tracking/market_data.py",
            "backend/src/entropytrade/tracking/accounting.py",
            "backend/src/entropytrade/execution/paper.py",
            "backend/src/entropytrade/portfolio/ledger.py",
            "backend/src/entropytrade/ml/forward.py",
            "backend/src/entropytrade/ml/probability.py",
            "backend/src/entropytrade/strategies/interpret.py",
            "backend/src/entropytrade/risk/engine.py",
            "backend/src/entropytrade/families/public.py",
        )
    }
    spec = StrategySpec.model_validate(monitor["spec"])
    weather = WeatherConfig.model_validate_json(
        (repo / "configs/data/weather-forward.json").read_text()
    )
    data = await capture_public(
        root / "public",
        family=monitor["family"],
        weather=weather,
        kalshi_transport=kalshi_transport,
        source_transport=source_transport,
        clock=clock,
    )
    universe = spec.market_universe
    binding = monitor.get("model_binding")
    protected = set(data.protected_events)
    if binding and binding.get("snapshot"):
        # Invalid frozen metadata is a failed cycle, never a reason to discard its boundary.
        if binding.get("kind") == "research_weather_v1":
            portable = PortableResearchModel.model_validate(binding["snapshot"])
            protected.update(portable.protected_events)
            protected.update(
                sample.event_id
                for sample in data.samples
                if sample.family in portable.series_locations
                and f"{portable.series_locations[sample.family]['entity']}:{sample.target_date}"
                in portable.protected_events
            )
        else:
            protected.update(FrozenWeather.model_validate(binding["snapshot"]).protected_events)
    research_binding = binding is not None and binding.get("kind") == "research_weather_v1"
    window_targets = {}
    research_window_at = None
    if research_binding and binding is not None:
        at = (clock or SystemClock()).now()
        research_window_at = at.isoformat()
        window_targets = {
            series: paper_window(binding, at, series) for series in binding["snapshot"]["series"]
        }
        data = data.revalidated(
            provenance=data.provenance | {"deployment_created_at": monitor.get("created_at")}
        )
    data = data.revalidated(
        protected_events=frozenset(protected),
        samples=tuple(
            s
            for s in data.samples
            if s.event_id not in protected
            and (not research_binding or window_targets.get(s.family) == s.target_date)
            and (
                s.ticker in universe.market_tickers
                or s.event_id in universe.event_tickers
                or s.family in universe.series_tickers
            )
        ),
    )
    target_tickers = {sample.ticker for sample in data.samples}
    contracts: list[dict[str, Any]] = []
    quotes: list[dict[str, Any]] = []
    for line in (root / "public/markets.jsonl").read_text().splitlines():
        evidence = MarketEvidence.model_validate_json(line)
        market = evidence.market
        if market.event_ticker in protected or (
            research_binding and market.ticker not in target_tickers
        ):
            continue
        if not (
            market.ticker in universe.market_tickers
            or market.event_ticker in universe.event_tickers
            or market.series_ticker in universe.series_tickers
        ):
            continue
        contracts.append(
            {
                "ticker": market.ticker,
                "market": market.model_dump(mode="json", exclude_computed_fields=True),
                "raw_hash": evidence.raw_hash,
                "raw_ref": "public/" + evidence.raw_ref,
            }
        )
        raw = json.loads((root / "public" / evidence.raw_ref).read_text())
        body = next(m for m in raw["markets"] if m["ticker"] == market.ticker)
        quotes.append(
            {
                "ticker": market.ticker,
                "available_at": market.rules.captured_at.isoformat(),
                "fidelity": "unsized_listing; never executable depth",
                "yes_bid_dollars": body.get("yes_bid_dollars"),
                "yes_ask_dollars": body.get("yes_ask_dollars"),
                "raw_hash": evidence.raw_hash,
            }
        )
    known = {c["ticker"]: c for c in monitor["contracts"]}
    changes = {
        c["ticker"]
        for c in contracts
        if c["ticker"] in known
        and not same_frozen_terms(
            Market.model_validate(c["market"]),
            Market.model_validate(known[c["ticker"]]["market"]["market"]),
        )
    }
    if len(set(known) | {c["ticker"] for c in contracts}) > 128:
        raise ValueError("128-contract monitor budget reached; start a separately reviewed monitor")
    # Changed terms remain in receipts, but cannot produce a decision under frozen semantics.
    data = data.revalidated(
        samples=tuple(
            s.revalidated(rules_known=False) if s.ticker in changes else s for s in data.samples
        )
    )
    reconciliation = await outcomes(
        root / "outcomes", monitor["contracts"], transport=outcome_transport, clock=clock
    )
    market_map = {c["ticker"]: Market.model_validate(c["market"]) for c in contracts}
    research_evidence = None
    if research_binding and binding is not None:
        research_evidence = await acquire_research_features(
            root / "research-features",
            repo,
            data,
            binding,
            transport=research_transport,
            clock=clock,
        )
    data, execution = await capture_execution(
        root / "execution", data, market_map, transport=execution_transport, clock=clock
    )
    if research_evidence is not None and binding is not None:
        data = materialize_research_features(data, research_evidence, market_map, binding)
    bundle = score(spec, data, binding, market_map)
    capture = data.provenance["capture"]
    held = reservations(monitor)
    complete = (
        not capture["failures"]
        and capture["universe_complete"]
        and not execution["failures"]
        and (research_evidence is None or not research_evidence.failures)
    )
    inputs = decision_inputs(
        spec,
        data,
        bundle,
        held=held,
        acquisition_complete=complete,
        fee_versions=fee_versions,
        series_fees=tuple(execution["fee_evidence"]),
    )
    (root / "decision-inputs.json").write_text(json.dumps(inputs, sort_keys=True, indent=2))
    decisions = evaluate(
        spec,
        data,
        bundle,
        reservations=held,
        acquisition_complete=complete,
        fee_versions=fee_versions,
        series_fees=tuple(execution["fee_evidence"]),
    )
    all_contracts = {c["ticker"]: c["market"]["market"] for c in monitor["contracts"]}
    for contract in contracts:
        all_contracts.setdefault(contract["ticker"], contract["market"])
    paper_inputs = {
        "schema": "shadow-paper-inputs-v2",
        "before": monitor.get("paper_account"),
        "before_hash": account_hash(monitor.get("paper_account")),
        "decision_inputs": inputs,
        "as_of": (clock or SystemClock()).now().isoformat(),
        "event_ids": {t: m["event_ticker"] for t, m in all_contracts.items()},
        "close_times": {t: m["close_time"] for t, m in all_contracts.items()},
        "outcomes": [
            o for o in reconciliation["outcomes"] if known[o["ticker"]]["outcome"] is None
        ],
        "execution_books": {},
        "execution_series_fees": [],
    }
    paper_inputs = json.loads(json.dumps(paper_inputs))
    preview = reproduce_paper(paper_inputs)
    eligible = {d["ticker"] for d in preview["decisions"] if d["status"] == "shadow_eligible"}
    paper_execution = None
    if eligible:
        # This is local simulated execution only. Both captures remain bounded public GETs.
        await asyncio.sleep(1)
        later, paper_execution = await capture_execution(
            root / "paper-execution",
            data.revalidated(samples=tuple(s for s in data.samples if s.ticker in eligible)),
            market_map,
            transport=execution_transport,
            clock=clock,
        )
        paper_inputs["execution_books"] = {
            s.ticker: s.book.model_dump(mode="json") for s in later.samples if s.book is not None
        }
        paper_inputs["execution_series_fees"] = paper_execution["fee_evidence"]
        paper_inputs["as_of"] = (clock or SystemClock()).now().isoformat()
    paper = reproduce_paper(paper_inputs)
    (root / "paper-inputs.json").write_text(json.dumps(paper_inputs, sort_keys=True, indent=2))
    return {
        "schema": "shadow-cycle-v1",
        "submission_enabled": False,
        "detail": (
            f"{len(decisions)} shadow decisions; {len(capture['failures'])} acquisition failures"
        ),
        "data_kind": "real",
        "dataset_version": data.dataset_version,
        "feature_version": data.feature_version,
        "capture": capture,
        "contracts": contracts,
        "quotes": quotes,
        "execution": execution,
        "fee_versions": [v.summary() for v in fee_versions],
        "model_binding": binding,
        **(
            {
                "research_features": research_evidence.summary,
                "deployment_created_at": monitor.get("created_at"),
                "research_window_at": research_window_at,
            }
            if research_evidence is not None
            else {}
        ),
        "decisions": decisions,
        "paper": paper,
        "paper_inputs": paper_inputs,
        "paper_execution": paper_execution,
        "model_refusals": bundle.refusals,
        "model_source_hash": bundle.source_hash,
        "risk_limits": shadow_limits().model_dump(mode="json"),
        "implementation": implementation,
        "changed_terms": sorted(changes),
        **reconciliation,
        "limitations": [
            *data.provenance["limitations"],
            "Observed shadow evidence and simulated paper account are separate. "
            "No exchange submissions, observed fills or profitability claim.",
            "Frozen research candidate is not approved or promoted. "
            "Only compatible data-only frozen weather models can score forward evidence.",
            "Only server-reviewed point-in-time document evidence can certify fees; "
            "series fields alone cannot.",
            "Outcome receipt clocks never rewrite earlier decisions or protected partitions.",
        ],
    }


def execute(store: TrackingStore, repo: Path, monitor_id: str, cycle_id: str) -> None:
    monitor = store.get(monitor_id, export=True)
    if (
        not monitor
        or monitor["status"] != "active"
        or not any(c["id"] == cycle_id and c["status"] == "running" for c in monitor["cycles"])
    ):
        return
    root = store.jobs.root / "shadow" / identifier(monitor_id) / identifier(cycle_id)
    root.mkdir(parents=True, exist_ok=False)
    try:
        result = asyncio.run(
            collect(monitor, repo, root, fee_versions=FeeEvidenceStore(store.jobs.root).snapshot())
        )
        failed = bool(
            result["capture"]["failures"]
            or result["outcome_failures"]
            or result.get("execution", {}).get("failures")
            or (result.get("paper_execution") or {}).get("failures")
            or (result.get("research_features") or {}).get("failures")
        )
    except Exception as exc:  # noqa: BLE001 - worker records a fail-closed bounded cycle
        result = {
            "detail": "Shadow cycle failed: " + type(exc).__name__,
            "failure": str(exc)[:1000],
            "submission_enabled": False,
        }
        failed = True
    result["artifacts"] = [
        {"path": p.relative_to(root).as_posix(), "sha256": file_hash(p), "bytes": p.stat().st_size}
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    store.finish(monitor_id, cycle_id, result, failed=failed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--monitor", required=True)
    parser.add_argument("--cycle", required=True)
    args = parser.parse_args()
    store = TrackingStore(Jobs(workspace_path(args.repo, args.workspace)))
    execute(store, args.repo, identifier(args.monitor), identifier(args.cycle))


if __name__ == "__main__":
    main()
