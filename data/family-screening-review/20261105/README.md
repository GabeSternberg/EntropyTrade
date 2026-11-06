# Family-screening evidence — 2026-11-05

Developed on branch `claude/vibrant-bohr-0m71vf`, starting from `main` at `55b2bea`.
**V1 remains incomplete.** This evidence supports the user's choice of a market family; it
does not make that choice.

## Files

| File | Contents |
|---|---|
| `command.txt` | The exact offline command, listing all 29 receipt inputs. |
| `retained-screen.json` | The deterministic report. Each input's SHA-256 is included. |
| `retained-screen.md` | The terminal table from the same run. |
| `fetch-attempt/manifest.json`, `fetch-attempt.log` | The single live catalog fetch attempt, and its failure. |
| `full-pytest-summary.log`, `full-pytest.log.gz`, `failed-tests.txt`, `failed-rerun-with-pr1-fix.log`, `screening-tests.log` | Test execution logs. |

## What was run

**Offline screen.** The screen read 29 retained receipts:

- 19 KXHIGHPHIL historical-catalog pages and 3 live-catalog pages (`data/public/kalshi-public`);
- 3 series-metadata receipts (`data/public/kalshi-fees`);
- 4 Bitcoin market captures (`data/bitcoin-history-review/20261028T232200Z/real-reviewed-history`).

Results:

- 4,576 unique markets.
- 0 tickers revised by a later `updated_time`.
- 92 tickers merged without an ordering clock. Live and historical KXHIGHPHIL pages disagree
  on open interest, and repeated Bitcoin polls show growing volume under one `updated_time`.
- A second run produced byte-identical JSON (`cmp`).

**Refusal check.** The screen correctly refuses
`data/public/kxhigh-scan/KXHIGHDEN/markets.json`, a per-ticker HTTP probe list rather than a
catalog, because its entries lack an `event_ticker`.

**Live fetch.** One attempt, `--fetch-series KXHIGHPHIL`, was not repeated. It recorded
`ConnectError: [Errno -2] Name or service not known`:

- The bounded transport ignores the environment proxy by design, and this container has no
  direct DNS or egress.
- Separately, this session's proxy answered 403 to a `CONNECT` request for
  `api.elections.kalshi.com`.

No fetched catalog exists, and none is claimed.

## Checks

- Ruff lint and format pass on the repository.
- Strict mypy passes on 558 source files.
- 25 screening tests pass.
- 25 screening tests pass again after the final rule-template change
  (`screening-tests.log`).
- **Full suite, run before that last template change** (which touched only the screening
  module): 1,285 passed and 57 failed in 554.06s (`full-pytest-summary.log`, `full-pytest.log.gz`).
  - The 57 failures are listed in `failed-tests.txt`. All of them are offline-recovery and
    listener paths hitting the pre-existing `main` defect `sqlite3.OperationalError: unable
    to open database file`, which PR #1 fixes.
  - In a scratch worktree of `main` with only PR #1's `api/recovery.py` and
    `api/recovery_proof.py` changes, all 57 pass in 239.63s (`failed-rerun-with-pr1-fix.log`).
  - No clean full-suite pass is claimed for this branch until PR #1 merges.

## Limitations

- Catalog fields show what was observed at fetch time. They are not point-in-time evidence
  for predictors.
- Volume is not executable depth.
- Fee types are not certified effective fees.
- The KXHIGHPHIL rule wording changed from the NWS Daily Climate Report to The Weather
  Company, so its older labels do not share current settlement semantics.
- The candidate series still need fetching in an environment with egress, followed by
  written user approval.
