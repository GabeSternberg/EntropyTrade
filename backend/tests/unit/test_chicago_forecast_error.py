"""Chicago forecast error uses the existing mean absolute error. No new model."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_forecast_error

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_the_stored_forecast_error_is_not_a_model() -> None:
    error = load_chicago_forecast_error(ROOT)
    assert error.days == 40
    assert error.mae == Decimal("2.4175")
    assert error.fitted_model is False
    assert error.promoted is False
