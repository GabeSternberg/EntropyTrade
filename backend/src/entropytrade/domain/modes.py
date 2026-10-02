"""Trading modes and the rules for entering them.

The default is :attr:`TradingMode.READ_ONLY`. ``LIVE`` is reachable only when three independent
settings agree: the configured mode is ``LIVE``, the Kalshi environment is ``PRODUCTION``, and
the process environment variable :data:`LIVE_TRADING_ENV_FLAG` is exactly ``"true"``. A fresh
checkout therefore cannot submit real-money orders.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from entropytrade.domain.enums import KalshiEnvironment


class TradingMode(StrEnum):
    READ_ONLY = "read_only"
    BACKTEST = "backtest"
    PAPER = "paper"
    SHADOW = "shadow"
    DEMO = "demo"
    LIVE = "live"

    @property
    def submits_orders_to_exchange(self) -> bool:
        """Only DEMO (demo exchange) and LIVE (production) ever send orders to Kalshi."""
        return self in (TradingMode.DEMO, TradingMode.LIVE)

    @property
    def uses_real_money(self) -> bool:
        return self is TradingMode.LIVE


DEFAULT_TRADING_MODE: Final = TradingMode.READ_ONLY
LIVE_TRADING_ENV_FLAG: Final = "ENTROPYTRADE_LIVE_TRADING_ENABLED"


class TradingModeError(ValueError):
    """A requested mode is inconsistent or not permitted."""


def check_mode_environment(mode: TradingMode, environment: KalshiEnvironment) -> None:
    """DEMO mode must target the demo exchange; LIVE mode must target production."""
    if mode is TradingMode.DEMO and environment is not KalshiEnvironment.DEMO:
        raise TradingModeError("DEMO mode must use the Kalshi demo environment")
    if mode is TradingMode.LIVE and environment is not KalshiEnvironment.PRODUCTION:
        raise TradingModeError("LIVE mode must use the Kalshi production environment")


def resolve_trading_mode(
    requested: TradingMode,
    environment: KalshiEnvironment,
    process_env: Mapping[str, str],
) -> TradingMode:
    """Validate a requested mode against the environment; refuse unconfirmed LIVE."""
    check_mode_environment(requested, environment)
    if requested is TradingMode.LIVE and process_env.get(LIVE_TRADING_ENV_FLAG) != "true":
        raise TradingModeError(
            f"LIVE mode requires {LIVE_TRADING_ENV_FLAG}=true in the execution process environment"
        )
    return requested
