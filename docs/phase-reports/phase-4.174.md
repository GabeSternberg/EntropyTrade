---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.174 checkpoint

Date: 2026-10-03. Phase 4.174 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.174.md`.

## Rule

This record rule was written before the downward records were counted.

A prediction record is one train or validation day of
`forecast_revision_down` on a city already scored on that rule. The
holdout is not recorded. A day with a missing vintage, or a vintage clock
after 15:00 UTC or at or after the label, is not a decision.

`probability_yes` is 1 when revision <= -2°F and 0 otherwise. That is the
frozen downward fire. It is not a new threshold. The market ticker is the
stored between-contract selected by that rule. If the rule fires and no
stored contract contains the later max, the ticker is `no-stored-bracket`,
which is not a Kalshi market. A day that does not fire also uses that
ticker, because no contract was selected. Bid, ask, and net edge stay
empty. A print is not a quote. The upward revision records are not
rewritten. Nothing is promoted.

## Result

551 train and validation days became downward records. 227 of them have
`probability_yes` 1. Philadelphia accounts for 18 of those fires. The
other 324 did not fire, so their ticker is `no-stored-bracket`. The
upward file still has 551 records, and the two id sets do not overlap.
The CLI rescore ids do not overlap either. Bid, ask, net edge,
uncertainty, and calibration are empty. The holdout is not recorded.
`2°F` and `0.40` were not changed. Nothing was promoted.
`docs/research/kxhigh-scan.md` includes the downward record sentence.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 277 passed.
