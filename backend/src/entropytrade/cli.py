"""Command line entry point. Phase 0 only reports the version; it does not trade."""

from entropytrade import __version__
from entropytrade.domain.modes import DEFAULT_TRADING_MODE


def main() -> None:
    print(f"entropytrade {__version__} (default trading mode: {DEFAULT_TRADING_MODE.value})")
