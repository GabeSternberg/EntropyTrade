"""Deterministic, isolated snapshot-taker paper accounting. Never calls an exchange.

Decisions use existing gates/DSL/risk. Execution requires a later receipt, at least one
second of latency, current certified fees and a second risk check. Unknown queues cancel.
An identical sized payload/sequence never replenishes consumed liquidity in this account.
"""

import argparse
import json
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from heapq import heapify, heappop, heappush
from pathlib import Path
from typing import Any
from uuid import UUID

from entropytrade.backtest.replay import clamp_to_decision
from entropytrade.domain.enums import LiquidityRole, MarketResult, OutcomeSide, TimeInForce
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import ZERO
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.strategy import StrategySpec
from entropytrade.execution.fee_evidence import FeeVersion, select_fee
from entropytrade.execution.fees import trade_fee
from entropytrade.execution.paper import PaperBroker
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.features.registry import scientific_hash
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, seal
from entropytrade.tracking.evaluate import evaluate, shadow_limits

LATENCY = timedelta(seconds=1)


def account_hash(state: dict[str, Any] | None) -> str:
    return scientific_hash(state)


def summary(state: dict[str, Any] | None) -> dict[str, Any]:
    if state is None:
        return {"status": "not_started", "reason": "No committed paper cycle; no retroactive fills"}
    ledger = Ledger.load(state["ledger"])
    return {
        "status": "simulated",
        "data_kind": state["data_kind"],
        "starting_cash": str(ledger.starting_cash),
        "cash": str(ledger.cash),
        "available_cash": str(ledger.available_cash),
        "fees": str(ledger.fees_paid),
        "realized_pnl": str(ledger.realized_pnl),
        "equity_at_cost": str(ledger.equity()),
        "positions": [p.model_dump(mode="json") for p in ledger.positions],
        "fill_count": len(ledger.fills()),
        "settlement_count": len(state["ledger"]["settlements"]),
        "as_of": ledger.as_of.isoformat(),
        "state_hash": account_hash(state),
        "limitation": "Per-monitor simulated $1000 account; open positions valued at cost. "
        "No observed fills, mark-to-market return or profitability claim.",
    }


def _capacity(
    book: OrderBook, liquidity: dict[str, Any], side: OutcomeSide
) -> tuple[str, OrderBook]:
    name = "asks" if side is OutcomeSide.YES else "bids"
    levels = book.asks if side is OutcomeSide.YES else book.bids
    key = scientific_hash(
        {
            "ticker": book.market_ticker,
            "side": name,
            "levels": [x.model_dump(mode="json") for x in levels],
            "sequence": book.sequence,
        }
    )
    remaining = OrderBook.model_validate(liquidity.get(key, book.model_dump(mode="json")))
    return key, book.revalidated(**{name: remaining.asks if name == "asks" else remaining.bids})


def _consume(book: OrderBook, fills: list[Any]) -> OrderBook:
    # Consume exact raw price levels, before the price-improvement clamp.
    for fill in fills:
        remaining = fill.quantity
        levels = book.asks if fill.contract.side is OutcomeSide.YES else book.bids
        updated = []
        for level in levels:
            taken = min(remaining, level.quantity)
            remaining -= taken
            if level.quantity > taken:
                updated.append(level.revalidated(quantity=level.quantity - taken))
        book = book.revalidated(
            **{"asks" if fill.contract.side is OutcomeSide.YES else "bids": tuple(updated)}
        )
    return book


