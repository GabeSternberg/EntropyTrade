"""Public read-only SDK acquisition into immutable, replayable source receipts."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from entropytrade.data.schema import DatasetConfig, MarketEvidence, MarketState
from entropytrade.data.sources import days, file_hash, stamp
from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.historical import ApiOrigin

if TYPE_CHECKING:
    from entropytrade.domain.market import Market
from entropytrade.domain.time import utc_now
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.storage.recorder import Recorder


async def acquire(root: Path, config: DatasetConfig) -> None:
    """No credentials, no implicit environment auth. Fail rather than overwrite evidence."""
    root.mkdir(parents=True, exist_ok=False)
    raw_dir = root / "raw"
    raw_dir.mkdir()
    receipt_store = Recorder(root / "acquisition.sqlite")
    last: tuple[str, str, datetime] | None = None
    counter = 0
    market_refs: dict[str, tuple[str, str, datetime, dict[str, object]]] = {}

    def capture(raw: RawCapture) -> None:
        nonlocal last, counter
        counter += 1
        name = f"raw/{counter:06d}.json"
        path = root / name
        path.write_bytes(raw.body)
        receipt_store.record_http(
            path=raw.path, status=raw.status, body=raw.body, received_at=raw.received_at
        )
        last = name, file_hash(path), raw.received_at
        body = json.loads(raw.body)
        for item in body.get("markets", []):
            market_refs[item["ticker"]] = (*last, item)

    gateway = KalshiGateway(
        environment=KalshiEnvironment.PRODUCTION, capture=capture, wait_for_budget=True
    )
    markets: list[MarketEvidence] = []
    states: list[MarketState] = []
    failures: list[dict[str, str]] = []
    try:
        for location in config.locations:
            for day in days(config.start, config.end):
                # Daily-high event convention selects the event, never a strike. The
                # response discovers its actual contracts; a missing event stays missing.
                event = location.series + "-" + day.strftime("%y%b%d").upper()
                found: dict[str, Market] = {}
                origins: dict[str, ApiOrigin] = {}
                for origin in (ApiOrigin.LIVE, ApiOrigin.HISTORICAL):
                    try:
                        batch = await gateway.list_markets(
                            series_ticker=location.series, event_ticker=event, origin=origin
                        )
                    except GatewayError as exc:
                        failures.append(
                            {"event": event, "origin": origin.value, "error": type(exc).__name__}
                        )
                        continue
                    # Capture each response's actual raw references, even with pagination.
                    for market in batch:
                        found[market.ticker] = market
                        origins[market.ticker] = origin
                for market in found.values():
                    # Locate the exact retained response containing this ticker.
                    ref = market_refs.get(market.ticker)
                    if ref is None:
                        raise ValueError("market has no retained raw receipt")
                    market = market.revalidated(rules=market.rules.revalidated(captured_at=ref[2]))
                    markets.append(
                        MarketEvidence(
                            market=market,
                            created_at=stamp(ref[3].get("created_time")),
                            capture_basis="receipt",
                            raw_ref=ref[0],
                            raw_hash=ref[1],
                        )
                    )
                    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
                    try:
                        candles = await gateway.get_candles(
                            market.ticker,
                            series=location.series,
                            start=start,
                            end=start + timedelta(days=2),
                            historical=origins[market.ticker] is ApiOrigin.HISTORICAL,
                        )
                    except GatewayError as exc:
                        failures.append({"market": market.ticker, "error": type(exc).__name__})
                        continue
                    if last is None:
                        raise ValueError("candle request has no receipt")
                    for candle in candles:
                        end_ts = candle.get("end_period_ts")
                        if not isinstance(end_ts, int):
                            raise ValueError("candle has no end time")
                        states.append(
                            MarketState(
                                market_ticker=market.ticker,
                                event_time=datetime.fromtimestamp(end_ts, tz=UTC),
                                received_at=last[2],
                                fidelity="candle",
                                payload=candle,
                                raw_ref=last[0],
                                raw_hash=last[1],
                            )
                        )
        (root / "markets.jsonl").write_text(
            "".join(m.model_dump_json(exclude_computed_fields=True) + "\n" for m in markets),
            encoding="utf-8",
        )
        (root / "market_states.jsonl").write_text(
            "".join(s.model_dump_json() + "\n" for s in states), encoding="utf-8"
        )
        (root / "acquisition.json").write_text(
            json.dumps(
                {
                    "retrieved_at": utc_now().isoformat(),
                    "markets": len(markets),
                    "states": len(states),
                    "failures": failures,
                },
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        await gateway.aclose()
        receipt_store.close()
