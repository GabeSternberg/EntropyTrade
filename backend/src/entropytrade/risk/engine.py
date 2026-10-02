"""Deterministic risk gate. Strategies do not get a path around it.

An intent is sized down to the tightest cap. A failed check rejects the whole intent.
``seal`` is what turns a decision into the only object the paper broker accepts, and it
raises when the decision did not approve.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import OutcomeSide
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.numeric import (
    QUANTITY_QUANTUM,
    ZERO,
    NonNegativeMoney,
    Price,
    Quantity,
    cost_per_contract,
)
from entropytrade.domain.orders import ApprovedOrderIntent, OrderIntent
from entropytrade.domain.portfolio import PortfolioSnapshot
from entropytrade.domain.risk import RiskCheckResult, RiskDecision
from entropytrade.domain.time import UtcDatetime

HALT_SENTINEL_NAME = "HALT"


def halt_sentinel(directory: Path) -> Path:
    """Local HALT file. The engine blocks new orders while this path exists."""
    return directory / HALT_SENTINEL_NAME


class RiskLimits(DomainModel):
    """Caps the engine enforces. None of these can be raised by a strategy spec."""

    bankroll: NonNegativeMoney
    per_trade: NonNegativeMoney
    per_event: NonNegativeMoney
    total_deployed: NonNegativeMoney
    max_loss: NonNegativeMoney
    max_drawdown: NonNegativeMoney
    max_book_age_seconds: int
    min_liquidity: Quantity
    max_spread: Price
    config_version: str


class RiskRejectedError(Exception):
    """``seal`` refused a decision that did not approve the intent."""

    def __init__(self, decision: RiskDecision) -> None:
        names = ", ".join(check.check_name for check in decision.failed_checks)
        super().__init__(f"risk rejected the intent: {names}")
        self.decision = decision


class RiskEngine:
    """Pure checks plus a kill switch. Evaluating an intent does not change the ledger."""

    def __init__(
        self,
        limits: RiskLimits,
        *,
        halt_file: Path | None = None,
        environ: Mapping[str, str] | None = None,
        trading_enabled: bool = True,
    ) -> None:
        self._limits = limits
        self._halt_file = halt_file
        self._environ = environ if environ is not None else {}
        self.trading_enabled = trading_enabled
        self.killed = False

    def kill(self) -> None:
        self.killed = True

    def resume(self) -> None:
        """Clear the in-process halt. A HALT file or a disabled flag still blocks."""
        self.killed = False

    def halted(self) -> bool:
        """True when any independent stop is on. New orders must not be approved."""
        if self.killed or not self.trading_enabled:
            return True
        if self._halt_file is not None and self._halt_file.is_file():
            return True
        enabled = self._environ.get("ENTROPYTRADE_TRADING_ENABLED", "true")
        return enabled.lower() != "true"

    def evaluate(
        self,
        intent: OrderIntent,
        *,
        portfolio: PortfolioSnapshot,
        book: OrderBook,
        now: datetime,
        event_deployed: Decimal,
        realized_pnl: Decimal,
        peak_equity: Decimal,
        equity: Decimal,
    ) -> RiskDecision:
        checks: list[RiskCheckResult] = []
        blocked = _gate(
            checks,
            intent=intent,
            book=book,
            now=now,
            limits=self._limits,
            killed=self.halted(),
            realized_pnl=realized_pnl,
            peak_equity=peak_equity,
            equity=equity,
        )
        if blocked:
            return _decision(
                intent,
                approved=False,
                quantity=ZERO,
                checks=checks,
                limits=self._limits,
                now=now,
            )
        quantity = _sized(
            checks,
            intent=intent,
            book=book,
            portfolio=portfolio,
            event_deployed=event_deployed,
            limits=self._limits,
        )
        return _decision(
            intent,
            approved=quantity > ZERO,
            quantity=quantity,
            checks=checks,
            limits=self._limits,
            now=now,
        )


def seal(intent: OrderIntent, decision: RiskDecision) -> ApprovedOrderIntent:
    """Build the broker's input. A rejection cannot be sealed."""
    try:
        return ApprovedOrderIntent(intent=intent, decision=decision)
    except ValueError as exc:
        raise RiskRejectedError(decision) from exc


