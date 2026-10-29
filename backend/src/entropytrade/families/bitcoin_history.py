"""Receipt-backed Bitcoin history. Neither spot nor a later rule snapshot backfills history.

Only the explicit KXBTC BRTI sixty-second-average, strictly-above template is recognized.
Targets are finalized Kalshi binary results, never reconstructed Coinbase/index prices.
This adapter does not certify executable liquidity, fees or exceptional settlement paths.
"""

import asyncio
import json
import math
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from entropytrade.data.schema import MarketEvidence, Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import KalshiEnvironment, MarketResult, MarketStatus, StrikeType
from entropytrade.domain.market import Market
from entropytrade.domain.time import Clock, SystemClock, ensure_utc
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.exchange.kalshi.transport import RawCapture
from entropytrade.experiments.data import ContractSample, ExperimentData
from entropytrade.families.bitcoin_models import history_readiness
from entropytrade.families.public import BoundedTransport, forward_data, fresh_spot
from entropytrade.features.registry import scientific_hash

SECONDARY = (
    "Not all cryptocurrency price data is the same. While checking a source like Google or "
    "Coinbase may help guide your decision, the price used to determine this market is based "
    "on CF Benchmarks' corresponding Real Time Index (RTI). At the last minute before "
    "expiration, 60 RTI prices are collected. The official and final value is the average "
    "of these prices."
)
PRIMARY = re.compile(
    r"If the simple average of the sixty seconds of CF Benchmarks' Bitcoin Real-Time Index "
    r"\(BRTI\) before (?P<hour>[1-9]|1[0-2]) (?P<ampm>AM|PM) (?P<zone>EST|EDT) is above "
    r"(?P<floor>[0-9]+(?:\.[0-9]+)?) at (?P=hour) (?P=ampm) (?P=zone) on "
    r"(?P<month>[A-Z][a-z]{2}) (?P<day>[0-9]{1,2}), (?P<year>[0-9]{4}), "
    r"then the market resolves to Yes\."
)
FEATURES = (
    ("spot_usd", "USD", "Fresh Coinbase BTC-USD covariate at the retained decision"),
    ("spot_minus_floor_usd", "USD", "Receipt-time spot minus frozen actual strike"),
    ("hours_to_close", "hours", "Actual frozen close minus retained decision"),
    (
        "scaled_moneyness",
        "dimensionless",
        "100 * log(spot / strike) / sqrt(hours_to_close); no volatility or price label inferred",
    ),
)
MONTHS = dict(
    zip(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        range(1, 13),
        strict=True,
    )
)
MAX_CAPTURES = 128


