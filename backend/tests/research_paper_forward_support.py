"""TEST-ONLY synthetic paper cycles through real collection/scoring/accounting code.

All HTTP uses MockTransport. Artificial dates are explicit and raw products retain a
CONTROLLED SYNTHETIC label. The production decoder and deployment provenance gates remain
unchanged; classification overrides exist only inside this test helper.
"""

import asyncio
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore, FeeVersion
from entropytrade.experiments.data import ExperimentData
from entropytrade.tracking import history, worker
from entropytrade.tracking.research_features import acquire_research_features
from tests.exchange.test_gateway_http import _market_body
from tests.research_fixture_support import recorded
from tests.unit.test_public_families import weather

BASE = datetime(2026, 11, 11, 23, 0, tzinfo=UTC)
_MONTHS = {
    name: index
    for index, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
    )
}


def _shift(body: bytes, days: int) -> bytes:
    text = body.decode()

    # The retained fixture products are November 2026. This test-only transformation
    # shifts publication and valid dates together, preserving lead and column semantics.
    def issued(match: re.Match[str]) -> str:
        stamp = date(int(match[8]), _MONTHS[match[6].upper()], int(match[7])) + timedelta(days=days)
        return (
            f"{match[1]}{match[2]} {match[3]} {match[4]} "
            f"{stamp:%a} {stamp:%b} {stamp.day} {stamp.year}"
        ).upper()

    text = re.sub(
        r"^(\d{1,2})(\d{2}) (AM|PM) ([A-Z]{3}) ([A-Z]{3}) ([A-Z]{3}) (\d{1,2}) (\d{4})[ \t]*$",
        issued,
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    text = re.sub(
        r"^([A-Z]{4}\d{2} [A-Z]{4} )(\d{2})(\d{4})",
        lambda match: match[1] + f"{int(match[2]) + days:02d}" + match[3],
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"\b11/(\d{1,2})(?!\d)",
        lambda match: f"{date(2026, 11, int(match[1])) + timedelta(days=days):%m/%d}",
        text,
    )
    text = re.sub(
        r"NOVEMBER\s+(\d{1,2})\s+2026",
        lambda match: f"{date(2026, 11, int(match[1])) + timedelta(days=days):%B %d %Y}".upper(),
        text,
    )
    return b"CONTROLLED SYNTHETIC SHIFTED WEATHER PRODUCTS; NOT AUTHENTIC DATES\n" + text.encode()


def source_transports(
    clock: SimulatedClock,
) -> tuple[httpx.MockTransport, httpx.MockTransport, httpx.MockTransport, httpx.MockTransport]:
    target = clock.now().date() + timedelta(days=1)
    event = "KXHIGHPHIL-" + target.strftime("%y%b%d").upper()
    ticker = event + "-T40"
    body = _market_body()
    body.update(
        ticker=ticker,
        event_ticker=event,
        floor_strike=40,
        strike_type="greater",
        title="CONTROLLED SYNTHETIC Philadelphia high",
        created_time=(clock.now() - timedelta(days=1)).isoformat(),
        open_time=(clock.now() - timedelta(days=1)).isoformat(),
        close_time=(clock.now() + timedelta(days=2)).isoformat(),
        latest_expiration_time=(clock.now() + timedelta(days=3)).isoformat(),
        rules_primary=(
            "CONTROLLED SYNTHETIC highest Philadelphia CLIPHL temperature "
            "in Fahrenheit greater than40 according to The Weather Company."
        ),
    )
    products = recorded()
    shift = (clock.now().date() - BASE.date()).days
    pfm = _shift(b"\n".join(value[2] for url, value in products.items() if "PFMPHI" in url), shift)
    cli = _shift(b"\n".join(value[2] for url, value in products.items() if "CLIPHL" in url), shift)

    def tick() -> None:
        clock.advance(timedelta(seconds=1))

    # Include ten currently active contracts outside the trained target horizon. They
    # must never exhaust the bounded book budget before the eligible next-day contract.
    prior_event = "KXHIGHPHIL-" + clock.now().strftime("%y%b%d").upper()
    older = [
        body | {"ticker": prior_event + "-T" + str(index), "event_ticker": prior_event}
        for index in range(10)
    ]

    def listing(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        tick()
        return httpx.Response(200, json={"markets": [*older, body], "cursor": ""})

    def hourly(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        tick()
        start = clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "latitude": 39.87,
                "longitude": -75.23,
                "hourly_units": {"temperature_2m": "°F"},
                "hourly": {
                    "time": [(start + timedelta(hours=index)).isoformat() for index in range(120)],
                    "temperature_2m": [60] * 120,
                },
            },
        )

    def exact(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "mesonet.agron.iastate.edu"
        tick()
        return httpx.Response(200, content=pfm if request.url.params["pil"] == "PFMPHI" else cli)

    def execution(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        tick()
        if request.url.path.endswith("/orderbook"):
            return httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [["0.3000", "5.00"]],
                        "no_dollars": [["0.6500", "5.00"]],
                    }
                },
            )
        from tests.shadow_support import execution_wire

        return execution_wire(request)

    return (
        httpx.MockTransport(listing),
        httpx.MockTransport(hourly),
        httpx.MockTransport(exact),
        httpx.MockTransport(execution),
    )


