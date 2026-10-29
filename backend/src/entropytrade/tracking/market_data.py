"""Bounded exact public book/series GETs. No fee coefficient is inferred from series fields."""

import asyncio
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from entropytrade.data.sources import file_hash
from entropytrade.domain.market import Market
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.exchange.kalshi.recorded import public_book_from_body, series_from_body
from entropytrade.exchange.kalshi.transport import ObservingTransport, RawCapture
from entropytrade.experiments.data import ExperimentData
from entropytrade.families.public import BoundedTransport
from entropytrade.features.registry import scientific_hash

if TYPE_CHECKING:
    from entropytrade.domain.market_data import OrderBook


class ShadowTransport(BoundedTransport):
    def __init__(self, paths: set[str], inner: httpx.AsyncBaseTransport | None) -> None:
        super().__init__(inner)
        self.paths = paths

    def permits_path(self, url: httpx.URL) -> bool:
        return url.host == "api.elections.kalshi.com" and url.path in self.paths


async def capture_execution(
    root: Path,
    data: ExperimentData,
    markets: dict[str, Market],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> tuple[ExperimentData, dict[str, Any]]:
    root.mkdir()
    now = (clock or SystemClock()).now
    # Fixed caps bound both request count (<=20) and exposure to an expanding universe.
    selected = sorted(data.samples, key=lambda s: s.ticker)[:10]
    series = sorted({markets[s.ticker].series_ticker or "" for s in selected})
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", s.ticker) for s in selected) or any(
        not ticker or not re.fullmatch(r"[A-Za-z0-9_-]+", ticker) for ticker in series
    ):
        raise ValueError("unsafe market/series identifier")
    paths = {f"/trade-api/v2/markets/{s.ticker}/orderbook" for s in selected} | {
        f"/trade-api/v2/series/{ticker}" for ticker in series
    }
    receipts: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    books: dict[str, OrderBook] = {}
    fees: list[dict[str, Any]] = []

    def retain(raw: RawCapture) -> None:
        name = f"{len(receipts):04d}.json"
        (root / name).write_bytes(raw.body)
        receipts.append(
            {
                "raw_ref": "execution/" + name,
                "sha256": file_hash(root / name),
                "received_at": raw.received_at.isoformat(),
                "path": raw.path,
                "status": raw.status,
            }
        )

    observed = ObservingTransport(ShadowTransport(paths, transport), capture=retain, clock=clock)
    client = httpx.AsyncClient(
        transport=observed,
        timeout=10,
        trust_env=False,
        follow_redirects=False,
        base_url="https://api.elections.kalshi.com",
    )
    try:
        async with asyncio.timeout(60):
            for ticker in series:
                try:
                    response = await client.get(f"/trade-api/v2/series/{ticker}")
                    response.raise_for_status()
                    row = series_from_body(response.json()["series"])
                    raw = observed.last
                    if raw is None or row.ticker != ticker:
                        raise ValueError("Missing matching series receipt")
                    body = json.loads(raw.body)["series"]
                    fees.append(
                        {
                            "series": ticker,
                            "fee_type": row.fee_type.value,
                            "fee_multiplier": str(row.fee_multiplier),
                            "metadata_updated_at": body.get("last_updated_ts"),
                            "available_at": raw.received_at.isoformat(),
                            "receipt": receipts[-1],
                            "version": scientific_hash({"receipt": receipts[-1], "series": ticker}),
                            "certified": False,
                            "reason": "Series fields do not certify the quadratic coefficient or "
                            "its effective interval; no fee schedule substituted",
                        }
                    )
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    failures.append(
                        {
                            "source": ticker,
                            "failure": type(exc).__name__,
                            "failed_at": now().isoformat(),
                        }
                    )
            for sample in selected:
                try:
                    response = await client.get(f"/trade-api/v2/markets/{sample.ticker}/orderbook")
                    response.raise_for_status()
                    raw = observed.last
                    if raw is None:
                        raise ValueError("Missing book receipt")
                    book = public_book_from_body(
                        response.json(), ticker=sample.ticker, received_at=raw.received_at
                    )
                    if book.market_ticker != sample.ticker:
                        raise ValueError("Book contract identity mismatch")
                    books[sample.ticker] = book
                except (httpx.HTTPError, ValueError) as exc:
                    failures.append(
                        {
                            "source": sample.ticker,
                            "failure": type(exc).__name__,
                            "failed_at": now().isoformat(),
                        }
                    )
    except TimeoutError:
        failures.append(
            {"source": "execution", "failure": "TimeBudgetExceeded", "failed_at": now().isoformat()}
        )
    finally:
        await client.aclose()
    decision = now()
    if any(s.decision_time > decision for s in data.samples):
        raise ValueError("execution clock precedes source capture")
    samples = []
    for sample in data.samples:
        features = {
            **sample.features,
            "hours_to_close": Decimal(str((sample.close_time - decision).total_seconds()))
            / Decimal(3600),
        }
        captured_book = books.get(sample.ticker)
        samples.append(
            sample.revalidated(
                decision_time=decision,
                features=features,
                book=captured_book,
                fidelity="order_book" if captured_book is not None else "missing",
                feature_hash=scientific_hash(
                    {
                        "source_features": sample.feature_hash,
                        "decision": decision.isoformat(),
                        "features": {k: str(v) for k, v in features.items()},
                    }
                ),
            )
        )
    evidence = {
        "receipts": receipts,
        "failures": failures,
        "fee_evidence": fees,
        "book_count": len(books),
        "deferred_tickers": sorted({s.ticker for s in data.samples} - {s.ticker for s in selected}),
        "decision_time": decision.isoformat(),
        "submission_enabled": False,
    }
    (root / "summary.json").write_text(json.dumps(evidence, sort_keys=True, indent=2))
    return data.revalidated(samples=tuple(samples)), evidence
