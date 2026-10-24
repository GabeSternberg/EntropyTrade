"""Long-lived orchestration with real SDK mock transport and reconnecting socket seam."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from entropytrade.collector.service import CollectorConfig, Stream, check_space, collect
from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.storage.recorder import Recorder
from tests.exchange.test_gateway_http import TICKER, _handler, _pem
from tests.exchange.test_recording_v2 import wire


def test_collector_reconnects_with_new_session_and_can_restart(tmp_path: Path) -> None:
    async def run() -> None:
        store = Recorder(tmp_path / "stream.sqlite")
        stop = asyncio.Event()
        opens = 0
        output: list[str] = []
        gateway = KalshiGateway(
            environment=KalshiEnvironment.DEMO,
            key_id="read-test",
            private_key_pem=_pem(),
            transport=httpx.MockTransport(_handler),
        )

        class Socket:
            def __init__(self, attempt: int) -> None:
                self.attempt = attempt
                self.reads = 0

            async def recv(self) -> str:
                self.reads += 1
                if self.reads == 1:
                    return wire(1)
                if self.attempt == 1:
                    raise ConnectionError("simulated network drop")
                stop.set()
                return wire(2, delta=True)

        @asynccontextmanager
        async def streams(tickers: tuple[str, ...]) -> AsyncIterator[Stream]:
            nonlocal opens
            assert tickers == (TICKER,)
            opens += 1
            yield Socket(opens)

        try:
            await collect(
                gateway=gateway,
                store=store,
                config=CollectorConfig(series=("KXHIGHPHIL",)),
                stream_factory=streams,
                stop=stop,
                emit=output.append,
            )
            assert opens == 2
            assert store.count("sessions") == 2
            assert store.count("frames") == 3
            assert store.health_summary()["unclosed_sessions"] == 0
            assert any(json.loads(line).get("state") == "retrying" for line in output)
        finally:
            await gateway.aclose()
            store.close()
        reopened = Recorder(tmp_path / "stream.sqlite")
        assert reopened.count("receipts") == 3
        assert reopened.health_summary()["latest"]["connected"] is False  # type: ignore[index]
        reopened.close()

    asyncio.run(run())


def test_paginated_discovery_uses_one_historical_filter_and_refuses_cursor_loops() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        result = _handler(request)
        if request.url.path.endswith("/markets"):
            if "/historical/" in request.url.path:
                assert "series_ticker" not in request.url.params
                assert request.url.params["event_ticker"] == "KXHIGHPHIL-26OCT02"
            payload = result.json()
            if "cursor" not in request.url.params:
                payload["cursor"] = "next"
            else:
                payload["markets"][0]["ticker"] = "KXHIGHPHIL-26OCT02-T80"
            # Observed API drift: this unused field is legitimately absent.
            payload["markets"][0].pop("liquidity_dollars", None)
            return httpx.Response(200, json=payload)
        return result

    async def run() -> None:
        from entropytrade.domain.historical import ApiOrigin

        gateway = KalshiGateway(
            environment=KalshiEnvironment.DEMO, transport=httpx.MockTransport(handler)
        )
        try:
            found = await gateway.list_markets(
                series_ticker="KXHIGHPHIL",
                event_ticker="KXHIGHPHIL-26OCT02",
                origin=ApiOrigin.HISTORICAL,
            )
            assert len(found) == 2
        finally:
            await gateway.aclose()

    asyncio.run(run())


def test_disk_budget_stops_without_deleting_existing_evidence(tmp_path: Path) -> None:
    path = tmp_path / "existing"
    path.write_bytes(b"evidence")
    with pytest.raises(OSError, match="disk budget"):
        check_space(path, 1)
    assert path.read_bytes() == b"evidence"


def test_sdk_socket_sends_only_public_subscriptions_and_keeps_raw_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.exchange.kalshi import socket as adapter

    commands: list[dict[str, object]] = []
    closed: list[bool] = []

    class Connection:
        def __init__(self, auth: object, config: object) -> None:
            pass

        async def connect(self) -> None:
            pass

        async def send(self, command: dict[str, object]) -> None:
            commands.append(command)

        async def recv(self) -> str:
            return wire(1)

        async def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(adapter, "ConnectionManager", Connection)
    key = tmp_path / "read.pem"
    key.write_text(_pem(), encoding="utf-8")

    async def run() -> None:
        factory = adapter.stream_factory(
            key_id="read-test", key_path=key, environment=KalshiEnvironment.DEMO
        )
        async with factory((TICKER,)) as stream:
            assert await stream.recv() == wire(1)

    asyncio.run(run())
    assert len(commands) == 3
    assert all(c["cmd"] == "subscribe" for c in commands)
    assert commands[-1]["params"] == {"channels": ["market_lifecycle_v2"]}
    assert closed == [True]


@pytest.mark.parametrize(
    ("scopes", "allowed"), [(["read"], True), (["read", "write"], False), ([], False)]
)
def test_collector_scope_verification_refuses_write_keys_and_does_not_record_key_inventory(
    scopes: list[str], allowed: bool
) -> None:
    from entropytrade.exchange.gateway import GatewayError

    captures: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"api_keys": [{"api_key_id": "read-test", "name": "test", "scopes": scopes}]}
        )

    async def run() -> None:
        gateway = KalshiGateway(
            environment=KalshiEnvironment.DEMO,
            key_id="read-test",
            private_key_pem=_pem(),
            transport=httpx.MockTransport(handler),
            capture=lambda raw: captures.append(raw.path),
        )
        try:
            if allowed:
                await gateway.require_read_scope("read-test")
            else:
                with pytest.raises(GatewayError, match="read-only scoped key"):
                    await gateway.require_read_scope("read-test")
        finally:
            await gateway.aclose()

    asyncio.run(run())
    assert captures == []
