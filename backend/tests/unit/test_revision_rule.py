"""The revision rule stays frozen. A missing vintage is not a score."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    PRICE_THRESHOLD,
)
from entropytrade.weather.revision_rule import (
    EARLIER_HOUR_UTC,
    REVISION_MINIMUM_F,
    load_revision,
    revision_lines,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "revision_rule.py"
)
_ERROR = '{"error":true,"reason":"Parameter \'run\' must not be set"}'


def test_two_vintages_were_refused() -> None:
    attempt = load_revision(ROOT)
    assert attempt.name == "forecast_revision_up"
    assert attempt.hypotheses == 1
    assert attempt.scored is False
    assert attempt.promoted is False
    assert attempt.two_vintages is False
    assert attempt.guaranteed_fill is False
    assert attempt.fidelity == "trade-print"
    assert attempt.http_status == 400
    assert attempt.error_body == _ERROR
    assert attempt.fires == "not scored"
    assert attempt.fills == "not scored"
    assert attempt.optimistic_equity == "not scored"
    assert attempt.validation_equity == "not scored"
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("0.4000") == PRICE_THRESHOLD
    assert Decimal(2) == REVISION_MINIMUM_F
    assert EARLIER_HOUR_UTC == 3
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    lines = "\n".join(revision_lines(ROOT))
    assert "Nothing was promoted." in lines
    assert _ERROR in lines
    assert "not scored" in lines
