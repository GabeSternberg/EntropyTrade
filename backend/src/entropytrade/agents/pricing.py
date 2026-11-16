"""Refuse unpriced provider responses before the non-streaming research loop continues."""

from __future__ import annotations

import time
from dataclasses import asdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.usage import RunUsage
from pydantic_core import to_jsonable_python

from entropytrade.domain.time import utc_now

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_ai.messages import ModelMessage, ModelResponse
    from pydantic_ai.models import Model, ModelRequestParameters
    from pydantic_ai.settings import ModelSettings


class ResearchPricingError(ValueError):
    """An individual provider response could not be priced; never retry this error."""


class PricedResearchModel(WrapperModel):
    """Check every raw response, including retries and suspended continuation segments.

    Stage-level hooks run after continuations have merged. Wrapping ``request`` checks
    each billed response before PydanticAI can process tools, validate output or continue.
    The separate receipt totals retain usage when refusal prevents framework accounting.
    Research uses only ``Agent.run``; no streaming requests enter this boundary.
    """

    def __init__(self, model: Model, *, stage: Callable[[], str], free: bool = False) -> None:
        super().__init__(model)
        self.stage = stage
        # Only a server-configured loopback endpoint is free; every hosted provider is priced.
        self.free = free
        self.responses: list[dict[str, Any]] = []
        self.request_failures: list[dict[str, Any]] = []
        self.observed_usage = RunUsage()
        self.refused = False

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        if self.refused:
            raise ResearchPricingError("provider response pricing is unavailable")
        started = time.monotonic()
        receipt: dict[str, Any] = {"stage": self.stage(), "started_at": utc_now().isoformat()}
        self.observed_usage.requests += 1
        try:
            response = await self.wrapped.request(
                messages, model_settings, model_request_parameters
            )
        except BaseException as exc:
            receipt.update(status="failed", error=type(exc).__name__)
            if isinstance(exc, ModelHTTPError):
                receipt["http_status"] = exc.status_code
            self.request_failures.append(receipt)
            raise
        finally:
            receipt.update(
                finished_at=utc_now().isoformat(), latency_ms=(time.monotonic() - started) * 1000
            )
        if self.free:
            response.usage.cost = Decimal(0)
        if response.usage.cost is None:
            try:
                response.usage.cost = response.cost().total_price
            except Exception:  # noqa: BLE001 - fail closed; never persist pricing exception text
                self.refused = True
        cost = response.usage.cost
        if cost is None or not cost.is_finite() or cost < 0:
            self.refused = True
            response.usage.cost = None
        self.observed_usage.incr(response.usage)
        receipt.update(
            status="unpriced" if self.refused else "returned",
            model_name=response.model_name,
            provider_name=response.provider_name,
            provider_response_id=response.provider_response_id,
            timestamp=response.timestamp.isoformat(),
            usage=to_jsonable_python(asdict(response.usage)),
            requested_tools=[p.tool_name for p in response.parts if isinstance(p, ToolCallPart)],
        )
        self.responses.append(receipt)
        if self.refused:
            raise ResearchPricingError("provider response pricing is unavailable")
        return response
