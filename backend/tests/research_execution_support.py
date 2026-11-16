"""Declared synthetic acquired market evidence for full persistent modeling/replay tests.

Books use forecasts rather than realized outcomes. Every record retains original bytes and
receipt clocks. Controlled fee certificates apply solely to synthetic experiments.
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.data.schema import MarketEvidence, MarketState
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus, MarketType, StrikeType
from entropytrade.domain.market import (
    Market,
    MarketRules,
    PriceRange,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import RawStore
from entropytrade.research.model import HypothesisSpec
from tests.fee_support import controlled_fee


def execution_fixture(
    root: Path,
    spec: HypothesisSpec,
    artifacts: list[dict[str, Any]],
    *,
    execution_delay_seconds: float | None = None,
) -> tuple[str, tuple[FeeVersion, ...]]:
    """Retain full typed synthetic market/rule/book/outcome evidence alongside features."""
    features: dict[str, dict[str, Any]] = {}
    labels = {}
    for artifact in artifacts:
        path = root / "features" / ("sha256-" + artifact["artifact_id"].removeprefix("sha256:"))
        rows = [json.loads(line) for line in (path / "values.jsonl").read_text().splitlines()]
        if artifact["feature_id"] == "nws_pfm_max_f":
            for row in rows:
                previous = features.get(row["target_date"])
                if previous is None or row["decision_time"] < previous["decision_time"]:
                    features[row["target_date"]] = row
        elif artifact["feature_id"] == "settlement_high_f":
            labels = {row["target_date"]: row for row in rows}
    raw_store = RawStore(root)
    records = []
    receipts = []

    def retain(payload: Any, clock: datetime) -> tuple[str, str]:
        body = json.dumps(payload, sort_keys=True).encode()
        digest = raw_store.put(body)
        receipts.append({"sha256": digest, "received_at": clock.isoformat()})
        return "synthetic:" + digest, digest

    for day_string, row in sorted(features.items()):
        day = date.fromisoformat(day_string)
        decision = datetime.fromisoformat(row["decision_time"])
        label = labels[day_string]
        label_at = datetime.fromisoformat(label["inputs_available_at"])
        forecast = Decimal(row["value"])
        strike = Strike(strike_type=StrikeType.GREATER, floor=forecast - 3)
        event = spec.universe[0] + "-" + day.strftime("%y%b%d").upper()
        ticker = event + "-T" + str(strike.floor)
        rules = MarketRules(
            market_ticker=ticker,
            rules_primary=(
                "SYNTHETIC highest temperature in Fahrenheit at CLIPHL Philadelphia, "
                "according to The Weather Company, greater than the stated threshold."
            ),
            settlement_sources=(SettlementSource(name="The Weather Company"),),
            settlement_basis="contract_text",
            settlement_target_date=day,
            captured_at=decision - timedelta(hours=1),
        )
        market = Market(
            ticker=ticker,
            event_ticker=event,
            series_ticker=spec.universe[0],
            market_type=MarketType.BINARY,
            title="SYNTHETIC Philadelphia daily high",
            status=MarketStatus.ACTIVE,
            open_time=decision - timedelta(hours=24),
            close_time=datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
            + timedelta(hours=5),
            strike=strike,
            rules=rules,
            tick_schedule=TickSchedule(
                ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal(".01")),)
            ),
        )
        for final in (False, True):
            captured_at = label_at if final else rules.captured_at
            found = (
                market
                if not final
                else market.revalidated(
                    status=MarketStatus.FINALIZED,
                    result=MarketResult.YES
                    if strike.resolves_yes(Decimal(label["value"]))
                    else MarketResult.NO,
                    rules=rules.revalidated(captured_at=captured_at),
                )
            )
            raw_ref, raw_hash = retain(found.model_dump(mode="json"), captured_at)
            evidence = MarketEvidence(
                market=found,
                created_at=market.open_time,
                capture_basis="receipt",
                raw_ref=raw_ref,
                raw_hash=raw_hash,
            )
            records.append({"record_type": "market_evidence", **evidence.model_dump(mode="json")})
        book = OrderBook(
            market_ticker=ticker,
            received_at=decision,
            bids=(OrderBookLevel(price=Decimal(".30"), quantity=Decimal(5)),),
            asks=(OrderBookLevel(price=Decimal(".35"), quantity=Decimal(5)),),
        )
        raw_ref, raw_hash = retain(book.model_dump(mode="json"), decision)
        state = MarketState(
            market_ticker=ticker,
            event_time=decision,
            available_at=decision,
            received_at=decision,
            fidelity="order_book",
            payload=book.model_dump(mode="json"),
            raw_ref=raw_ref,
            raw_hash=raw_hash,
        )
        records.append({"record_type": "market_state", **state.model_dump(mode="json")})
        if execution_delay_seconds is not None:
            execution_at = decision + timedelta(seconds=execution_delay_seconds)
            if execution_at <= decision or execution_at >= market.close_time:
                raise ValueError("controlled execution receipt must follow decision before close")
            execution_book = book.revalidated(received_at=execution_at)
            raw_ref, raw_hash = retain(execution_book.model_dump(mode="json"), execution_at)
            execution_state = state.revalidated(
                event_time=execution_at,
                available_at=execution_at,
                received_at=execution_at,
                payload=execution_book.model_dump(mode="json"),
                raw_ref=raw_ref,
                raw_hash=raw_hash,
            )
            records.append(
                {"record_type": "market_state", **execution_state.model_dump(mode="json")}
            )
    staging = root / ".synthetic-execution-dataset"
    staging.mkdir()
    (staging / "records.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    )
    (staging / "receipts.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in receipts)
    )
    (staging / "parameters.json").write_text(
        json.dumps({"fixture": "synthetic-acquired-execution-v1"})
    )
    hashes = {
        name: file_hash(staging / name)
        for name in ("records.jsonl", "receipts.jsonl", "parameters.json")
    }
    identifier = scientific_hash(hashes)
    (staging / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": identifier,
                "checksums": hashes,
                "data_kind": "synthetic",
                "raw_hashes": sorted({r["sha256"] for r in receipts}),
            }
        )
    )
    target = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
    if target.exists():
        import shutil

        shutil.rmtree(staging)
    else:
        staging.rename(target)
    fee = controlled_fee()
    at = datetime(2025, 1, 1, tzinfo=UTC)
    fee = fee.revalidated(
        series=spec.universe,
        policy=fee.policy.revalidated(
            effective_from=at, effective_to=datetime(2027, 1, 1, tzinfo=UTC)
        )
        if fee.policy
        else None,
    )
    return identifier, (fee,)
