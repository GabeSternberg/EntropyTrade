# Real workbench browser acceptance

For the local-operation/recovery milestone, use the [one-command fresh-install driver](../../docs/local-recovery.md)
or select `--grep 'local operation and recovery'` with new evidence/workspace paths.
`recovery.spec.cjs` performs actual research/results, paused and active shadow lifecycle,
offline snapshot/restore, restored downloads, fresh cycles and cancellation/restart.
The [current executed attempt](../../data/local-operation-review/README.md) installs managed
Chromium but fails launch at Crashpad `setsockopt: Operation not permitted (1)` before
page/listener interaction. Its trace/reports are retained; no new screenshot or current
browser pass is claimed. Do not repeat that denied launch in the same environment. The
default driver must execute in a permitted environment for supervisor acceptance;
`--prepare-only` explicitly leaves browser and full suite unverified.

For the continuous shadow milestone use `--grep 'continuous shadow'` with new absolute
evidence/workspace directories as in [the shadow guide](../../docs/shadow-tracking.md).
`shadow.spec.cjs` uses actual form interaction, real server/subprocesses, source capture,
pause/restart/resume and checksummed downloads. It distinguishes actual acquisition failure
from ingestion, uses no controlled responses or clock overrides, and retains screenshots
only when page interaction executes. The current strengthened procedure requires structured
source and execution audits and refuses an internal collection exception as a passing cycle.
The [October 29 model integration run](../../data/shadow-review/20261029-model-integration/README.md)
passed on a real localhost listener with two completed authentic source/book/fee cycles,
three screenshots and three downloads. The first attempt exposed a decimal-strike parser
failure; it is retained separately and was corrected before the fresh successful run.
Earlier Chromium/socket denials remain failed historical attempts. Do not repeat a denied
launch in the same environment or substitute mocked HTTP tests for browser interaction.

To exercise **real retained receipts**, set `ENTROPYTRADE_BROWSER_RETAINED` to an absolute
verified Bitcoin history snapshot under this repository's `data/`, and select
`--grep 'REAL retained receipts'`. Use new absolute workspace/evidence directories as
below. The setup helper imports the verified source copies and prior outcome snapshot
without changing receipt clocks; imported jobs explicitly say receipt replay. Subsequent
form submission, discovery, worker, all tabs, downloads and restart use the actual app.
This test asserts honest insufficiency and never claims fitting/evaluation from sparse
data. It uses no controlled responses or response interception. The new
[executed real case](../../data/bitcoin-history-review/20261029T001500Z/README.md) retains
four screenshots, four downloads, a trace and the stopped workspace. Its public result
reconciliation and one-shot source-access probe are separate executed evidence.

The new Bitcoin retained-history procedure can be selected with
`--grep 'Bitcoin retained history'`. Use a new absolute evidence directory and workspace
as below. It runs `bitcoin-history.spec.cjs` against a real localhost server/worker,
checks empty-history and **controlled populated-history** insufficiency across all tabs,
downloads both artifacts, restarts the server and compares downloads. The populated case
uses the test-only `tests.integration.bitcoin_history_fixture` setup: three retained
captures, a prior snapshot with three finalized outcome responses and 55 unrelated jobs
that push the inputs outside the UI's history window. No response interception or worker
replacement is used after setup. Controlled setup is software evidence only; the adapter's
existing `data_kind=real` field identifies its receipt-processing path and does not make
these fixture responses empirical data. Receipts, filenames and setup jobs label them
CONTROLLED. The empty case uses the exact requested workspace; the populated case uses
that path with `-controlled` appended. Both paths must be new.

It needs an actual permitted browser/listener; a launch denial remains failed acceptance.
This procedure does not establish successful public ingestion or historical model accuracy.
The [October 28 attempt](../../data/bitcoin-history-review/20261028T232200Z/README.md)
retains its Chromium socket-permission failure before page interaction. The original
four-workflow harness below can be selected with `--grep 'four documented'`.

The [acceptance continuation](../../data/bitcoin-history-review/20261028T235347Z/README.md)
retains actual passing page-interaction checks for both history cases. Its separate Python
listener regression also adds a repeated capture between restarts, checks unchanged earliest
decisions and frozen partitions, verifies copied artifact hashes and compares both completed
reviews after another restart. Run that regression in an environment permitting loopback
sockets and asyncio socketpair wakeups:

```bash
.venv/bin/pytest backend/tests/integration/test_bitcoin_history_listener.py -vv
```

For a new durable evidence copy, set `ENTROPYTRADE_HISTORY_EVIDENCE` to a new absolute
directory beneath the repository's `data/bitcoin-history-review/` before running it.
The test copies the quiescent workspace, downloads and a CONTROLLED receipt there.
Socket denial fails the regression; it is never skipped or converted into mock HTTP coverage.

This harness automates all four procedures in `docs/workbench.md` against the actual
loopback HTTP server, durable queue and isolated research workers. It clicks the form,
tabs, details, downloads, cancellation and saved history. It stops/restarts its own server
and compares every completed run's browser downloads before and after restart.
It does not use Computer Use, personal Chrome, a saved browser profile, CDP, response
stubs, direct job submissions or replacement data. Application and safety code is unchanged.
This four-workflow procedure is separate from the explicitly controlled history setup above.

From the repository root, with locked Python dependencies already installed:

```bash
uv sync --locked
npm ci --prefix frontend/browser --ignore-scripts --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium

stamp=$(date -u +%Y%m%dT%H%M%SZ)
env -i PATH="$PATH" TZ=UTC \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/workbench-review/$stamp/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/workbench-browser-review-$stamp" \
  ENTROPYTRADE_BROWSER_DENY_PUBLIC=1 \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs
```

