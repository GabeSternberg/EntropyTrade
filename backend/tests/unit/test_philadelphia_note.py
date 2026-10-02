"""The Philadelphia note quotes the stored scores and does not add a model."""

from pathlib import Path

from entropytrade.weather.informational_rules import load_rule_scores
from entropytrade.weather.walk_forward import load_rule_walk_forward

ROOT = Path(__file__).resolve().parents[3]
NOTE = ROOT / "docs" / "research" / "philadelphia-daily-high.md"
PUBLIC = ROOT / "data" / "public"


def test_the_note_matches_the_stored_rules() -> None:
    text = NOTE.read_text(encoding="utf-8")
    assert "does not fit a model" in text
    assert "Four rules were tried" in text
    assert "None was promoted" in text
    assert "holdout 10" in text
    compact = text.replace(" ", "")
    scores = {rule.name: rule for rule in load_rule_scores(PUBLIC)}
    gap = scores["forecast_gap"].scenarios[0]
    assert f"{gap.assumed_fills}|{gap.equity}" in compact
    walked = load_rule_walk_forward(PUBLIC)
    assert walked.holdout_scored is False
    assert walked.promoted is False
    train = {rule.name: rule for rule in walked.train}["forecast_gap"].scenarios[0]
    validation = {rule.name: rule for rule in walked.validation}["forecast_gap"].scenarios[0]
    assert f"{train.assumed_fills}|{train.equity}" in compact
    assert f"{validation.assumed_fills}|{validation.equity}" in compact
