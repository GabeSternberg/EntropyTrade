# Research cohorts over retained partitions — October 30, 2026

Implemented in place on `supervisor/20261030-202711`, starting at `69e2740`.
The supervisor owns all Git operations and independent acceptance. **V1 remains incomplete.**
No credentials, exchange orders, live activation, new family or risk-limit changes were used.

The private website freezes up to eight explicitly selected history partitions plus
optional later-outcome partitions as one research cohort. History batches remain limited
to 128 inputs; the aggregate retains the 256 MB raw-input budget. Completed immutable
batches persist across interrupted assembly. Final features are rebuilt jointly from frozen
batch receipts through the existing snapshot/R2/model/R4 pipeline. Original clocks,
raw provenance, independent-event counting and inherited calendar/model/holdout protections
persist. Partial/unknown selections and malformed API payloads refuse rather than truncate.

## Executed browser acceptance

All three procedures pass actual repository-managed Chromium page interaction through
real localhost listeners and ordinary isolated workers. The supported Chromium installer
also succeeds. No personal Chrome, mocks of the browser/listener, sandbox policy changes
or alternate browser launch flags are used. The two earlier outstanding procedures are
now executed; their original sandbox-denied attempt stays in the historical evidence bundle.

- [CONTROLLED 130-cycle receipt](browser-final/controlled/weather-browser-receipt.json):
  history/outcome partition selection, deterministic insufficiency, all result tabs,
  three downloads, offline restore and identical reopened downloads.
- [Authentic receipt replay](browser-final/authentic/weather-browser-receipt.json):
  original receipts, four independent events on two dates, no scalar highs/probabilities
  or backtest scenarios; all result tabs/downloads and offline restore.
- [CONTROLLED sufficient-data cohort](browser-final/cohort/weather-browser-receipt.json):
  two history partitions, 130 captures, 200 city/day events on 100 dates, normal research
  and validation probabilities, honest trading-backtest refusal, downloads and restore.

The final run passes all three procedures in approximately three minutes. Its
[Playwright report](browser-final/playwright-results.json),
[JUnit](browser-final/playwright-results.xml), traces, **18 screenshots and 18 downloads**
are retained. [Browser verification](browser-verification.json) independently hashes every
screenshot/download and compares all nine original/reopened download pairs. Zero page
errors occurred. Independent supervisor inspection remains required; no execution step
for these three procedures is outstanding.

Exact offline archives used by restore are retained as `offline.zip.gz` alongside each
browser receipt. Decompression reproduces the original archive bytes, verified against
[archive locations/hashes](offline-archive-locations.json). Uncompressed originals stay
in the repository's ignored cache to avoid introducing a 149 MB file into Git. The earlier
passing development runs remain intact in the cache locations recorded in
[preliminary-browser-locations.json](preliminary-browser-locations.json); they are not
substituted for the final-source run.

## Controlled model and refusal evidence

[Browser model proof](controlled-model-proof.json) and [complete model artifacts](controlled-models/)
retain the ordinary browser worker's uncalibrated model results, as requested by its local
template specs, plus predictions, hashes and data-only forward snapshots. Separately,
[calibration/reproduction proof](controlled-calibration-reproduction.json) and
[calibrated artifacts](controlled-calibrated-models/) execute the existing modeling pipeline
with default Platt calibration in two independent output directories and require identical
results and prediction bytes. All retained model checksums are verified. The fixtures use simulated
normalized receipts and clocks to exercise the real-data adapter. Their `data_kind=real`
adapter tag does **not** make them authentic empirical data or performance evidence.

Default gates admit 96 fitting events and 24 calibration events. Forecast-error/ridge
models exercise Platt calibration; validation covers 60 independent events on 30 dates.
Twenty holdout events are excluded. Boosting remains refused by its existing minimum.
Repeated captures produce more decision rows without increasing event counts. The two
browser research candidates expose 156 validation prediction records in total and both
remain `INSUFFICIENT_DATA`, untested for trading, with zero backtest scenarios because
sized books and certified fees are missing. These numerical outputs verify software only.

`test_weather_cohorts.py` independently fits into two modeling directories and requires
identical model identities/results and prediction bytes. It simulates interruption after
the first completed batch, reuses that batch on retry, verifies selection-order identity,
offline restore and protected-label/bias exclusions. Other cases require missing-label
refusal, inherited early-event protection before fitting, unknown/oversized selections and
the unchanged aggregate byte limit. The actual-listener/ordinary-worker regression tests
strict API refusals and fitted forecast metrics while retaining the execution refusal.

## Authentic evidence and remaining release gaps

[Authentic cohort proof](authentic-cohort-proof.json) separately assembles a cohort from
the original authentic shadow receipts. It still has four independent events on two dates
and zero source-matched scalar highs, with explicit insufficiency. The authentic browser
procedure covers single-partition selection; unit tests additionally cover the cohort
selector on these original receipts. No new acquisition, receipt backdating, empirical
probability accuracy, execution returns or profitability is inferred. All 68 original
authentic source files remain unchanged against [the source freeze](final-source.json).

Final quality results and exact source comparisons are in
[verification.json](verification.json). The complete suite passes **1,083 tests in 563.76s**,
with zero failures/errors/skips. Ruff lint/format covers 522 backend/tool files; strict
mypy passes all 519 source/test files. All 21 named frontend assertions pass. The focused ten-test cohort
gate, complete Python suite, browser procedures and their scopes have separate logs/JUnit.
The existing installation is reused; this is not a fresh clean-install pass.

Sufficient authentic fitting/validation and source-matched outcomes, certified effective
fees, separately authorized external-provider verification, empirical two-family evidence,
a clean release installation and independent final V1 acceptance remain open. Preserve
Bitcoin's original validation boundaries and defer new-family selection pending user
approval. Return this coherent milestone for review before another major phase.