@contextmanager
def controlled_forward_environment(clock: SimulatedClock) -> Iterator[None]:
    """Explicit synthetic classification for test-only mocked incoming observations."""
    capture_name, decode_name = "capture_public", "forward_data"
    actual_capture, actual_decode = getattr(worker, capture_name), getattr(history, decode_name)

    def synthetic(value: ExperimentData) -> ExperimentData:
        return value.revalidated(
            data_kind="synthetic",
            samples=tuple(
                sample.revalidated(
                    sources=tuple(
                        "synthetic-kalshi" if source == "kalshi" else source
                        for source in sample.sources
                    )
                )
                for sample in value.samples
            ),
        )

    async def capture(*args: Any, **kwargs: Any) -> ExperimentData:
        value: ExperimentData = await actual_capture(*args, **kwargs)
        return synthetic(value)

    def decode(*args: Any, **kwargs: Any) -> ExperimentData:
        value: ExperimentData = actual_decode(*args, **kwargs)
        return synthetic(value)

    async def acquire(*args: Any, **kwargs: Any) -> Any:
        async def no_sleep(_: float) -> None:
            pass

        return await acquire_research_features(*args, **(kwargs | {"sleep": no_sleep}))

    config = weather().revalidated(locations=weather().locations[:1], providers=("open-meteo",))
    with (
        patch.object(worker, "capture_public", side_effect=capture),
        patch.object(history, "forward_data", side_effect=decode),
        patch.object(worker, "acquire_research_features", side_effect=acquire),
        patch(
            "entropytrade.tracking.worker.WeatherConfig.model_validate_json", return_value=config
        ),
        patch("entropytrade.weather.collection.utc_now", clock.now),
        patch("entropytrade.storage.forecast_archive.utc_now", clock.now),
    ):
        yield


async def collect_controlled_cycle(
    monitor: dict[str, Any],
    repo: Path,
    root: Path,
    *,
    clock: SimulatedClock,
    fee_versions: tuple[FeeVersion, ...],
) -> dict[str, Any]:
    listing, hourly, exact, execution = source_transports(clock)
    with controlled_forward_environment(clock):
        result = await worker.collect(
            monitor,
            repo,
            root,
            clock=clock,
            kalshi_transport=listing,
            source_transport=hourly,
            research_transport=exact,
            execution_transport=execution,
            outcome_transport=execution,
            fee_versions=fee_versions,
        )
    return result | {"data_kind": "synthetic", "controlled_synthetic": True}


def commit_controlled_cycle(
    fixture: Any, when: datetime, *, clock: SimulatedClock | None = None
) -> dict[str, Any]:
    """Claim, collect, account and commit using real TrackingStore lifecycle methods."""
    if clock is None:
        clock = SimulatedClock(when)
    elif clock.now() > when:
        raise ValueError("controlled cycle clock cannot move backward")
    else:
        clock.advance_to(when)
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        claim = fixture.tracking.claim()
        if claim is None:
            raise ValueError("no controlled paper deployment is due")
        mid, cid = claim
        monitor = fixture.tracking.get(mid, export=True)
        assert monitor is not None
        root = fixture.jobs.root / "shadow" / mid / cid
        root.mkdir(parents=True)
        result = asyncio.run(
            collect_controlled_cycle(
                monitor,
                Path(__file__).resolve().parents[2],
                root,
                clock=clock,
                fee_versions=FeeEvidenceStore(fixture.jobs.root).snapshot(),
            )
        )
        result["artifacts"] = [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": file_hash(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
        (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
        if not fixture.tracking.finish(mid, cid, result):
            raise ValueError("controlled paper cycle was cancelled before commit")
        return result
