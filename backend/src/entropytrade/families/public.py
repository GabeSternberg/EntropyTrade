"""Forward weather and Bitcoin evidence. Spot is a covariate, never a settlement label."""

import asyncio
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import fmean
from typing import Any

import httpx

from entropytrade.data.schema import MarketEvidence, Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import KalshiEnvironment, MarketStatus
from entropytrade.domain.market import Market, MarketRules
from entropytrade.domain.strategy import StrategySpec
from entropytrade.domain.time import Clock, SystemClock, ensure_utc
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.experiments.data import ContractSample, ExperimentData, PredictionBundle
from entropytrade.features.pipeline import full_day_maxima
from entropytrade.features.registry import scientific_hash
from entropytrade.storage.forecast_archive import ForecastArchive
from entropytrade.weather.collection import WeatherConfig, poll_weather

BITCOIN_FEATURES = (
    ("spot_usd", "USD", "Latest fresh Coinbase BTC-USD trade, available at receipt"),
    ("hours_to_close", "hours", "Actual market close minus decision time"),
    (
        "spot_minus_floor_usd",
        "USD",
        "Coinbase covariate minus actual strike floor; no outcome inference",
    ),
)
WEATHER_FEATURES = (
    ("forecast_high_f", "degF", "Mean latest full-local-day hourly maximum proxy per model"),
    ("hours_to_close", "hours", "Actual market close minus decision time"),
)


def bitcoin_rules(rules: MarketRules) -> MarketRules:
    """No Bitcoin resolution parser exists; text mentions cannot verify a source."""
    return rules.revalidated(
        settlement_basis="unresolved", settlement_sources=(), settlement_target_date=None
    )


def authority_mentions(rules: MarketRules) -> list[dict[str, str]]:
    """Retain exact authority-name mentions, including negated/ambiguous contexts.

    These are lexical provenance only. Neither polarity nor settlement authority is
    inferred; the full original rule fields remain available beside these locations.
    """
    return [
        {
            "name": "CF Benchmarks",
            "rule_field": field,
            "text": match[0],
            "status": "unverified_mention",
        }
        for field in ("rules_primary", "rules_secondary")
        for match in re.finditer(r"\bcf\s+benchmarks\b", getattr(rules, field), re.IGNORECASE)
    ]


