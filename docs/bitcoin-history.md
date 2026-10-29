# Retained Bitcoin research history

The workbench now connects retained real Bitcoin receipts → frozen features → later
official binary outcomes → typed hypotheses → binary probability models → the existing
protected experiment engine. This is an intermediate second-family capability. **V1 and
empirical second-family acceptance remain incomplete.** Forward weather and Bitcoin
capture, the weather CLI, and the existing synthetic demonstration remain available.

The [acceptance continuation](../data/bitcoin-history-review/20261028T235347Z/README.md)
adds a populated-history regression through actual Jobs discovery, loopback HTTP and the
unchanged subprocess worker. Its controlled wire setup is **software evidence only**.
It verifies retained inputs beyond the UI history window, original finalized-receipt reuse,
fixed calendar boundaries, repeated-capture deduplication, honest insufficiency and
downloads/restart persistence. Playwright exercises both empty and controlled populated
history through the actual page; see the [harness guide](../frontend/browser/README.md).
This acceptance adds no real historical observations or empirical performance claims.

In the website, choose **Bitcoin → Fetch public sources now** on separate dates. A completed
capture retains the actual market rules and Coinbase covariate. Then choose **Retained
Bitcoin history + official outcomes**. The worker verifies all completed Bitcoin inputs in
that workspace, freezes an immutable history snapshot, reads up to ten later contract
results, formulates local typed proposals and runs the shared experiments. History summaries,
failures and limitations appear on every result tab and in the downloaded report. No
provider or exchange credentials are read. Local templates interpret only their documented
signal/comparison grammar; this does not add LLM reasoning to the website.

The same workflow is available from the CLI, using existing public capture directories:

```bash
uv run entropytrade bitcoin-history \
  --capture data/workbench-review/20261025T163400Z/public-bitcoin/public \
  --capture data/workbench-review/20261026T203717Z/browser-attempt-2/runs/public-bitcoin/public \
  --output data/cache/bitcoin-history-first \
  --prompt 'Test scaled_moneyness > 0'
```

Use a new output directory each time. Pass `--no-fetch` when explicitly replaying
receipts without any new network access.
That mode records `fetch_enabled=false`, zero new reads and any deferred targets; it never
claims that ingestion succeeded. On later runs, supply the same capture partition plus
new captures and `--previous data/cache/bitcoin-history-first/history`. Prior snapshots
preserve finalized outcome receipts and their original availability clocks. The website
finds these completed snapshots automatically. Final targets are reused; pending targets
rotate by last attempt so one unresolved contract cannot starve the rest. Interrupted or
cancelled jobs never become trusted inputs. Partial files remain on disk for inspection.
No background scheduler, paper/shadow activation or order submission is added.

## Information and settlement boundaries

The loader verifies every input checksum and original raw-to-normalized market/spot
identity. Coinbase's provider trade clock and our receipt clock must both precede the
decision and be fresh within five minutes. Rules must actually have been received while
the contract was active and before close. Fresh responses cannot backfill earlier
decisions. Repeated polling freezes the earliest retained decision for each event; related
strikes share that event rather than becoming independent samples.

The first supported binary-target grammar is deliberately narrow: the complete actual
primary rule must specify the simple average of the sixty seconds of CF Benchmarks BRTI,
strictly above an exact strike, with an explicit Eastern date/hour. The complete secondary
text must match the retained sixty-price-average definition. Strike, timezone/DST and
close must agree. Ambiguous, negated, changed, exceptional, below/between or other rule
forms are excluded. A source-name mention cannot pass this parser.

Only a matching **finalized**, nonprovisional YES/NO result with a matching binary payout,
settlement timestamp, event, strike and recognized terms becomes a label. Availability is
the later HTTP receipt, even when settlement happened earlier. Coinbase prices never
become settlement prices; no rounding or scalar BRTI label is reconstructed. This binary
result mapping does **not** certify all exceptional resolution paths: `rules_known=false`
continues to block execution. Historical depth and certified fees are also absent.

