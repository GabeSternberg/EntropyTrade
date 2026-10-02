"""The Chicago note quotes the stored scores and does not add a model."""

from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_score, load_chicago_walk_forward

ROOT = Path(__file__).resolve().parents[3]
NOTE = ROOT / "docs" / "research" / "chicago-daily-high.md"
PUBLIC = ROOT / "data" / "public"


def test_the_note_matches_the_stored_chicago_rules() -> None:
    text = NOTE.read_text(encoding="utf-8")
    assert "does not fit a model" in text
    assert "Four rules were tried" in text
    assert "None was promoted" in text
    assert "Optimistic trade-print equity is not a fill" in text
    assert "holdout 10" in text
    compact = text.replace(" ", "")
    scores = {rule.name: rule for rule in load_chicago_score(PUBLIC).rules}
    assert len(scores) == 4
    for rule in scores.values():
        optimistic = rule.scenarios[0]
        assert f"{optimistic.assumed_fills}|{optimistic.equity}" in compact
        assert rule.promoted is False
    walked = load_chicago_walk_forward(PUBLIC)
    assert walked.holdout_scored is False
    assert walked.promoted is False
    for fold in (walked.train, walked.validation):
        for rule in fold:
            optimistic = rule.scenarios[0]
            needle = (
                f"{rule.fires}|{rule.claim_hits}|{optimistic.assumed_fills}|{optimistic.equity}"
            )
            assert needle in compact
            assert f"{rule.scenarios[1].equity}" in text
            assert f"{rule.scenarios[2].equity}" in text
