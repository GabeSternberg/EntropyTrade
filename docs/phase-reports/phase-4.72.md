---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.72 checkpoint

Date: 2026-10-02. Phase 4.72 is complete. It is off-plan work. No order was
sent. The 0.50 line and the 15:00 UTC decision were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.72.md`.

## What was scored

On each of the 40 stored CLI days, the guess uses the last `B80.5` print
from the 2026 tape whose time is at or before 15:00 UTC and strictly before
the label's `available_at`. A price at or above 0.50 would be a YES guess.
A lower price is a NO guess. A day with no such print gets no guess. If
several prints share the last timestamp, the guess uses the highest YES
price. The historical trade table is not read. The print is not a
guaranteed fill.

10 days have an eligible print. 30 do not. None of the 10 prices are at or
above 0.50, so every guess is NO. 9 of those 10 match the bracket: the CLI
high is outside 80 to 81. The miss is 25 August 2026. The print is 0.1000
and the CLI high is 80, so the bracket resolves YES. Fidelity stays
`trade-print`. Nothing is promoted. CLI replay equity stays 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 209 passed
(207 from Phase 4.71, plus 2 pre-decision guess checks).

## Files

- `backend/src/entropytrade/weather/cli_print_guess.py`
- `backend/tests/unit/test_cli_print_guess.py`
