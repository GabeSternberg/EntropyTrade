"""Phase 4 questions on the CLI labels, the broader public tape, and stored fees.

Candlesticks are not books. The taker coefficient stays unset because the
vendored docs and the stored series payload do not state one. Nothing is fit
and nothing is promoted.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.backtest.replay import DecisionView, ReplayResult, run_replay
from entropytrade.domain.enums import FeeType
from entropytrade.domain.market_data import OrderBook
from entropytrade.domain.orders import OrderIntent
from entropytrade.domain.runs import SampleSplit, SplitWindow
from entropytrade.exchange.cli_window import load_cli_window
from entropytrade.execution.fees import FeeSchedule
from entropytrade.execution.paper import PaperBroker
from entropytrade.execution.published_fees import PUBLISHED_FEE_VERSION, QUADRATIC_COEFFICIENT
from entropytrade.execution.series_fees import FEE_MODEL_VERSION, load_series_fees
from entropytrade.portfolio.ledger import Ledger
from entropytrade.risk.engine import RiskEngine, RiskLimits
from entropytrade.weather.settlement_score import load_aligned_score

_SERIES = "KXHIGHPHIL"


@dataclass(frozen=True)
class TapeRescore:
    """Stored-row answers. ``trades`` is true only when a fill exists."""

    scored_days: int
    mae: Decimal
    mae_first_half: Decimal
    mae_second_half: Decimal
    probability_days: int
    brier_raw: Decimal
    brier_climatology: Decimal
    brier_calibrated: Decimal
    forecast_signal_days: int
    sized_books_before_label: int
    empty_books_in_window: int
    candles_stored: int
    replay_fills: int
    replay_equity: Decimal
    equity_at_two_hour_latency: Decimal
    fee_model_version: str
    published_fee_version: str
    series_fee_type: str
    maker_fraction: Decimal
    quadratic_coefficient: Decimal | None
    fitted_model: bool
    promoted: bool

    @property
    def trades(self) -> bool:
        return self.replay_fills > 0

    def questions(self) -> tuple[str, str, str, str, str]:
        """The five Phase 4 questions, in spec order, from these fields only."""
        predictive = (
            f"The previous-day forecast has MAE {self.mae} °F on {self.scored_days} CLI days. "
            f"It resolves the 80-81 strike on {self.forecast_signal_days} days. "
            f"Raw Brier is {self.brier_raw} against climatology {self.brier_climatology} "
            f"on {self.probability_days} days. "
            "No sized book supplies a market probability before the label."
        )
        incremental = (
            f"The calibrated blend Brier is {self.brier_calibrated}. "
            "It does not beat the raw forecast. No model was fit. "
            "Candles were not used as a market feature."
        )
        edge = (
            "The rule does not trade. "
            f"Fills are {self.replay_fills} and equity stays {self.replay_equity}. "
            f"{_SERIES} is {self.series_fee_type} with maker fraction {self.maker_fraction}. "
            "The taker coefficient is unpublished, so no costed edge is claimed."
        )
        stability = (
            f"MAE is {self.mae_first_half} in the first half and "
            f"{self.mae_second_half} in the second. "
            f"Both halves leave the replay at {self.replay_fills} fills."
        )
        sensitivity = (
            f"{self.empty_books_in_window} current books in the window are empty and "
            f"{self.candles_stored} candles have no touch size. "
            "A two-hour latency on that tape still ends at "
            f"{self.equity_at_two_hour_latency}. "
            "The unpublished coefficient was not swept."
        )
        return predictive, incremental, edge, stability, sensitivity


def load_tape_rescore(root: Path) -> TapeRescore:
    """Join the CLI score, the CLI-window tape, and the stored series fee."""
    aligned = load_aligned_score(root)
    tape = load_cli_window(root)
    fees = load_series_fees(root)
    series = fees.match(_SERIES)
    if series.fee_type is not FeeType.QUADRATIC:
        raise ValueError(f"{_SERIES} fee type is not the stored quadratic schedule")
    books: tuple[OrderBook, ...] = ()
    if tape.sized_books != 0 or aligned.sized_books_in_window != 0:
        raise ValueError("a sized book appeared; the rescore must use those rows explicitly")
    if aligned.replay_fills != 0 or aligned.replay_equity != Decimal("100.000000"):
        raise ValueError("the forecast rule traded on a stored book")
    immediate = _replay(books, latency=timedelta(0), fees_root=root)
    delayed = _replay(books, latency=timedelta(hours=2), fees_root=root)
    if immediate.fee_model_version != FEE_MODEL_VERSION:
        raise ValueError("replay did not record the stored series fee version")
    if immediate.ending_equity != aligned.replay_equity or delayed.fill_ids:
        raise ValueError("the fee-model replay does not match the forecast rule")
    return TapeRescore(
        scored_days=aligned.scored_days,
        mae=aligned.mae,
        mae_first_half=aligned.mae_first_half,
        mae_second_half=aligned.mae_second_half,
        probability_days=aligned.probability_days,
        brier_raw=aligned.brier_raw,
        brier_climatology=aligned.brier_climatology,
        brier_calibrated=aligned.brier_calibrated,
        forecast_signal_days=aligned.forecast_signal_days,
        sized_books_before_label=aligned.sized_books_in_window + tape.sized_books,
        empty_books_in_window=tape.orderbook_empty,
        candles_stored=tape.candles_stored,
        replay_fills=aligned.replay_fills,
        replay_equity=aligned.replay_equity,
        equity_at_two_hour_latency=delayed.ending_equity,
        fee_model_version=immediate.fee_model_version or "",
        published_fee_version=PUBLISHED_FEE_VERSION,
        series_fee_type=series.fee_type.value,
        maker_fraction=series.maker_fraction,
        quadratic_coefficient=QUADRATIC_COEFFICIENT,
        fitted_model=aligned.fitted_model,
        promoted=aligned.promoted,
    )


def _replay(
    books: tuple[OrderBook, ...],
    *,
    latency: timedelta,
    fees_root: Path,
) -> ReplayResult:
    start = datetime(2026, 8, 23, tzinfo=UTC)
    ledger = Ledger(Decimal("100"), as_of=start)

    def trade(view: DecisionView, book: OrderBook) -> OrderIntent | None:
        del view, book
        return None

    return run_replay(
        books=books,
        records=(),
        strategy=trade,
        ledger=ledger,
        broker=PaperBroker(
            ledger,
            FeeSchedule(
                fee_type=FeeType.QUADRATIC,
                fee_multiplier=Decimal(1),
                maker_pays=False,
                quadratic_coefficient=Decimal(0),
            ),
        ),
        engine=RiskEngine(
            RiskLimits(
                bankroll=Decimal("100"),
                per_trade=Decimal("100"),
                per_event=Decimal("100"),
                total_deployed=Decimal("100"),
                max_loss=Decimal("50"),
                max_drawdown=Decimal("50"),
                max_book_age_seconds=86400,
                min_liquidity=Decimal("1.00"),
                max_spread=Decimal("0.2000"),
                config_version="tape-rescore-v1",
            )
        ),
        latency=latency,
        window=SplitWindow(
            split=SampleSplit.TRAIN,
            start=start,
            end=datetime(2026, 10, 3, tzinfo=UTC),
        ),
        series_fees=load_series_fees(fees_root),
    )