def reproduce(inputs: dict[str, Any]) -> dict[str, Any]:
    """Replay one cycle from frozen JSON, including its pre-cycle account; no I/O."""
    if inputs["schema"] != "shadow-paper-inputs-v1":
        raise ValueError("unknown paper schema")
    before = inputs["before"]
    if account_hash(before) != inputs["before_hash"]:
        raise ValueError("paper previous-state checksum mismatch")
    decision_inputs = inputs["decision_inputs"]
    spec = StrategySpec.model_validate(decision_inputs["spec"])
    data = ExperimentData.model_validate(decision_inputs["data"])
    bundle = PredictionBundle.model_validate(decision_inputs["bundle"])
    versions = tuple(FeeVersion.model_validate(v) for v in decision_inputs.get("fee_versions", []))
    end = datetime.fromisoformat(inputs["as_of"])
    start = min((s.decision_time for s in data.samples), default=end)
    if end < start:
        raise ValueError("paper cycle clock precedes decision")
    if before is not None:
        if before["schema"] != "shadow-paper-state-v1" or before["data_kind"] != data.data_kind:
            raise ValueError("paper account provenance/schema mismatch")
        ledger = Ledger.load(before["ledger"])
        if ledger.as_of > start:
            raise ValueError("paper decision precedes committed account clock")
        liquidity = json.loads(json.dumps(before["liquidity"]))
        resolved = dict(before["resolved"])
    else:
        ledger = Ledger(shadow_limits().bankroll, as_of=start)
        liquidity, resolved = {}, {}
    event_ids = {**(before or {}).get("event_ids", {})}
    for ticker, event_id in inputs["event_ids"].items():
        if ticker in event_ids and event_ids[ticker] != event_id:
            raise ValueError("paper contract event changed")
        event_ids[ticker] = event_id
    close_times = {
        key: datetime.fromisoformat(value) for key, value in inputs["close_times"].items()
    }
    books = {
        key: OrderBook.model_validate(value) for key, value in inputs["execution_books"].items()
    }
    # Ordered by availability, never the exchange's earlier settlement timestamp.
    events: list[tuple[datetime, int, str, Any]] = []
    seen_outcomes: dict[str, str] = {}
    for outcome in sorted(inputs["outcomes"], key=lambda o: o["available_at"]):
        available = datetime.fromisoformat(outcome["available_at"])
        settled = datetime.fromisoformat(outcome["settled_at"])
        ticker = outcome["ticker"]
        if (
            outcome["result"] not in {"yes", "no"}
            or ticker not in close_times
            or not close_times[ticker] <= settled <= available <= end
            or outcome["receipt"]["received_at"] != outcome["available_at"]
            or outcome["receipt"]["status"] != 200
        ):
            raise ValueError("invalid paper official outcome availability/semantics")
        if ticker in seen_outcomes:
            if seen_outcomes[ticker] != outcome["result"]:
                raise ValueError("conflicting paper settlement")
            continue
        seen_outcomes[ticker] = outcome["result"]
        events.append((max(ledger.as_of, available), 0, ticker, outcome))
    events.extend((s.decision_time, 1, s.ticker, s) for s in data.samples)
    decisions, executions, settlements = [], [], []
    engine = RiskEngine(shadow_limits().revalidated(min_net_edge=spec.minimum_edge))
    # Current live cycles have one decision per ticker. Reject ambiguous execution bindings.
    if len({s.ticker for s in data.samples}) != len(data.samples):
        raise ValueError("one paper decision per ticker per cycle required")
    pending: dict[str, dict[str, Any]] = {}
    heapify(events)
    while events:
        when, kind, ticker, payload = heappop(events)
        if when > end:
            raise ValueError("paper event after cycle clock")
        if kind == 0:
            prior = resolved.get(ticker)
            if prior and prior["result"] != payload["result"]:
                raise ValueError("conflicting paper settlement")
            if prior:
                continue
            if ledger.position(ticker) is not None:
                settled_row = ledger.settle(ticker, MarketResult(payload["result"]), at=when)
                settlements.append(
                    {"settlement": settled_row.model_dump(mode="json"), "observed_outcome": payload}
                )
            resolved[ticker] = payload
            continue
        if kind == 1:
            rows = evaluate(
                spec,
                data.revalidated(samples=(payload,)),
                bundle,
                fee_versions=versions,
                series_fees=tuple(decision_inputs.get("series_fees", [])),
                acquisition_complete=decision_inputs["acquisition_complete"],
                ledger=ledger,
                event_ids=event_ids,
                reservations=tuple(pending.values()),
            )
            decisions.extend(rows)
            if not rows or rows[0]["status"] != "shadow_eligible":
                continue
            row = rows[0]
            book = books.get(ticker)
            fill_at = book.received_at if book is not None else when
            if book is None or not when + LATENCY <= fill_at <= end:
                executions.append(
                    {
                        "ticker": ticker,
                        "decision_hash": row["decision_hash"],
                        "status": "blocked",
                        "reason": "missing_later_sized_book",
                        "fills": [],
                    }
                )
                continue
            intent = OrderIntent.model_validate(row["intent"])
            reserve = intent.max_cost + (
                intent.edge.fee_per_contract * intent.quantity if intent.edge else ZERO
            )
            ledger.reserve(intent.intent_id, reserve)
            pending[ticker] = {"intent": row["intent"], "event_id": payload.event_id}
            heappush(events, (fill_at, 2, ticker, (payload, row)))
            continue
        payload, row = payload
        intent = OrderIntent.model_validate(row["intent"])
        ledger.release(intent.intent_id)
        pending.pop(ticker)
        when = payload.decision_time
        audit: dict[str, Any] = {
            "ticker": ticker,
            "decision_hash": row["decision_hash"],
            "status": "blocked",
            "reason": None,
            "fills": [],
        }
        executions.append(audit)
        book = books.get(ticker)
        # Fill clock is the later sized receipt, with fixed minimum latency. No future/as-of join.
        fill_at = book.received_at if book is not None else end
        if ticker in resolved or fill_at >= payload.close_time:
            audit["reason"] = "closed_or_resolved"
            continue
        if ledger.order(intent.intent_id) is not None:
            audit["reason"] = "duplicate_intent"
            continue
        if book is None or not when + LATENCY <= fill_at <= end:
            audit["reason"] = "missing_later_sized_book"
            continue
        if (
            book.market_ticker != ticker
            or book.is_crossed
            or (book.exchange_ts is not None and book.exchange_ts > fill_at)
        ):
            audit["reason"] = "invalid_execution_book"
            continue
        # A settlement received before execution cancels the intent even if decision was earlier.
        if any(
            o["ticker"] == ticker and datetime.fromisoformat(o["available_at"]) <= fill_at
            for o in inputs["outcomes"]
        ):
            audit["reason"] = "closed_or_resolved"
            continue
        fee, fee_audit = select_fee(
            versions, series=payload.family, when=fill_at, data_kind=data.data_kind
        )
        audit.update(
            executed_at=fill_at.isoformat(),
            fee_evidence=fee_audit,
            observed_book=book.model_dump(mode="json"),
        )
        if fee is None:
            audit["reason"] = fee_audit["reason"]
            continue
        if any(
            r["series"] == payload.family
            and (
                r["fee_type"] != fee.schedule.fee_type.value
                or Decimal(r["fee_multiplier"]) != fee.schedule.fee_multiplier
            )
            for r in inputs.get("execution_series_fees", [])
        ):
            audit["reason"] = "series_metadata_conflict"
            continue
        key, remaining = _capacity(book, liquidity, intent.contract.side)
        decision_book = OrderBook.model_validate(row["quote"])
        fill_book = clamp_to_decision(decision_book, remaining)
        levels = fill_book.asks if intent.contract.side is OutcomeSide.YES else fill_book.bids
        if not levels:
            audit["reason"] = "liquidity_exhausted"
            continue
        estimate = trade_fee(
            fee.schedule,
            yes_price=Decimal(".5"),
            quantity=intent.quantity,
            role=LiquidityRole.TAKER,
        ) + max(0, len(levels) - 1) * Decimal(".01")
        if intent.edge is not None:
            intent = intent.revalidated(
                edge=intent.edge.revalidated(
                    fee_per_contract=(estimate / intent.quantity).quantize(
                        Decimal(".000001"), rounding=ROUND_CEILING
                    )
                )
            )
        event_cost = sum(
            (
                p.total_cost + p.fees_paid
                for p in ledger.positions
                if event_ids.get(p.contract.market_ticker) == payload.event_id
            ),
            ZERO,
        )
        deployed = sum((p.total_cost + p.fees_paid for p in ledger.positions), ZERO)
        risk = engine.evaluate(
            intent,
            portfolio=ledger.snapshot(),
            book=fill_book,
            now=fill_at,
            event_deployed=event_cost,
            realized_pnl=ledger.realized_pnl,
            peak_equity=ledger.peak_equity,
            equity=ledger.equity(),
            model_as_of=datetime.fromisoformat(row["prediction"]["fitted_before"]),
        )
        risk = risk.revalidated(
            decision_id=UUID(
                scientific_hash(
                    {
                        "intent": intent.model_dump(mode="json"),
                        "risk": risk.model_dump(mode="json", exclude={"decision_id"}),
                    }
                ).removeprefix("sha256:")[:32]
            )
        )
        audit["risk"] = risk.model_dump(mode="json")
        cost = intent.max_cost + estimate
        limits = shadow_limits()
        if (
            not risk.approved
            or cost > min(limits.per_trade, ledger.available_cash)
            or cost + event_cost > limits.per_event
            or cost + deployed > limits.total_deployed
        ):
            audit["reason"] = "execution_risk_rejected"
            continue
        if (
            intent.time_in_force is TimeInForce.FILL_OR_KILL
            and risk.approved_quantity != intent.quantity
        ):
            audit["reason"] = "insufficient_fok_capacity"
            continue
        broker = PaperBroker(ledger, fee.schedule)
        prior_fills = {f.fill_id for f in ledger.fills()}
        order = broker.submit(seal(intent, risk), fill_book, now=fill_at)
        if not order.state.is_terminal:
            order = broker.cancel(order.client_order_id, now=fill_at)
        fresh = [f for f in ledger.fills() if f.fill_id not in prior_fills]
        liquidity[key] = _consume(remaining, fresh).model_dump(mode="json")
        audit.update(
            status=order.state.value,
            intended_quantity=str(intent.quantity),
            approved_quantity=str(risk.approved_quantity),
            unsubmitted_quantity=str(intent.quantity - risk.approved_quantity),
            order=order.model_dump(mode="json"),
            fills=[f.model_dump(mode="json") for f in fresh],
            liquidity_key=key,
            simulated_book=fill_book.model_dump(mode="json"),
        )
    ledger.as_of = end
    state = {
        "schema": "shadow-paper-state-v1",
        "data_kind": data.data_kind,
        "ledger": ledger.dump(),
        "liquidity": liquidity,
        "resolved": resolved,
        "event_ids": event_ids,
    }
    result = {
        "schema": "shadow-paper-cycle-v1",
        "before_hash": inputs["before_hash"],
        "state": state,
        "state_hash": account_hash(state),
        "summary": summary(state),
        "decisions": decisions,
        "executions": executions,
        "settlements": settlements,
        "submission_enabled": False,
    }
    return json.loads(json.dumps(result))  # type: ignore[no-any-return]


def verify_export(value: dict[str, Any]) -> dict[str, Any]:
    """Verify the portable account chain independently from the local database."""
    previous = None
    count = 0
    for cycle in sorted(value["cycles"], key=lambda c: c["sequence"]):
        if not cycle.get("result") or "paper" not in cycle["result"]:
            continue
        result = cycle["result"]
        if scientific_hash(result) != cycle["digest"]:
            raise ValueError("paper cycle checksum mismatch")
        inputs = result["paper_inputs"]
        if inputs["before_hash"] != account_hash(previous):
            raise ValueError("broken paper account chain")
        actual = reproduce(inputs)
        if actual != result["paper"]:
            raise ValueError("paper replay differs from committed cycle")
        previous = actual["state"]
        count += 1
    if value["paper_account"] != previous:
        raise ValueError("paper final account differs")
    return {
        "verified": True,
        "paper_cycles": count,
        "state_hash": account_hash(previous),
        "submission_enabled": False,
        "limitation": "Accounting replay, not source certification",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_export(json.loads(args.export.read_text())), sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
