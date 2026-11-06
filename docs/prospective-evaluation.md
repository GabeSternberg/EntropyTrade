# Prospective shadow forecast evaluation

Start the private workbench with `uv run entropytrade-web`, select a saved shadow monitor,
and inspect **Prospective forecast evaluation**. Opening a report performs no acquisition,
fitting, strategy promotion or order submission. Use **Forecast evaluation JSON** and
**Forecast observations CSV** to export the current projection. Its hash identifies that report.

The panel shows pending, refused and matched observations, contract/poll counts, independent
events and target dates, outcome revisions, model probabilities and lineage. Expand **Forecast,
source and outcome lineage** for original feature/source/model clocks and subsequent retained
outcome receipts. Expand **Excluded, failed and interrupted evidence** for lifecycle/integrity
failures. Missing forecasts remain refusals even when an official outcome exists. A valid forecast
awaiting a verified official binary receipt stays pending. Invalid outcome responses remain
in its history with refusal reasons.

Selection is fixed: one earliest retained pre-close observation per contract. Repeated polls
never increase independent counts or replace earlier missing/refused forecasts. Equal-clock
conflicts refuse. Protected boundaries are unioned before projection; excluded features,
predictions and outcomes do not appear in report rows. Original receipt files, historical
partitions and prior reports are never rewritten.

Forecast groups separate real/synthetic data, frozen model version and calibration. Ten matched
events on five target dates permit descriptive Brier score, clipped log loss and fixed probability
reliability bins. Each event receives equal weight; its strike contracts divide that weight
equally. These minimums do not establish significance, model approval, historical validation or
profitability. Small or missing authentic evidence yields no metrics. Scored controlled examples
carry **CONTROLLED SYNTHETIC** labels. Depth, fee, signal and monetary-risk refusals remain visible
as the saved shadow decision; they do not invalidate an otherwise causal forecast.

Real reports verify cycle/database digests, checksummed artifacts, deterministic decision replay,
public source/contract bindings and the frozen data-only model's original scoring. Synthetic
replays verify computation and are never certified as public sources. Integrity failures withhold
the observation projection and all metrics because protected boundaries may be unverified.
Work stays bounded by 1,000 cycles/128 contracts per monitor and a 256 MB artifact-read
budget. Reports cover full bounded history, rather than just the latest 20 cycle cards.

Official outcomes must match original ticker, event, close, strike and rule terms, be final
non-provisional YES/NO results with matching payouts, and have settlement clocks between original
close and HTTP receipt. Availability starts at the receipt. The latest valid receipt at the cutoff
supplies the monitoring label; older versions remain visible. Later invalid/preliminary responses
do not erase a previously valid result. First accounting settlements stay frozen separately;
correcting account settlements is outside this milestone. Bounded revision checks run only while
the server/monitor run; reports cannot detect external changes without later authentic receipts.

Offline replay uses the same verifier:

```bash
uv run python -m entropytrade.tracking.prospective \
  --workspace data/cache/workbench --monitor MONITOR_UUID
```

Optional `--as-of 2026-10-31T12:00:00Z` restricts decisions/outcomes by original availability,
without backdating receipts. The default cutoff is the latest retained decision or outcome
receipt clock, not wall time. Snapshot/restore the paused workspace with the existing
`entropytrade.api.recovery` command to reproduce exact membership/hash. A growing workspace
includes new cycles/lifecycle changes; an old cutoff alone does not pin membership. Downloads
reflect evidence when each request is processed. Keep the workspace snapshot with an export.

`frontend/browser/prospective.spec.cjs` has two managed-Chromium procedures: synthetic scored
and authentic insufficient. Each uses real localhost pages, JSON/CSV downloads, restart,
offline CLI replay/restore, screenshots and byte comparisons, without intercepted browser routes
or personal browser profiles. Run once in a socket-permitted environment with fresh paths:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/prospective-evaluation-review/NEW/browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/prospective-browser-NEW" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  frontend/browser/node_modules/.bin/playwright test \
  -c frontend/browser/playwright.config.cjs prospective.spec.cjs --max-failures=1
```

Both procedures, the real-listener test and the complete pytest suite (1,320 tests) passed on
2026-11-05 in a socket-permitted runtime after a recovery portability fix (`uri=True` for
read-only SQLite URIs). See [current evidence](../data/prospective-evaluation-review/20261105/README.md),
including the disclosed Chromium build deviation (preinstalled build 1243 exposed at the pinned
1194 path because the pinned download was blocked). The [October 31 evidence](../data/prospective-evaluation-review/20261031/README.md)
retains the earlier denied attempts. Browser discovery, DOM tests and offline exports do not
count as browser interaction/download acceptance.
