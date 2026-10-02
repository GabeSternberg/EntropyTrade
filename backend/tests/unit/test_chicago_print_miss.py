"""The one Chicago pre-decision print that misses the CLI bracket."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.trade_prints import load_trade_tape
from entropytrade.weather.chicago_rules import load_chicago_print_disagreements
from entropytrade.weather.cli_observations import load_comparison
from entropytrade.weather.cli_print_guess import DECISION_HOUR, print_disagreements
from entropytrade.weather.last_print import GUESS_YES_AT

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_september_29_is_the_only_chicago_miss() -> None:
    assert Decimal("0.50") == GUESS_YES_AT
    assert DECISION_HOUR == 15
    misses = load_chicago_print_disagreements(ROOT)
    assert len(misses) == 1
    miss = misses[0]
    assert miss.valid_on == date(2026, 9, 29)
    assert miss.yes_price == Decimal("0.02")
    assert miss.high_f == Decimal(80)
    assert miss.created_at == datetime(2026, 9, 29, 14, 42, 56, 655073, tzinfo=UTC)
    assert miss.created_at < datetime(2026, 9, 29, 15, tzinfo=UTC)
    assert miss.guess_yes is False
    assert miss.bracket_yes is True
    labels, _comparison = load_comparison(ROOT)
    philadelphia = print_disagreements(labels, load_trade_tape(ROOT).b805_prints)
    assert len(philadelphia) == 1
    assert philadelphia[0].valid_on == date(2026, 8, 25)
    assert philadelphia[0].yes_price == Decimal("0.1000")
    assert philadelphia[0].high_f == Decimal(80)
    assert philadelphia[0].created_at == datetime(2026, 8, 25, 14, 58, 7, 443186, tzinfo=UTC)
    assert philadelphia[0].guess_yes is False
    assert philadelphia[0].bracket_yes is True
