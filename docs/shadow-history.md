# Sustained shadow history to reproducible experiments

Open the private local workbench with `uv run entropytrade-web`. Under **Retained weather
history**, refresh the catalog, select a **History partition**, optionally select a later
**Outcome partition**, and freeze the dataset. Select the immutable weather dataset and
submit a research idea. Review shortages, shadow lineage and execution blockers on every
results tab. Download **Review JSON**, **Text report** and **Shadow experiment inputs**.

Each selection processes at most 128 committed captures and 128 outcome cycles, with the
existing 256 MB input budget. The catalog enumerates all eligible completed inputs; it
does not delete receipts or silently select the most recent 128. Missing/failed/interrupted
cycles remain in monitor evidence but are not eligible completed inputs. Catalog membership
is hashed. A changing partial partition or unknown selection is refused with a refresh
message; previously frozen datasets remain usable. Select another partition to inspect
other retained history.

To research multiple partitions together, select **Cohort history partitions**, optionally
select **Cohort outcome partitions**, and click **Freeze research cohort**. Use Ctrl/Cmd
to select several entries. With no outcome selection, all selected history partitions
supply their retained shadow outcomes. Select one to eight distinct partitions of each
kind. Cohorts retain the 256 MB aggregate raw-input budget and existing model minimums;
excess selections refuse rather than truncating history. A changed partial partition must
be refreshed; published datasets remain usable by their immutable IDs.

Each history partition first becomes an immutable bounded batch under
`runs/weather-datasets/.batches`. Completed batches survive a process interruption and are
verified/reused on explicit retry. Only complete cohorts appear in the dataset selector.
Final assembly uses the frozen batch receipts, then rebuilds point-in-time features jointly
through the same snapshot pipeline. This supports history/bias joins across batch boundaries;
it does not concatenate preengineered features or average partition performance. The shared
frozen calendar and union of source/model/snapshot protections apply before any batch is
built. Independent event counts deduplicate repeated captures. Cohort metadata and batch
identities remain visible on every results tab and in the downloaded review. Offline
snapshot/restore verifies both completed batch snapshots and final datasets.

The calendar anchor is computed from checksummed market metadata across the workspace,
including when the first selected partition is a later one. The initial 48/12/30-day
training/calibration/validation boundaries remain fixed across later selections. Existing
snapshots and frozen model protections are inherited. Adding an earlier-than-frozen
anchor refuses rather than moving boundaries. Metadata scanning is proportional to retained
history; receipt parsing, feature construction and replay work are bounded by the selected
partitions. Large selections can take several seconds and remain under the existing single
snapshot build lock.

A shadow capture must match its committed database digest, artifacts and saved result.
Its decisions must reproduce with the existing deterministic evaluator. Separately, each
saved source version, original feature vector/hash and availability clock is checked
against the public receipt adapter. Every saved book must match a unique successful raw
GET and be available by its actual decision clock. Consistent replay by itself cannot
certify these source bindings. Rehashed but forged source/clock/book changes are refused.

Blocked decisions received after market close remain in the saved replay evidence, but
cannot become engineered modeling rows. A capture with no open decision is explicitly refused.
Engineered weather rows use actual saved shadow decision times, rather than the earlier
public-capture completion time. Each row gets only its own saved book. A missing/deferred
book never borrows earlier or later depth from another cycle. Book age and exchange clocks
remain subject to execution refusal. Original shadow feature hashes, versions and clocks
remain in row lineage; R2 engineered features keep their own identity. The downloadable
projection separately retains original shadow samples, probabilities, frozen specs, saved
decisions, versioned fee evidence and subsequent labels. Forward prediction partitions
are preserved and cannot be promoted to validation.

Later finalized binary labels require matching original contract terms, status, result,
payout, settlement time and original receipt availability. An outcome partition may include
unrelated contracts; these cannot become labels for the selected captures. Binary results
never supply integer daily highs. Protected events have no labels in experiment inputs
and cannot appear in the downloadable shadow sample/decision/prediction projection. Raw
original receipts remain intact in the local immutable snapshot. Existing risk caps,
independent-event minimums, source-matched scalar label gates and certified fee requirements
remain enforced. No real orders, execution activation or profitability claim is supported.

`test_weather_cohorts.py` adds a CONTROLLED 130-capture cohort over two partitions and
200 city/day events on 100 dates. Default model gates exercise deterministic fitting,
Platt calibration and validation on the frozen calendar, excluding 20 holdout events.
Independent model outputs reproduce prediction bytes. Interrupted-batch retry, inherited
protection, absence of labels, raw-input budget, and offline restore are tested. The
listener regression uses ordinary local-template research and the existing R4 engine;
controlled probabilities are available while missing sized depth/fees refuse trading
backtests. This fixture is simulated software evidence, not authentic historical data.

`test_shadow_history.py` exercises 130 actual collector/store cycles with explicitly
CONTROLLED source payloads and simulated clocks, restart after cycle 64, partitions of
128 and 2, later labels, source bindings, deterministic decision comparison and offline
restore. `test_shadow_history_listener.py` exercises the real localhost listener and
ordinary research worker, checksummed downloads and restore. These controlled tests are
software evidence; the separate authentic retained cycles still lack scalar highs and
empirical validation.

The reproducible browser harness is `frontend/browser/shadow-history.spec.cjs`. It has
separate controlled 130-cycle, authentic-insufficiency and sufficient-data cohort procedures,
real form selection,
research, inspection, three downloads, offline restore and byte-identical reopened
downloads. Run in a permitted environment with fresh directories:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/shadow-history-review/NEW/browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/shadow-history-browser-NEW" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  frontend/browser/node_modules/.bin/playwright test \
  -c frontend/browser/playwright.config.cjs \
  --grep 'sustained shadow history|research cohort' --max-failures=1
```

Repository-managed Chromium installation and all three real-page procedures now pass
through the normal supported permission mechanism, with real localhost listeners,
screenshots, matching downloads, zero page errors and offline restore. See the
[current evidence bundle](../data/research-cohort-review/20261030/README.md). The prior
sandbox launch denial at `crashpad/util/linux/socket.cc:45` (`setsockopt: Operation not
permitted`, SIGTRAP) remains in the [historical bundle](../data/shadow-history-review/20261030/README.md);
the same denied launch was not repeated. No sandbox policy or launch flags were changed.
There is no outstanding execution step for these three procedures; independent supervisor
review remains required. V1 stays incomplete; external-provider checking, authentic
empirical validation, certified fees, clean release installation and new-family selection
are deferred.
