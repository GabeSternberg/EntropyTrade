"""Submit stays off the network except for an injected demo transport."""

from pathlib import Path
from uuid import UUID

import pytest

from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.modes import TradingMode
from entropytrade.domain.orders import OrderRequest
from entropytrade.exchange.gateway import OrderSubmissionForbiddenError
from entropytrade.execution.submit_gate import (
    SubmitAttempt,
    SubmitTransportError,
    Transport,
    TransportResult,
    attempt_submit,
)
from tests.support import order_request

FORBIDDEN_HOSTS = ("api.elections.kalshi.com", "demo-api.kalshi.co")


def _called(request: OrderRequest) -> TransportResult:
    raise AssertionError(request.client_order_id)


def _timeout(_request: OrderRequest) -> TransportResult:
    raise SubmitTransportError("timed out")


def test_live_paper_and_shadow_never_call_the_transport() -> None:
    request = order_request()
    cases: tuple[tuple[TradingMode, dict[str, str]], ...] = (
        (TradingMode.READ_ONLY, {}),
        (TradingMode.PAPER, {}),
        (TradingMode.SHADOW, {}),
        (TradingMode.LIVE, {"ENTROPYTRADE_LIVE_TRADING_ENABLED": "true"}),
    )
    for mode, env in cases:
        with pytest.raises(OrderSubmissionForbiddenError):
            attempt_submit(
                requested=mode,
                environment=KalshiEnvironment.PRODUCTION,
                process_env=env,
                request=request,
                transport=_called,
            )


def test_demo_classifies_ack_reject_and_unknown() -> None:
    request = order_request()

    def transport(seen: OrderRequest) -> TransportResult:
        assert seen.client_order_id == request.client_order_id
        return TransportResult(201, seen.client_order_id, True)

    ack = _demo(request, transport)
    assert ack.verdict == "acknowledged"
    assert ack.client_order_id == request.client_order_id

    rejected = _demo(request, lambda _request: TransportResult(400, request.client_order_id, True))
    assert rejected.verdict == "rejected"

    unknown = _demo(request, lambda _request: TransportResult(201, UUID(int=1), False))
    assert unknown.verdict == "unknown"
    assert unknown.client_order_id == request.client_order_id

    timed_out = _demo(request, _timeout)
    assert timed_out.verdict == "unknown"
    assert timed_out.client_order_id == request.client_order_id


def test_the_gate_names_no_exchange_host() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/execution/submit_gate.py")
        .read_text(encoding="utf-8")
    )
    for host in FORBIDDEN_HOSTS:
        assert host not in text
    assert "httpx" not in text
    assert "kalshi" not in text


def _demo(request: OrderRequest, transport: Transport) -> SubmitAttempt:
    return attempt_submit(
        requested=TradingMode.DEMO,
        environment=KalshiEnvironment.DEMO,
        process_env={},
        request=request,
        transport=transport,
    )
