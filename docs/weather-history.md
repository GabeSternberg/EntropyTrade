# Retained weather research

The private workbench can freeze authentic forward/shadow receipts into an immutable
weather dataset and run the existing research, modeling and experiment workflow against
that exact selection. It performs no network requests while building a snapshot. Binary
Kalshi outcomes never substitute for source-matched scalar temperature highs.

Run `uv run entropytrade-web`, open the printed localhost address, and collect public
weather receipts or use a completed weather shadow cycle in that workspace. Click
**Freeze retained weather dataset**. Inspect the event/date counts, original capture
failures, known forecasts, matched labels and partition shortages. Select the dataset,
choose **Retained weather dataset**, enter an idea and start research. When snapshots exist,
the page defaults to the retained route. The legacy six-event sample remains available.
Local templates require no credentials. External-provider verification is deferred until
credentials are separately authorized; existing configured-provider consent gates remain.

Results show the selected dataset identity and readiness on every tab. **Review JSON** and
**Text report** download the ordinary deterministic experiment or explicit insufficiency
result. Returning after restart preserves the datasets, queued request references and
completed download bytes. Unfinished jobs become interrupted; retry is explicit.

Committed shadow-cycle digests and artifact inventories are checked before ingestion.

Snapshots live at `runs/weather-datasets/<digest>/` within the workspace. A snapshot copies
checksummed original capture files, retains dataset rows, observations and feature artifacts,
and verifies its complete inventory before atomic publication. The content identity includes
input versions, outcome receipts, frozen protection and implementation hashes. A repeated
freeze reuses the same version. New receipts create a separate version. An interrupted
staging directory is rebuilt on the next explicit freeze; completed versions are never
rewritten. Verified workspace snapshot/restore includes these files and validates references.

Decisions use actual capture times while the contract was open, including captures made
before its target day. Repeated `(contract, decision)` rows are deduplicated. Identical
forecast vintages use their earliest retained authentic receipt; corrected values retain
separate revision clocks. Conflicting values within a revision are refused. Later rules
cannot backfill a decision. Completed shadow outcome summaries are independently checked
against hashed finalized exchange receipts and the original contract terms; the first
matching receipt establishes binary-label availability. Changed, provisional, disputed,
mismatched or corrupt outcomes cannot become training labels.

The first snapshot freezes target-date partitions from its earliest verified target date:
48 days for fitting, 12 for calibration, 30 for validation, then protected final holdout.
These dates never roll forward. Existing source/model protections carry forward; protected
scalar labels cannot enter prior-error features. Inputs preceding the frozen anchor require
an explicitly reviewed separate partition. Fitting and calibration use labels available by
the first actual decision in the next partition. Later/overnight decisions cannot enter an
earlier fit. The existing minimums remain: 60 training events, 20 calibration events,
20 evaluation events, 200 for boosting, and at least ten dates. Diagnostic baseline behavior
and explicit calibration refusals remain governed by the existing model engine.
Final holdout is never evaluated; retained runs do not use rolling walk-forward diagnostics.

A snapshot is bounded to 128 input captures/cycles and 256 MB of retained input files.
Exceeding those budgets fails explicitly, without silently discarding history. Source
capture failures stay visible; collection completeness is separate from job completion.
Missing labels, unsupported source semantics, short partitions, uncertified fees and absent
historical depth remain blockers. A software workflow can pass while empirical validation
and profitability remain absent.

## Executable acceptance

The new unit tests distinguish authentic receipt replay from controlled scalar/outcome
mutations and synthetic fitting. The listener test uses ordinary subprocess workers and
checks downloads, cancellation, interruption and offline restore:

```bash
uv run pytest backend/tests/unit/test_weather_history.py \
  backend/tests/integration/test_weather_history_listener.py -q
```

The Playwright harness imports two verified October 29 public captures from retained shadow
cycles into a **new** workspace. It never edits their clocks, intercepts HTTP or replaces
workers. Actual browser interaction freezes/selects the dataset, runs research, inspects
all tabs, downloads artifacts and verifies them after server restart. This is authentic
receipt ingestion/replay, not new source acquisition or an empirical strategy evaluation.

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/weather-history-review/new-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/new-weather-acceptance" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser test -- --grep 'authentic retained weather'
```

The workspace gets a `-weather-history` suffix. Use new absolute paths for each attempt.
The fresh-install acceptance driver exports the exact two required authentic public
captures and includes this procedure in its default browser selection. A denied launch or
listener remains a failed attempt; no mocked request test counts as browser acceptance.
Current results and remaining limitations are in the
[milestone evidence bundle](../data/weather-history-review/20261030/README.md).


The sustained-history extension adds browser-selectable partitions and verified shadow
books/decision clocks. Workspaces exceeding 128 cycles can select bounded capture and
later outcome partitions without deleting receipts or shifting calendar boundaries.
See [sustained shadow history](shadow-history.md) for behavior, evidence and the current
outstanding browser acceptance step; earlier browser passes describe their original checkout.