class BoundedTransport(httpx.AsyncBaseTransport):
    """No redirects/authentication; cap requests and streamed response sizes before decoding."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport | None = None,
        *,
        on_response: Callable[[httpx.Request, httpx.Response], None] | None = None,
        on_error: Callable[[httpx.Request, httpx.HTTPError], None] | None = None,
    ) -> None:
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        self.requests = 0
        self.bytes = 0
        self.on_response, self.on_error = on_response, on_error

    def permits_path(self, url: httpx.URL) -> bool:
        allowed = {
            "api.elections.kalshi.com": ("/trade-api/v2/markets",),
            "api.exchange.coinbase.com": ("/products/BTC-USD/ticker",),
            "api.open-meteo.com": ("/v1/forecast",),
            "api.weather.gov": ("/points/", "/gridpoints/"),
        }
        return any(
            url.path == p or (p.endswith("/") and url.path.startswith(p))
            for p in allowed.get(url.host, ())
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.url.scheme != "https"
            or request.url.port not in {None, 443}
            or not self.permits_path(request.url)
            or any(
                "authorization" in h.lower()
                or "api-key" in h.lower()
                or "kalshi-access" in h.lower()
                for h in request.headers
            )
        ):
            raise ValueError("public acquisition destination/authentication denied")
        self.requests += 1
        if self.requests > 20 or request.method != "GET":
            raise ValueError("public acquisition request budget exceeded")
        try:
            response = await self.inner.handle_async_request(request)
        except httpx.HTTPError as exc:
            if self.on_error is not None:
                self.on_error(request, exc)
            raise
        body = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                self.bytes += len(chunk)
                if len(body) > 2_000_000 or self.bytes > 12_000_000:
                    raise ValueError("public acquisition byte budget exceeded")
        except httpx.HTTPError as exc:
            if self.on_error is not None:
                self.on_error(request, exc)
            raise
        finally:
            await response.aclose()
        # Already decoded by aiter_bytes; do not decode content encoding twice.
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in {"content-encoding", "content-length"}
        }
        result = httpx.Response(response.status_code, headers=headers, content=bytes(body))
        if self.on_response is not None:
            self.on_response(request, result)
        return result

    async def aclose(self) -> None:
        await self.inner.aclose()


def fresh_spot(observations: list[Observation], decision: datetime) -> Observation | None:
    eligible = [
        o
        for o in observations
        if o.source_id == "coinbase"
        and o.entity_id == "BTC-USD"
        and o.variable == "spot_usd"
        and o.role == "feature"
        and o.unit == "USD"
        and o.value > 0
        and o.known_at(decision)
        and o.available_at is not None
        and decision - o.available_at <= timedelta(minutes=5)
        and o.valid_at is not None
        and timedelta(0) <= decision - o.valid_at <= timedelta(minutes=5)
    ]
    return max(eligible, key=lambda o: o.available_at or decision) if eligible else None


def forward_data(root: Path) -> ExperimentData:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["family"] not in {"bitcoin", "weather"}:
        raise ValueError("unregistered public family")
    if not {"markets.jsonl", "observations.jsonl", "capture.json"} <= set(manifest["checksums"]):
        raise ValueError("public manifest omits required input checksums")
    for name, digest in manifest["checksums"].items():
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not (root / name).resolve().is_relative_to(root.resolve())
        ):
            raise ValueError("unexpected public input")
        if file_hash(root / name) != digest:
            raise ValueError("public evidence checksum mismatch")
    if (
        scientific_hash({k: v for k, v in manifest.items() if k != "dataset_version"})
        != manifest["dataset_version"]
    ):
        raise ValueError("public manifest identity mismatch")
    decision = ensure_utc(datetime.fromisoformat(manifest["decision_time"]))
    observations = [
        Observation.model_validate_json(line)
        for line in (root / "observations.jsonl").read_text().splitlines()
    ]
    markets = [
        MarketEvidence.model_validate_json(line)
        for line in (root / "markets.jsonl").read_text().splitlines()
    ]
    inputs: list[Observation | MarketEvidence] = [*observations, *markets]
    for item in inputs:
        if manifest["checksums"].get(item.raw_ref) != item.raw_hash:
            raise ValueError("normalized evidence lacks a verified raw receipt")
    config = WeatherConfig.model_validate(manifest["weather_config"])
    definitions = BITCOIN_FEATURES if manifest["family"] == "bitcoin" else WEATHER_FEATURES
    catalog = {
        "version": "public-forward-v1",
        "features": [
            {
                "name": name,
                "version": "1",
                "unit": unit,
                "transformation": transformation,
                "missing_behavior": "null; never impute unavailable evidence",
            }
            for name, unit, transformation in definitions
        ],
    }
    version = scientific_hash(
        {
            "dataset": manifest["dataset_version"],
            "schema": catalog,
            "implementation": file_hash(Path(__file__)),
        }
    )
    samples = []
    details = []
    spot = fresh_spot(observations, decision)
    locations = {location.series: location for location in config.locations}
    for evidence in markets:
        market = evidence.market
        if manifest["family"] == "bitcoin":
            # Apply the same closed gate when loading earlier captures too.
            market = market.revalidated(rules=bitcoin_rules(market.rules))
        permitted_series = {"KXBTC"} if manifest["family"] == "bitcoin" else set(locations)
        if market.series_ticker not in permitted_series:
            raise ValueError("contract is outside the configured family")
        if not market.open_time <= decision < market.close_time:
            continue
        if market.rules.captured_at > decision:
            raise ValueError("future rules snapshot")
        sources = {"kalshi"}
        features: dict[str, Decimal | None] = {
            "hours_to_close": Decimal(str((market.close_time - decision).total_seconds() / 3600))
        }
        refs: list[str] = [evidence.raw_hash]
        if manifest["family"] == "bitcoin":
            target = market.close_time.date()  # grouping date only, never settlement semantics
            features["spot_usd"] = spot.value if spot else None
            features["spot_minus_floor_usd"] = (
                spot.value - market.strike.floor
                if spot and market.strike and market.strike.floor is not None
                else None
            )
            if spot:
                sources.add("coinbase")
                refs.append(spot.raw_hash)
        else:
            # A weather date must come from the existing verified rule parser.
            if market.rules.settlement_target_date is None or market.series_ticker not in locations:
                continue
            target = market.rules.settlement_target_date
            maxima = full_day_maxima(
                observations,
                location=locations[market.series_ticker],
                target=target,
                decision=decision,
            )
            per_model = {(p["provider"], p["model"]): p for p in maxima}
            latest = list(per_model.values())
            features["forecast_high_f"] = (
                Decimal(str(fmean(p["high_f"] for p in latest))) if latest else None
            )
            sources.update(p["provider"] for p in latest)
            refs.extend(h for p in latest for h in p["raw_hashes"])
        feature_hash = scientific_hash(
            {
                "features": {k: str(v) if v is not None else None for k, v in features.items()},
                "decision": decision.isoformat(),
                "inputs": sorted(refs),
                "version": version,
            }
        )
        # Naming an authority is provenance, not a verified resolution definition.
        # Bitcoin has no complete parser for comparator, index, averaging interval,
        # timezone, rounding and exceptional outcomes. Keep its independent gate closed.
        rules_known = (
            manifest["family"] == "weather"
            and market.rules.settlement_basis == "contract_text"
            and bool(market.rules.settlement_sources)
        )
        samples.append(
            ContractSample(
                event_id=market.event_ticker,
                ticker=market.ticker,
                family=market.series_ticker or "UNKNOWN",
                target_date=target,
                decision_time=decision,
                close_time=market.close_time,
                features_available_at=decision,
                features=features,
                versions={name: "1" for name, _, _ in definitions},
                feature_hash=feature_hash,
                sources=tuple(sorted(sources)),
                rules_known=rules_known,
                eligible=all(v is not None for v in features.values()),
                # A current quote/last trade does not establish executable depth or an outcome.
                fidelity="missing",
            )
        )
        details.append(
            {
                "ticker": market.ticker,
                "title": market.title,
                "event": market.event_ticker,
                "close_time": market.close_time.isoformat(),
                "rules_hash": market.rules.rules_hash,
                "rules_primary": market.rules.rules_primary,
                "rules_secondary": market.rules.rules_secondary,
                "settlement_sources": [s.model_dump() for s in market.rules.settlement_sources],
                "authority_mentions": (
                    authority_mentions(market.rules) if manifest["family"] == "bitcoin" else []
                ),
                "settlement_basis": market.rules.settlement_basis,
                "rules_known": rules_known,
                "features": {k: str(v) if v is not None else None for k, v in features.items()},
                "available_at": decision.isoformat(),
                "input_hashes": sorted(refs),
            }
        )
    return ExperimentData(
        dataset_version=manifest["dataset_version"],
        feature_version=version,
        data_kind="real",
        samples=tuple(samples),
        feature_definitions=catalog,
        provenance={
            "adapter": "public-forward-v1:" + manifest["family"],
            "source_kinds": sorted({source for sample in samples for source in sample.sources}),
            "configured_sources": (
                ["kalshi", "coinbase"]
                if manifest["family"] == "bitcoin"
                else ["kalshi", *config.providers]
            ),
            "capture": json.loads((root / "capture.json").read_text()),
            "contracts": details,
            "decision_time": decision.isoformat(),
            "limitations": [
                "Forward evidence only; no historical release clocks or outcomes inferred.",
                "No historical sized books or certified fee schedule; no execution returns.",
                *(
                    [
                        "Bitcoin resolution semantics are unverified; rules_known is false "
                        "and settlement sources remain unresolved. Authority mentions are "
                        "lexical provenance only, including negated or ambiguous mentions."
                    ]
                    if manifest["family"] == "bitcoin"
                    else []
                ),
                (
                    "Coinbase spot is a covariate, never a Kalshi settlement-source substitute."
                    if manifest["family"] == "bitcoin"
                    else "Full-day hourly forecast maxima are proxies, "
                    "not official settlement highs."
                ),
            ],
        },
    )


class ForwardPredictions:
    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        if family != "forward_only" or spec.model_ref is not None:
            raise ValueError("no matching fitted model exists for forward evidence")
        return PredictionBundle(
            records=(),
            source_hash=scientific_hash({"adapter": "forward-only-v1"}),
            model_metadata={"data_kind": "real", "status": "INSUFFICIENT_DATA"},
            refusals={
                family: "No independent temporal training/validation history or matched outcomes"
            },
        )


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

                archive = ForecastArchive(root / "weather.sqlite")
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
                    archive.export(root / "weather")
                    summary = json.loads((root / "weather/manifest.json").read_text())
                    if summary["failures"] or not summary["vintages"]:
                        failed("weather", "IncompleteCapture")
                    observations = [
                        Observation.model_validate_json(line).revalidated(
                            raw_ref="weather/" + Observation.model_validate_json(line).raw_ref
                        )
                        for line in (root / "weather/observations.jsonl").read_text().splitlines()
                    ]
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
