"""Walk-forward on stored CLI days. The holdout is not run."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.walk_forward import load_stored_walk_forward

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_stored_days_walk_forward_skips_the_holdout() -> None:
    result = load_stored_walk_forward(ROOT)
    assert result.train_days == 20
    assert result.validation_days == 10
    assert result.holdout_days == 10
    assert result.ran_splits == ("train", "validation")
    assert result.holdout_blocked is True
    assert result.replay_fills == 0
    assert result.replay_equity == Decimal("100.000000")
    assert result.promoted is False
    assert result.train_mae == Decimal("2.94")
    assert result.validation_mae == Decimal("2.53")


def test_walk_forward_does_not_call_a_provider() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/walk_forward.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "pydantic_ai", "openai", "anthropic"):
        assert name not in text
