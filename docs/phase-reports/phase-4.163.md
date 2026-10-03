---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.163 checkpoint

Date: 2026-10-03. Phase 4.163 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.163.md`.

## Rule

This record rule was written before the records were counted.

A prediction record is one train or validation day of
`forecast_revision_bracket` on a city already scored. The holdout is not
recorded. A day with a missing vintage, or a vintage clock after 15:00 UTC
or at or after the label, is not a decision.

`probability_yes` is 1 when revision >= 2°F and 0 otherwise. That is the
frozen fire rule. It is not a new threshold. The market ticker is the
stored between-contract selected by that rule. If the rule fires and no
stored contract contains the later max, the ticker is `no-stored-bracket`,
which is not a Kalshi market. Bid, ask, and net edge stay empty. A print is
not a quote. Nothing is promoted.

## Result

551 train and validation days became records. 91 of them have
`probability_yes` 1. The other 460 did not fire, so their ticker is
`no-stored-bracket`. That string is not a Kalshi market. A day that did
not fire does not receive a traded ticker.

Three fires selected a stored contract: Philadelphia train 2026-09-10
`KXHIGHPHIL-26SEP10-B88.5`, Boston validation 2026-09-17
`KXHIGHTBOS-26SEP17-B80.5`, and San Diego train 2026-09-02
`KXHIGHTSAN-26SEP02-B80.5`. The other 88 fires have no stored
between-contract containing the later max. `2°F` and `0.40` were not
changed after those tickers were known.

The holdout is not in the file. Bid, ask, net edge, uncertainty, and
calibration are empty. The CLI rescore records are unchanged. Nothing was
promoted. `docs/research/kxhigh-scan.md` includes the record sentence.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 266 passed.
