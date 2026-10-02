"""Build a Kalshi client config without ever trusting the process environment for the host.

``KalshiConfig.from_env`` is not used. ``KALSHI_ALLOW_UNKNOWN_HOST`` would let a signed
request follow a typo or a proxy; if that variable is set, the process refuses to start.
"""

import os
from collections.abc import Mapping

from kalshi.config import KalshiConfig

from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.exchange.gateway import GatewayError


def refuse_unknown_host_override(environ: Mapping[str, str] | None = None) -> None:
    """Raise when the SDK's host-check escape hatch is switched on."""
    env = os.environ if environ is None else environ
    if env.get("KALSHI_ALLOW_UNKNOWN_HOST", "").strip() == "1":
        raise GatewayError(
            "KALSHI_ALLOW_UNKNOWN_HOST is set; refusing to sign requests to an unlisted host"
        )


def kalshi_config_for(environment: KalshiEnvironment) -> KalshiConfig:
    """Demo or production, retries off. The caller has already rejected the unknown-host flag."""
    if environment is KalshiEnvironment.DEMO:
        return KalshiConfig.demo(max_retries=0)
    return KalshiConfig.production(max_retries=0)