def _input(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("history reference escaped its snapshot")
    return path


def recognized_terms(market: Market) -> date | None:
    """Exact positive grammar plus strike/clock checks; a lexical mention never suffices.

    No rounding assumption is needed for a binary official-result target. Unknown rule
    text, exceptional conditions and non-above contracts remain unsupported. The broader
    forward adapter's independent settlement gate stays closed.
    """
    rules, strike = market.rules, market.strike
    match = PRIMARY.fullmatch(rules.rules_primary)
    if (
        market.series_ticker != "KXBTC"
        or rules.market_ticker != market.ticker
        or rules.rules_secondary != SECONDARY
        or rules.early_close_condition
        or not match
        or strike is None
        or strike.strike_type is not StrikeType.GREATER
        or strike.floor != Decimal(match["floor"])
        or strike.floor <= 0
    ):
        return None
    try:
        hour = int(match["hour"]) % 12 + (12 if match["ampm"] == "PM" else 0)
        close = datetime(
            int(match["year"]),
            MONTHS[match["month"]],
            int(match["day"]),
            hour,
            tzinfo=ZoneInfo("America/New_York"),
        )
    except (KeyError, ValueError):
        return None
    if close.tzname() != match["zone"] or close.astimezone(UTC) != market.close_time:
        return None
    return close.date()


def _receipt(root: Path, manifest: dict[str, Any], ref: str) -> dict[str, Any]:
    found = [r for r in manifest["receipts"] if r["raw_ref"] == ref and r["status"] == 200]
    if len(found) != 1 or found[0]["hash"] != file_hash(_input(root, ref)):
        raise ValueError("history input lacks a unique successful raw receipt")
    return dict(found[0])


def capture_samples(root: Path) -> tuple[ContractSample, ...]:
    """Recheck immutable manifests, then derive features from original raw values."""
    data = forward_data(root)
    capture = data.provenance["capture"]
    if capture["family"] != "bitcoin":
        raise ValueError("Bitcoin history requires Bitcoin public captures")
    decision = ensure_utc(datetime.fromisoformat(capture["decision_time"]))
    observations = [
        Observation.model_validate_json(line)
        for line in (root / "observations.jsonl").read_text().splitlines()
    ]
    spot = fresh_spot(observations, decision)
    if spot is None:
        return ()
    receipt = _receipt(root, capture, spot.raw_ref)
    payload = json.loads((root / spot.raw_ref).read_text())
    if (
        receipt["path"] != "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        or spot.value != Decimal(payload["price"])
        or spot.valid_at
        != ensure_utc(datetime.fromisoformat(payload["time"].replace("Z", "+00:00")))
        or spot.available_at != ensure_utc(datetime.fromisoformat(receipt["received_at"]))
    ):
        raise ValueError("spot normalization disagrees with original receipt")
    samples = []
    for line in (root / "markets.jsonl").read_text().splitlines():
        evidence = MarketEvidence.model_validate_json(line)
        receipt = _receipt(root, capture, evidence.raw_ref)
        url = httpx.URL("https://api.elections.kalshi.com" + receipt["path"])
        if (
            url.path != "/trade-api/v2/markets"
            or url.params.get("series_ticker") != "KXBTC"
            or url.params.get("status") != "open"
            or evidence.capture_basis != "receipt"
        ):
            raise ValueError("history needs original public market-list receipts")
        at = ensure_utc(datetime.fromisoformat(receipt["received_at"]))
        bodies = json.loads((root / evidence.raw_ref).read_text())["markets"]
        bodies = [b for b in bodies if b["ticker"] == evidence.market.ticker]
        if len(bodies) != 1:
            raise ValueError("normalized market absent from its original receipt")
        market = market_from_body(bodies[0], captured_at=at, series="KXBTC")
        original = evidence.market
        if any(
            getattr(market, field) != getattr(original, field)
            for field in ("ticker", "event_ticker", "open_time", "close_time", "strike")
        ) or any(
            getattr(market.rules, field) != getattr(original.rules, field)
            for field in (
                "rules_primary",
                "rules_secondary",
                "early_close_condition",
                "captured_at",
            )
        ):
            raise ValueError("market normalization disagrees with original receipt")
        target = recognized_terms(market)
        if (
            target is None
            or market.status is not MarketStatus.ACTIVE
            or market.result is not None
            or not market.open_time <= at <= decision < market.close_time
        ):
            continue
        assert market.strike is not None  # noqa: S101
        assert market.strike.floor is not None  # noqa: S101
        hours = (market.close_time - decision).total_seconds() / 3600
        # Avoid float overflow/unstable near-expiry scaling. This is a model domain limit.
        if not 0.25 <= hours <= 48:
            continue
        values: dict[str, Decimal | None] = {
            "spot_usd": spot.value,
            "spot_minus_floor_usd": spot.value - market.strike.floor,
            "hours_to_close": Decimal(str(hours)),
            "scaled_moneyness": Decimal(
                str(100 * math.log(float(spot.value / market.strike.floor)) / math.sqrt(hours))
            ),
        }
        identity = {
            "decision": decision.isoformat(),
            "values": {k: str(v) for k, v in values.items()},
            "market_receipt": evidence.raw_hash,
            "spot_receipt": spot.raw_hash,
            "rules": market.rules.rules_hash,
            "adapter": "bitcoin-history-v1",
        }
        samples.append(
            ContractSample(
                event_id=market.event_ticker,
                ticker=market.ticker,
                family="KXBTC",
                target_date=target,
                decision_time=decision,
                close_time=market.close_time,
                features_available_at=decision,
                features=values,
                versions={name: "1" for name, _, _ in FEATURES},
                feature_hash=scientific_hash(identity),
                sources=("coinbase", "kalshi"),
                # Recognized binary target terms do not certify exceptional paths or execution.
                rules_known=False,
                eligible=True,
            )
        )
    return tuple(samples)


class OutcomeTransport(BoundedTransport):
    """Only exact captured ticker reads; no discovery, accounts, orders or redirects."""

    def __init__(self, tickers: Sequence[str], inner: httpx.AsyncBaseTransport | None) -> None:
        super().__init__(inner)
        self.paths = {
            f"/trade-api/v2/{prefix}markets/{ticker}"
            for ticker in tickers
            for prefix in ("", "historical/")
        }

    def permits_path(self, url: httpx.URL) -> bool:
        return url.host == "api.elections.kalshi.com" and url.path in self.paths and not url.query


async def reconcile(
    root: Path,
    samples: Sequence[ContractSample],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
    previous: Sequence[Path] = (),
    fetch: bool = True,
) -> dict[str, Any]:
    """Bounded receipt-time reconciliation. A later final result never gains an earlier clock."""
    now = (clock or SystemClock()).now
    root.mkdir(parents=True, exist_ok=False)
    started = now()
    receipts: list[dict[str, Any]] = []
    retained: set[str] = set()
    attempts: dict[str, str] = {}
    retained_bytes = 0
    for prior in previous:
        # history_data verifies the whole prior snapshot before any bytes are reused.
        history_data(prior)
        prior_summary = json.loads((prior / "outcomes/receipts.json").read_text())
        for ticker, at in prior_summary.get("attempts", {}).items():
            attempts[ticker] = max(attempts.get(ticker, ""), at)
        for receipt in prior_summary["receipts"]:
            identity = scientific_hash({k: v for k, v in receipt.items() if k != "raw_ref"})
            if identity in retained:
                continue
            retained.add(identity)
            name = f"{len(receipts):04d}.json"
            content = _input(prior / "outcomes", receipt["raw_ref"]).read_bytes()
            retained_bytes += len(content)
            if retained_bytes > 32_000_000 or len(receipts) >= 1280:
                raise ValueError("outcome history exceeds bounded partition size")
            (root / name).write_bytes(content)
            receipts.append({**receipt, "raw_ref": name})
    # Preserve original receipt clocks across retries/restarts; skip verified final targets.
    (root / "receipts.json").write_text(json.dumps({"receipts": receipts}))
    resolved = _outcomes(root, samples)
    tickers = sorted({s.ticker for s in samples if s.close_time <= started})
    # Two reads per ticker at most (live + archive fallback), within the 20-request cap.
    pending = [ticker for ticker in tickers if ticker not in resolved]
    pending.sort(key=lambda ticker: (attempts.get(ticker, ""), ticker))
    selected = pending[:10] if fetch else []
    failures: list[dict[str, str]] = []

    def retain(raw: RawCapture) -> None:
        name = f"{len(receipts):04d}.json"
        (root / name).write_bytes(raw.body)
        receipts.append(
            {
                "raw_ref": name,
                "hash": file_hash(root / name),
                "path": raw.path,
                "status": raw.status,
                "received_at": raw.received_at.isoformat(),
            }
        )

    gateway = KalshiGateway(
        environment=KalshiEnvironment.PRODUCTION,
        environ={},
        capture=retain,
        clock=clock,
        transport=OutcomeTransport(selected, transport),
    )
    try:
        async with asyncio.timeout(90):
            for ticker in selected:
                attempts[ticker] = now().isoformat()
                try:
                    try:
                        await gateway.get_market(ticker)
                    except GatewayError:
                        if (
                            not gateway.last_capture
                            or gateway.last_capture.status != 404
                            or gateway.last_capture.path != f"/trade-api/v2/markets/{ticker}"
                        ):
                            raise
                        await gateway.get_archived_market(ticker)
                except (GatewayError, httpx.HTTPError, ValueError) as exc:
                    failures.append(
                        {
                            "ticker": ticker,
                            "failure": type(exc).__name__,
                            "failed_at": now().isoformat(),
                        }
                    )
    except TimeoutError:
        failures.append(
            {"ticker": "batch", "failure": "TimeBudgetExceeded", "failed_at": now().isoformat()}
        )
    finally:
        await gateway.aclose()
    summary = {
        "started_at": started.isoformat(),
        "finished_at": now().isoformat(),
        "requested": len(selected),
        "deferred": len(pending) - len(selected),
        "retained_receipts": len(retained),
        "fetch_enabled": fetch,
        "attempts": attempts,
        "receipts": receipts,
        "failures": failures,
    }
    (root / "receipts.json").write_text(json.dumps(summary, sort_keys=True, indent=2))
    return summary


def _outcomes(
    root: Path, samples: Sequence[ContractSample]
) -> dict[str, tuple[MarketResult, datetime]]:
    summary = json.loads((root / "receipts.json").read_text())
    by_ticker = {s.ticker: s for s in samples}
    results: dict[str, tuple[MarketResult, datetime]] = {}
    for receipt in summary["receipts"]:
        if receipt["status"] != 200:
            continue
        at = ensure_utc(datetime.fromisoformat(receipt["received_at"]))
        raw = json.loads(_input(root, receipt["raw_ref"]).read_text())
        market = market_from_body(raw["market"], captured_at=at, series="KXBTC")
        sample = by_ticker.get(market.ticker)
        if receipt["hash"] != file_hash(_input(root, receipt["raw_ref"])):
            raise ValueError("outcome receipt checksum mismatch")
        if receipt["path"] not in {
            f"/trade-api/v2/markets/{market.ticker}",
            f"/trade-api/v2/historical/markets/{market.ticker}",
        }:
            raise ValueError("outcome receipt is outside the captured universe")
        if sample is None:
            continue  # A prior snapshot may contain other explicitly selected captures.
        if (
            market.status is MarketStatus.FINALIZED
            and market.result in {MarketResult.YES, MarketResult.NO}
            and market.settlement_ts is not None
            and market.settlement_value
            == (Decimal(1) if market.result is MarketResult.YES else Decimal(0))
            and raw["market"].get("is_provisional") in {None, False}
            and sample.close_time <= market.settlement_ts <= at
            and market.close_time == sample.close_time
            and recognized_terms(market) == sample.target_date
        ):
            # Frozen feature identity already binds the strike and terms. Reconciliation
            # additionally verifies the original strike via the fixed spot/floor feature.
            assert market.strike is not None  # noqa: S101
            floor = sample.features["spot_usd"] - sample.features["spot_minus_floor_usd"]  # type: ignore[operator]
            if market.event_ticker != sample.event_id or market.strike.floor != floor:
                raise ValueError("outcome changed captured identity/strike")
            if market.ticker in results and results[market.ticker][0] != market.result:
                raise ValueError("conflicting finalized outcomes")
            previous = results.get(market.ticker)
            results[market.ticker] = market.result, min(at, previous[1]) if previous else at
    return results


def history_data(root: Path) -> ExperimentData:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["schema"] != "bitcoin-history-v1":
        raise ValueError("unknown history schema")
    if (
        scientific_hash({k: v for k, v in manifest.items() if k != "dataset_version"})
        != manifest["dataset_version"]
    ):
        raise ValueError("history manifest identity mismatch")
    for name, digest in manifest["checksums"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != digest:
            raise ValueError("history input checksum/path mismatch")
    # Require the exact complete file inventory, including all nested raw receipts.
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p != root / "manifest.json"
    }
    if actual != set(manifest["checksums"]):
        raise ValueError("history manifest omits or adds inputs")
    samples: dict[tuple[str, datetime], ContractSample] = {}
    for name in manifest["captures"]:
        for sample in capture_samples(_input(root, name)):
            samples[sample.ticker, sample.decision_time] = sample
    # Freeze the earliest retained decision for an event; repeated polling is not new evidence.
    earliest: dict[str, datetime] = {}
    for sample in samples.values():
        earliest[sample.event_id] = min(
            earliest.get(sample.event_id, sample.decision_time), sample.decision_time
        )
    selected = sorted(
        (s for s in samples.values() if s.decision_time == earliest[s.event_id]),
        key=lambda s: (s.decision_time, s.ticker),
    )
    outcomes = _outcomes(root / "outcomes", selected)
    selected = [
        s.revalidated(outcome=outcomes[s.ticker][0], outcome_available_at=outcomes[s.ticker][1])
        if s.ticker in outcomes
        else s
        for s in selected
    ]
    dates = sorted({s.target_date for s in selected})
    partition = manifest["partition"]
    boundary = date.fromisoformat(partition["holdout_start"])
    protected = frozenset(s.event_id for s in selected if s.target_date >= boundary)
    catalog = {
        "version": "bitcoin-history-v1",
        "features": [
            {
                "name": name,
                "version": "1",
                "unit": unit,
                "transformation": transform,
                "missing_behavior": "exclude; no imputation",
            }
            for name, unit, transform in FEATURES
        ],
    }
    data = ExperimentData(
        dataset_version=manifest["dataset_version"],
        feature_version=scientific_hash(
            {"catalog": catalog, "implementation": file_hash(Path(__file__))}
        ),
        data_kind="real",
        samples=tuple(selected),
        protected_events=protected,
        feature_definitions=catalog,
        provenance={
            "adapter": "bitcoin-history-v1",
            "partition": partition,
            "source_kinds": ["coinbase", "kalshi"],
            "capture_count": len(manifest["captures"]),
            "protected_events": len(protected),
            "retained_events": len(earliest),
            "retained_dates": len(dates),
            "reconciliation": json.loads((root / "outcomes/receipts.json").read_text()),
            "limitations": [
                "Only exact BRTI sixty-second-average strictly-above rule templates "
                "and finalized binary Kalshi results are modeled.",
                "Coinbase is a predictor, never a settlement price. "
                "Outcome availability is receipt time.",
                "Exceptional settlement paths remain unverified; "
                "rules_known stays false for execution.",
                "No historical depth or certified fees; "
                "trading backtests and returns remain blocked.",
                "Repeated snapshots are one event. Fixed fit/validation/holdout dates "
                "persist across snapshots and never roll forward.",
            ],
        },
    )
    data.provenance["readiness"] = history_readiness(data)
    return data


async def build_history(
    root: Path,
    captures: Sequence[Path],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
    previous: Sequence[Path] = (),
    fetch: bool = True,
) -> ExperimentData:
    if len(captures) > MAX_CAPTURES or len(previous) > MAX_CAPTURES:
        raise ValueError("history is bounded to 128 captures; select an explicit partition")
    # Validate before writing, including raw-to-normalized identity/clock checks.
    unique = {forward_data(p).dataset_version: p for p in captures}
    for path in unique.values():
        capture_samples(path)
    policies = [history_data(p).provenance["partition"] for p in previous]
    if policies and any(policy != policies[0] for policy in policies):
        raise ValueError("previous snapshots have different protected calendar boundaries")
    first = min(
        (
            ensure_utc(
                datetime.fromisoformat(
                    json.loads((p / "manifest.json").read_text())["decision_time"]
                )
            ).date()
            for p in unique.values()
        ),
        default=(clock or SystemClock()).now().date(),
    )
    # Predeclare once, before modeling: 60 capture days for fitting, then 30 for validation.
    # All later dates are protected. Later snapshots inherit these exact dates.
    partition = (
        policies[0]
        if policies
        else {
            "anchor": first.isoformat(),
            "fit_before": (first + timedelta(days=60)).isoformat(),
            "holdout_start": (first + timedelta(days=90)).isoformat(),
        }
    )
    if unique and first < date.fromisoformat(partition["anchor"]):
        raise ValueError(
            "new capture precedes the frozen partition anchor; select an explicit partition"
        )
    root.mkdir(parents=True, exist_ok=False)
    names = []
    total = 0
    samples: list[ContractSample] = []
    for index, (_, path) in enumerate(sorted(unique.items())):
        name = f"captures/{index:04d}"
        names.append(name)
        manifest = json.loads((path / "manifest.json").read_text())
        for relative in ("manifest.json", *manifest["checksums"]):
            content = (path / relative).read_bytes()
            total += len(content)
            if total > 128_000_000:
                raise ValueError("history exceeds the 128 MB input budget")
            output = root / name / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
        samples.extend(capture_samples(root / name))
    await reconcile(
        root / "outcomes", samples, transport=transport, clock=clock, previous=previous, fetch=fetch
    )
    manifest = {
        "schema": "bitcoin-history-v1",
        "partition": partition,
        "captures": names,
        "checksums": {
            p.relative_to(root).as_posix(): file_hash(p)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        },
    }
    manifest["dataset_version"] = scientific_hash(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return history_data(root)
