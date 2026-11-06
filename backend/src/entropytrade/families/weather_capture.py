"""Public-family capture that retains each response body once (capture layout v2).

``families/public.py`` is deliberately left byte-for-byte unchanged: ``forward_data`` binds
every capture's ``feature_version`` to that file's hash, so editing it would invalidate the
verification of every retained shadow cycle. Its ``capture_public`` remains for reference;
collectors use this module. Captures written here verify through the same ``forward_data``.
"""

import asyncio
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from entropytrade.data.schema import MarketEvidence, Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import KalshiEnvironment, MarketStatus
from entropytrade.domain.time import Clock, SystemClock, ensure_utc
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.experiments.data import ExperimentData
from entropytrade.families.public import BoundedTransport, bitcoin_rules, forward_data
from entropytrade.features.registry import scientific_hash
from entropytrade.storage.forecast_archive import ForecastArchive
from entropytrade.weather.collection import WeatherConfig, poll_weather

if TYPE_CHECKING:
    from entropytrade.domain.market import Market

WEATHER_LEDGER = "entropytrade-weather-receipts-v1"


def retain_weather(
    archive: ForecastArchive,
    scratch: Path,
    root: Path,
    receipts: list[dict[str, Any]],
) -> tuple[list[Observation], dict[str, Any]]:
    """Export forecast observations that cite the capture's own exact raw response bytes.

    Every weather response is already retained byte-for-byte under ``raw/`` by the transport
    callback, so each observation's ``raw_ref`` points there (same bytes, same hash). Only a
    body with no identical retained response is copied to ``weather/raw/``. The receipt ledger
    keeps each receipt's URL, clocks, body hash and the vintage or failure it produced; the
    archive database itself is not retained. Availability clocks are unchanged.
    """
    archive.export(scratch)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        by_hash.setdefault(str(receipt["hash"]), []).append(receipt)

    def retained(sha256: str, url: str | None) -> str | None:
        matches = by_hash.get(sha256, [])
        exact = [r for r in matches if r["path"] == url]
        chosen = (exact or matches)[:1]
        return str(chosen[0]["raw_ref"]) if chosen else None

    rows = archive.receipt_ledger()
    urls = {row["receipt_id"]: row["url"] for row in rows}
    weather_dir = root / "weather"
    weather_dir.mkdir()
    observations = []
    for line in (scratch / "observations.jsonl").read_text().splitlines():
        item = Observation.model_validate_json(line)
        receipt_id = item.raw_ref.removeprefix("raw/").removesuffix(".json")
        reference = retained(str(item.raw_hash), urls.get(receipt_id))
        if reference is None:
            copy = weather_dir / item.raw_ref
            copy.parent.mkdir(exist_ok=True)
            if not copy.exists():
                shutil.copyfile(scratch / item.raw_ref, copy)
            reference = "weather/" + item.raw_ref
            by_hash.setdefault(str(item.raw_hash), []).append(
                {"hash": item.raw_hash, "path": urls.get(receipt_id), "raw_ref": reference}
            )
        if file_hash(root / reference) != item.raw_hash:
            raise ValueError("weather observation lacks its exact retained response")
        observations.append(item.revalidated(raw_ref=reference))
    ledger = []
    for row in rows:
        body = str(row.pop("body")).encode("utf-8")
        sha256 = "sha256:" + hashlib.sha256(body).hexdigest()
        ledger.append({**row, "sha256": sha256, "raw_ref": retained(sha256, row["url"])})
    summary = json.loads((scratch / "manifest.json").read_text())
    (weather_dir / "manifest.json").write_text(json.dumps(summary, sort_keys=True, indent=2))
    (weather_dir / "receipts.json").write_text(
        json.dumps({"schema": WEATHER_LEDGER, "receipts": ledger}, sort_keys=True, indent=2)
    )
    return observations, summary


