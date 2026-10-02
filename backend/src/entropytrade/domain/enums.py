"""Small closed vocabularies shared across the domain."""

from enum import StrEnum


class Venue(StrEnum):
    KALSHI = "kalshi"


class KalshiEnvironment(StrEnum):
    DEMO = "demo"
    PRODUCTION = "production"


class OutcomeSide(StrEnum):
    """Which outcome a position or order is long.

    Mirrors Kalshi's ``outcome_side``: buying YES and selling NO are the same exposure, so the
    domain only records the resulting side (plus ``reduce_only`` when closing).
    """

    YES = "yes"
    NO = "no"

    @property
    def opposite(self) -> "OutcomeSide":
        return OutcomeSide.NO if self is OutcomeSide.YES else OutcomeSide.YES


class MarketStatus(StrEnum):
    """Kalshi market lifecycle statuses (``GET /markets``)."""

    INITIALIZED = "initialized"
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    DETERMINED = "determined"
    DISPUTED = "disputed"
    AMENDED = "amended"
    FINALIZED = "finalized"

    @property
    def is_tradable(self) -> bool:
        return self is MarketStatus.ACTIVE

    @property
    def has_result(self) -> bool:
        return self in _STATUSES_WITH_RESULT


_STATUSES_WITH_RESULT = frozenset(
    {MarketStatus.DETERMINED, MarketStatus.DISPUTED, MarketStatus.AMENDED, MarketStatus.FINALIZED}
)


class MarketType(StrEnum):
    BINARY = "binary"
    SCALAR = "scalar"


class MarketResult(StrEnum):
    YES = "yes"
    NO = "no"
    SCALAR = "scalar"


class StrikeType(StrEnum):
    GREATER = "greater"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS = "less"
    LESS_OR_EQUAL = "less_or_equal"
    BETWEEN = "between"
    FUNCTIONAL = "functional"
    CUSTOM = "custom"
    STRUCTURED = "structured"


class TimeInForce(StrEnum):
    FILL_OR_KILL = "fill_or_kill"
    GOOD_TILL_CANCELED = "good_till_canceled"
    IMMEDIATE_OR_CANCEL = "immediate_or_cancel"


class LiquidityRole(StrEnum):
    MAKER = "maker"
    TAKER = "taker"


class FeeType(StrEnum):
    """Kalshi series fee structures (OpenAPI ``FeeType``)."""

    QUADRATIC = "quadratic"
    QUADRATIC_WITH_MAKER_FEES = "quadratic_with_maker_fees"
    QUADRATIC_WITH_COMBO_MAKER_FEES = "quadratic_with_combo_maker_fees"
    FLAT = "flat"


class StrategyFamily(StrEnum):
    """Informational strategies forecast reality; structural ones exploit price inconsistencies."""

    INFORMATIONAL = "informational"
    STRUCTURAL = "structural"


class FillScenario(StrEnum):
    OPTIMISTIC = "optimistic"
    BASE = "base"
    CONSERVATIVE = "conservative"


class ExecutionFidelity(StrEnum):
    """How much market microstructure a backtest could see. Lower fidelity must be labelled."""

    ORDER_BOOK = "order_book"
    TRADES_AND_QUOTES = "trades_and_quotes"
    CANDLES_ONLY = "candles_only"


class ActorKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class RiskSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HALT = "halt"