The pinned npm lockfile and Playwright-managed Chromium are independent of Python's
application dependency lock. Chromium is installed only under the ignored `.browsers/`
directory. The configuration explicitly launches that executable in headless mode with
a fresh browser context. Both the evidence receipt and Playwright results record outcomes;
JSON/JUnit reports, traces, screenshots, DOM text, real run files and browser downloads
remain in the selected evidence directory. Existing receipts/workspaces are refused.
The server uses a credential-free environment allowlist. Port 43128 must be free; override
it with `ENTROPYTRADE_BROWSER_PORT`. Override the Python interpreter with an absolute
`ENTROPYTRADE_BROWSER_PYTHON` if the environment is elsewhere.

The optional `ENTROPYTRADE_BROWSER_DENY_PUBLIC=1` test requires macOS `/usr/bin/sandbox-exec`.
After the normal weather/Bitcoin captures, the harness restarts the real backend with OS
outbound connections denied. A new Bitcoin request must produce timestamped connection
failures, zero fabricated HTTP receipts/data and visible incomplete summaries on all three
tabs and its text download. The fault is explicitly labeled and never counts as successful
ingestion. The harness then restores normal backend execution before lifecycle testing.
On another OS, omit this variable; failure-path coverage is recorded as unexecuted unless
an actual fresh capture fails. A denied installer, browser launch or listener remains a
failure, with its exact error in logs/results; do not skip it or substitute HTTP-only tests.

Each workflow has a recorded outcome. Acquisition completeness is checked separately from
worker completion; partial public capture leaves workflow 3 failed while subsequent
lifecycle checks still execute. Calibration timestamps may be null for uncalibrated model
outputs; present calibration clocks and all fit clocks must precede the decision. All
exposed predictions must be validation records, and protected final holdout must remain
excluded. Synthetic results prove software behavior only. No V1 or trading approval follows
from this test. Run the unchanged full Python/frontend gates separately before review.

No commits, ref changes, merging or pushing are performed by this harness.

## Provider website acceptance (October 29)

`provider.spec.cjs` runs actual Chromium page interactions through the private website and
SQLite/subprocess lifecycle. A test-only listener/worker controls only OpenAI HTTP replies;
production has no endpoint or switch to select that fixture. It verifies fresh explicit
consent, three typed hypotheses, deterministic insufficient-data experiments, all tabs,
checksummed report/JSON downloads, redacted provider outage, active cancellation and restart
with identical reopened bytes. A second unmodified server with no credentials verifies
`ResearchCredentialError` and zero requests. This is **controlled provider software proof**,
not an external service session or real model/returns validation.

The default `tools/local_acceptance.py` selects this procedure, `recovery.spec.cjs`,
authentic weather history, **both `paper.spec.cjs` procedures and `alerts.spec.cjs`** from a
fresh locked Python/npm installation before the complete pytest suite. It retains separate
discovery reports and checks localhost/asyncio socket capabilities before browser launch.
It validates JSON reports against six fixed file/title identities, actual successful result
records and aggregate counts. A zero process exit cannot pass missing, skipped, failed or
empty results. Full discovery always runs independently of `--browser-grep`; narrowed
selections have separate discovery reports and can only produce explicitly partial
receipts with missing procedures listed and `acceptance_complete=false`.
Denied capabilities block browser/full-suite execution with a nonzero exit and explicit
unexecuted checks. Browser execution stops after its first failure. `--prepare-only` installs
and discovers tests without retrying a known environment denial; it cannot pass acceptance.
Use a short
TMPDIR for Chromium: Unix socket addresses are limited to 108 bytes on Linux. The driver
allocates and cleans a short `/tmp/entropytrade-*` directory; durable evidence stays in
the requested repository output. No launch flag, event loop or test assertion is relaxed.
See [current evidence](../../data/provider-review/20261029/README.md) for executed results,
retained failed attempts and any remaining external/human acceptance steps.


`shadow-history.spec.cjs` has CONTROLLED 130-cycle, authentic-insufficiency and CONTROLLED
sufficient-data research-cohort procedures. It selects single or multiple history/outcome
partitions through the page, runs ordinary research, inspects all tabs, downloads
review/report/shadow inputs and compares downloads after offline restore. Select all three
with `--grep 'sustained shadow history|research cohort'`. See
[the guide](../../docs/shadow-history.md) and [executed evidence](../../data/research-cohort-review/20261030/README.md).
All three now execute using managed Chromium and real localhost listeners through normal
supported approval. The prior sandbox-denied launch remains historical evidence; its
policy/launch flags were not changed. Controlled fits never establish empirical results;
authentic fitting remains insufficient. Run with fresh evidence/workspace paths and retain
screenshots/download hashes; HTTP/DOM checks do not replace browser acceptance.


For point-in-time fee evidence select `--grep 'point-in-time fees'` with fresh absolute
workspace/evidence paths. `fees.spec.cjs` separates CONTROLLED synthetic eligible-intention
fixtures from authentic original-receipt refusal. Both inspect actual pages, download full
versions and exact original bytes, inspect frozen shadow selections, restart the real server
and compare downloads. The authentic flow submits ordinary research and downloads frozen
experiment fees plus its insufficient-data review. See [the guide](../../docs/fee-evidence.md)
and [executed evidence](../../data/fee-evidence-review/20261030/README.md). These are actual
managed-Chromium checks; controlled success does not establish empirical data or returns.