async def capture_public(
    root: Path,
    *,
    family: str,
    weather: WeatherConfig,
    kalshi_transport: httpx.AsyncBaseTransport | None = None,
    source_transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> ExperimentData:
    if family not in {"weather", "bitcoin"}:
        raise ValueError("unregistered public family")
    root.mkdir(parents=True, exist_ok=False)
    (root / "raw").mkdir()
    receipts: list[dict[str, Any]] = []
    refs: dict[str, tuple[str, str, datetime]] = {}
    failures: list[dict[str, str]] = []
    now = (clock or SystemClock()).now
    started_at = now()

    def failed(source: str, failure: str) -> None:
        # Network failures have no HTTP response body; record a clocked failure event,
        # never manufacture a successful receipt or substitute a fixture.
        failures.append({"source": source, "failure": failure, "failed_at": now().isoformat()})

    def retain(raw: RawCapture, *, collect_market_refs: bool = True) -> None:
        name = f"raw/{len(receipts) + 1:04d}.json"
        (root / name).write_bytes(raw.body)
        digest = file_hash(root / name)
        receipts.append(
            {
                "path": raw.path,
                "status": raw.status,
                "raw_ref": name,
                "hash": digest,
                "received_at": raw.received_at.isoformat(),
            }
        )
        if collect_market_refs and raw.status == 200:
            for item in json.loads(raw.body).get("markets", []):
                refs[item["ticker"]] = name, digest, raw.received_at

    gateway = KalshiGateway(
        environment=KalshiEnvironment.PRODUCTION,
        capture=retain,
        transport=BoundedTransport(kalshi_transport),
        wait_for_budget=True,
        environ={},
        clock=clock,
    )
    markets: list[Market] = []
    observations: list[Observation] = []
    try:
        async with asyncio.timeout(120):
            series = (
                ("KXBTC",) if family == "bitcoin" else tuple(p.series for p in weather.locations)
            )
            for ticker in series:
                try:
                    markets.extend(
                        await gateway.list_markets(series_ticker=ticker, status=MarketStatus.ACTIVE)
                    )
                except (GatewayError, httpx.HTTPError, ValueError) as exc:
                    failed(ticker, type(exc).__name__)
            if family == "bitcoin":
                url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
                async with httpx.AsyncClient(
                    transport=BoundedTransport(source_transport), timeout=20
                ) as client:
                    try:
                        response = await client.get(url)
                        at = now()
                        retain(
                            RawCapture("GET", url, response.status_code, response.content, {}, at),
                            collect_market_refs=False,
                        )
                        response.raise_for_status()
                        payload = response.json()
                        if not isinstance(payload["price"], str):
                            raise ValueError("spot price must be an exact decimal string")
                        price = Decimal(payload["price"])
                        valid = ensure_utc(
                            datetime.fromisoformat(payload["time"].replace("Z", "+00:00"))
                        )
                        if not price.is_finite() or price <= 0 or valid > at:
                            raise ValueError("invalid spot value or future trade time")
                        observations.append(
                            Observation(
                                source_id="coinbase",
                                entity_id="BTC-USD",
                                variable="spot_usd",
                                valid_on=valid.date(),
                                valid_at=valid,
                                value=price,
                                unit="USD",
                                available_at=at,
                                received_at=at,
                                timing_basis="received",
                                evidence=(
                                    "First public ticker receipt; Coinbase is a covariate only"
                                ),
                                raw_ref=receipts[-1]["raw_ref"],
                                raw_hash=receipts[-1]["hash"],
                            )
                        )
                    except (
                        httpx.HTTPError,
                        ValueError,
                        KeyError,
                        TypeError,
                        InvalidOperation,
                    ) as exc:
                        failed("coinbase", type(exc).__name__)
            else:

                def weather_response(request: httpx.Request, response: httpx.Response) -> None:
                    retain(
                        RawCapture(
                            "GET",
                            str(request.url),
                            response.status_code,
                            response.content,
                            {},
                            now(),
                        ),
                        collect_market_refs=False,
                    )
                    if response.status_code != 200:
                        failed(str(request.url), f"HTTP{response.status_code}")

                def weather_error(request: httpx.Request, error: httpx.HTTPError) -> None:
                    failed(str(request.url), type(error).__name__)

                def weather_progress(message: str) -> None:
                    event = json.loads(message)
                    if not event["captured"]:
                        failed(
                            "weather:" + event["provider"] + ":" + event.get("location", "unknown"),
                            "NoForecastVintage",
                        )

                # The forecast archive is a parsing intermediate: it lives outside the
                # capture, and only its exact-body references and receipt ledger are kept.
                with tempfile.TemporaryDirectory(prefix="entropytrade-weather-") as scratch:
                    archive = ForecastArchive(Path(scratch) / "weather.sqlite")
                    try:
                        try:
                            await poll_weather(
                                config=weather.revalidated(attempts=1),
                                archive=archive,
                                stop=asyncio.Event(),
                                once=True,
                                transport=BoundedTransport(
                                    source_transport,
                                    on_response=weather_response,
                                    on_error=weather_error,
                                ),
                                emit=weather_progress,
                            )
                        except (httpx.HTTPError, ValueError) as exc:
                            failed("weather", type(exc).__name__)
                        observations, summary = retain_weather(
                            archive, Path(scratch) / "export", root, receipts
                        )
                        if summary["failures"] or not summary["vintages"]:
                            failed("weather", "IncompleteCapture")
                    finally:
                        archive.close()
    except TimeoutError:
        failed("acquisition", "TimeBudgetExceeded")
    finally:
        await gateway.aclose()
    decision = now()
    if family == "bitcoin":
        markets = [m.revalidated(rules=bitcoin_rules(m.rules)) for m in markets]
    evidence = [
        MarketEvidence(
            market=m.revalidated(rules=m.rules.revalidated(captured_at=refs[m.ticker][2])),
            capture_basis="receipt",
            raw_ref=refs[m.ticker][0],
            raw_hash=refs[m.ticker][1],
        )
        for m in markets
        if m.ticker in refs
    ]
    for name, rows in (("markets.jsonl", evidence), ("observations.jsonl", observations)):
        (root / name).write_text(
            "".join(r.model_dump_json(exclude_computed_fields=True) + "\n" for r in rows)
        )
    capture = {
        "family": family,
        "started_at": started_at.isoformat(),
        "decision_time": decision.isoformat(),
        "receipts": receipts,
        "failures": failures,
        "listed_contracts": len(evidence),
        "observations": len(observations),
        "history_complete": False,
        "universe_complete": not failures,
        "truncated_universe": bool(failures),
    }
    (root / "capture.json").write_text(json.dumps(capture, sort_keys=True, indent=2))
    manifest = {
        "family": family,
        "decision_time": decision.isoformat(),
        "ingestion_code_hash": file_hash(Path(__file__)),
        "weather_config": weather.model_dump(mode="json"),
        "checksums": {
            p.relative_to(root).as_posix(): file_hash(p)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        },
    }
    manifest["dataset_version"] = scientific_hash(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return forward_data(root)
