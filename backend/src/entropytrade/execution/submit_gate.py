"""Decide whether a submit may leave the process. This module does not open a socket.

Only ``DEMO`` is allowed to call the injected transport, and only a test should
provide one. ``LIVE`` is refused after ``resolve_trading_mode``, including when
the live flag is set. A non-4xx response, a validation failure, or a transport
error is ``unknown`` and keeps the request's ``client_order_id``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.modes import TradingMode, resolve_trading_mode
from entropytrade.domain.orders import OrderRequest
from entropytrade.exchange.gateway import OrderSubmissionForbiddenError


class SubmitTransportError(Exception):
    """The transport did not return a definite response."""


@dataclass(frozen=True)
class TransportResult:
    """What a mock transport hands back. ``valid`` is false when the body fails validation."""

    status_code: int
    client_order_id: UUID | None
    valid: bool


@dataclass(frozen=True)
class SubmitAttempt:
    verdict: str
    client_order_id: UUID


Transport = Callable[[OrderRequest], TransportResult]


def attempt_submit(
    *,
    requested: TradingMode,
    environment: KalshiEnvironment,
    process_env: Mapping[str, str],
    request: OrderRequest,
    transport: Transport,
) -> SubmitAttempt:
    """Call ``transport`` only for ``DEMO``. Every other mode returns first."""
    resolved = resolve_trading_mode(requested, environment, process_env)
    if resolved is not TradingMode.DEMO:
        raise OrderSubmissionForbiddenError(resolved)
    try:
        result = transport(request)
    except SubmitTransportError:
        return SubmitAttempt("unknown", request.client_order_id)
    if 400 <= result.status_code < 500:
        return SubmitAttempt("rejected", request.client_order_id)
    matched = result.valid and result.client_order_id == request.client_order_id
    if result.status_code in (200, 201) and matched:
        return SubmitAttempt("acknowledged", request.client_order_id)
    return SubmitAttempt("unknown", request.client_order_id)