Outcome reads use the pinned SDK boundary, restricted to GETs of the exact captured
tickers. A live 404 permits an exact archived-market fallback; other failures are retained
without fabricating a response. Kalshi documents the separate
[historical tier](https://docs.kalshi.com/getting_started/historical_data) and
[exact archived-market endpoint](https://docs.kalshi.com/api-reference/historical/get-historical-market).
There are no account/order routes, auth headers, arbitrary URLs or redirect following.
Reads are capped at 20 requests, two MB per body, 12 MB per batch and 90 seconds.

## Fixed experiments

Before fitting, the first history snapshot fixes calendar boundaries anchored to its
earliest captured decision date: the first 60 days are fitting history, the following
30 days are validation, and all later target dates are protected final holdout. Subsequent
snapshots inherit those exact dates. Conflicting partitions or earlier imported captures
are refused. Adding observations cannot roll holdout dates into fitting or evaluation.
This conservative initial policy needs longitudinal collection; importing today's
historical outcome response does not meet it. The dates are retained in the manifest and
review, and there is no website control to move them.

Two fixed, uncalibrated binary models compare an event-weighted training YES frequency
with regularized logistic regression on `100 * log(spot / strike) / sqrt(hours_to_close)`.
These are contract-result models, not weather models or fitted scalar-price distributions.
They require at least 40 fitting events across 20 dates, labels received by the fixed fit
cutoff, and at least 20 validation events across ten dates. Each event has total fitting
weight one. A nonpositive moneyness slope blocks the logistic candidate. Predictions do
not extrapolate beyond training moneyness/horizon ranges; supported capture horizons are
15 minutes through 48 hours. There is no validation-based tuning or calibration fit.

Versioned numeric parameters, training identities, cutoffs, predictions and refusals are
retained as JSON, without executable model deserialization. Validation probabilities use
the existing protected browser projection. The shared engine calculates event-weighted
forecast scores and the training-only baseline comparison when evidence exists. Missing
rules, depth and fees keep trading scenarios/P&L closed. The existing synthetic weather
execution demonstration remains separate.

Inputs are bounded to 128 captures and 128 previous snapshots, 128 MB of copied source
inputs and bounded retained outcome receipts. Each review owns its source copies, outcome
receipts and manifest; old artifacts are not rewritten. Repeated snapshots consume disk.
For a larger archive, select an explicit CLI partition; do not silently truncate history
or change the protected dates. The UI recent-run window does not limit input discovery.

## Acceptance and remaining evidence

`backend/tests/unit/test_bitcoin_history.py` checks raw identity, exact rules, archived
fallback, finalized-only receipt-time labels, immutable reload/restart, destination/auth
limits, late-label exclusion, deterministic models, untouched later labels and the actual
shared research/experiment/review path. Fitting/scoring checks use **explicit synthetic
contract samples**. These cannot establish real-data accuracy, trading returns or V1.

The real-data command and current validation receipts are in
[the October 28 bundle](../data/bitcoin-history-review/20261028T232200Z/README.md).
Outbound DNS and Chromium socket permissions are blocked in this environment. The
Playwright-managed Chromium installation succeeded, but launch failed with
`setsockopt: Operation not permitted` and `SIGTRAP`, before page interaction. No new
browser workflow or screenshot is claimed. Prior website browser receipts remain records
of their original code state.

The executable browser procedure is
[`bitcoin-history.spec.cjs`](../frontend/browser/bitcoin-history.spec.cjs). In a permitted
environment run it with a new workspace/evidence directory and `--grep 'Bitcoin retained
history'` using the existing Playwright config. It opens the real localhost website,
submits an empty-history request, checks all tabs and downloads, restarts the actual
server, and compares saved downloads. Successful real outcome ingestion and sufficient
longitudinal validation remain additional requirements; an empty-history browser pass
does not satisfy them. Before approving this milestone, the supervisor must independently
run the complete gates and browser procedure. No Git operation was performed here.