def _decision(
    intent: OrderIntent,
    *,
    approved: bool,
    quantity: Decimal,
    checks: list[RiskCheckResult],
    limits: RiskLimits,
    now: UtcDatetime,
) -> RiskDecision:
    if not approved:
        failed = [check for check in checks if not check.passed]
        if not failed:
            checks.append(
                RiskCheckResult(
                    check_name="unapproved",
                    passed=False,
                    detail="quantity is zero",
                )
            )
    return RiskDecision(
        intent_id=intent.intent_id,
        approved=approved,
        approved_quantity=quantity if approved else ZERO,
        checks=tuple(checks),
        risk_config_version=limits.config_version,
        decided_at=now,
    )


def _gate(
    checks: list[RiskCheckResult],
    *,
    intent: OrderIntent,
    book: OrderBook,
    now: datetime,
    limits: RiskLimits,
    killed: bool,
    realized_pnl: Decimal,
    peak_equity: Decimal,
    equity: Decimal,
) -> bool:
    checks.append(
        RiskCheckResult(
            check_name="kill_switch",
            passed=not killed,
            detail="killed" if killed else "",
        )
    )
    age = (now - book.received_at).total_seconds()
    stale = age > limits.max_book_age_seconds
    checks.append(
        RiskCheckResult(
            check_name="stale_book",
            passed=not stale,
            observed=str(age),
            limit=str(limits.max_book_age_seconds),
        )
    )
    checks.append(RiskCheckResult(check_name="crossed_book", passed=not book.is_crossed))
    spread = book.spread
    spread_ok = spread is not None and spread <= limits.max_spread and spread > ZERO
    checks.append(
        RiskCheckResult(
            check_name="max_spread",
            passed=spread_ok,
            observed=None if spread is None else str(spread),
            limit=str(limits.max_spread),
        )
    )
    loss = -realized_pnl
    checks.append(
        RiskCheckResult(
            check_name="loss_limit",
            passed=loss < limits.max_loss,
            observed=str(loss),
            limit=str(limits.max_loss),
        )
    )
    drawdown = peak_equity - equity
    checks.append(
        RiskCheckResult(
            check_name="drawdown",
            passed=drawdown < limits.max_drawdown,
            observed=str(drawdown),
            limit=str(limits.max_drawdown),
        )
    )
    if intent.post_only:
        touch = _touch_size(book)
    else:
        touch = _take_size(book, intent.contract.side, intent.yes_price)
    liquid = touch >= limits.min_liquidity
    checks.append(
        RiskCheckResult(
            check_name="min_liquidity",
            passed=liquid,
            observed=str(touch),
            limit=str(limits.min_liquidity),
        )
    )
    return any(not check.passed for check in checks)


def _sized(
    checks: list[RiskCheckResult],
    *,
    intent: OrderIntent,
    book: OrderBook,
    portfolio: PortfolioSnapshot,
    event_deployed: Decimal,
    limits: RiskLimits,
) -> Decimal:
    price = cost_per_contract(intent.contract.side, intent.yes_price)
    deployed = portfolio.capital_at_risk
    rooms = (
        ("per_trade", limits.per_trade),
        ("per_event", limits.per_event - event_deployed),
        ("total_deployed", limits.total_deployed - deployed),
        ("bankroll", limits.bankroll - deployed),
    )
    quantity = intent.quantity
    if not intent.post_only:
        quantity = min(quantity, _take_size(book, intent.contract.side, intent.yes_price))
    for name, room in rooms:
        allowed = _qty_for_room(price, room, quantity)
        checks.append(
            RiskCheckResult(
                check_name=name,
                passed=allowed > ZERO,
                observed=str(room),
                limit=str(quantity),
            )
        )
        quantity = allowed
    return quantity


def _qty_for_room(price_per: Decimal, room: Decimal, cap: Decimal) -> Decimal:
    if room <= ZERO or price_per <= ZERO or cap <= ZERO:
        return ZERO
    fitted = (room / price_per).quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN)
    if fitted <= ZERO:
        return ZERO
    return min(fitted, cap)


def _take_size(book: OrderBook, side: OutcomeSide, yes_limit: Decimal) -> Decimal:
    total = ZERO
    levels = book.asks if side is OutcomeSide.YES else book.bids
    for level in levels:
        if side is OutcomeSide.YES:
            marketable = level.price <= yes_limit
        else:
            marketable = level.price >= yes_limit
        if not marketable:
            break
        total += level.quantity
    return total


def _touch_size(book: OrderBook) -> Decimal:
    bid = book.best_bid.quantity if book.best_bid is not None else ZERO
    ask = book.best_ask.quantity if book.best_ask is not None else ZERO
    return bid + ask
