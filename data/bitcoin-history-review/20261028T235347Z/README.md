# Bitcoin history acceptance continuation — October 28–29, 2026

**Requested software acceptance passes. V1 and empirical second-family acceptance remain
incomplete.** Controlled responses in this bundle verify software behavior only. They do
not establish successful external ingestion, fitted real-data probabilities, accuracy,
profitability or returns. No next major milestone was started.

Work began clean on `supervisor/20261028-191140`, HEAD
`446c910` (full identity in [source.json](source.json)). Actual local `main` was
`9ba9b3d`, superseding the older main pointer described in STATUS. No remote freshness
is claimed. There were no Git mutations, credential reads, supervisor control-file changes,
production execution changes or risk-limit changes. Application source and previous tests
are unchanged. Added code is acceptance setup/tests plus the extended Playwright harness.
All changes remain for the supervisor to review and commit.

| Acceptance check | Executed result | Evidence |
| --- | --- | --- |
| Populated history via actual HTTP and worker | Passed; two submitted history jobs, two listener restarts, three then four discovered captures | [log](listener.log), [JUnit](listener.xml), [receipt and frozen workspace](listener/README.md) |
| Ruff lint and format | Passed; 482 files formatted | [complete gate log](full-check.log) |
| Strict mypy | Passed; 482 source/test files | [complete gate log](full-check.log) |
| Complete pytest suite | **752 passed in 269.88s**, zero failures/errors/skips | [log](full-check.log), [JUnit](pytest.xml) |
| Frontend assertions | **12 passed**, zero failures/skips, direct Node execution | [direct TAP output](frontend-direct.log) |
| Managed Chromium installation | Supported install command exited 0 using the existing repo-local Playwright browser cache | [log](chromium-install.log) |
| Actual browser acceptance | **2 passed in 21.1s**; empty and CONTROLLED populated history, form/tabs/downloads/restart | [log](browser.log), [browser evidence guide](browser/README.md), [JSON](browser/playwright-results.json), [JUnit](browser/playwright-results.xml) |
| Independent frozen-artifact check | Passed; SQLite quick-check/results, raw receipt reuse, model split/refusals, artifact hashes, eight screenshots/eight downloads | [result](validation.json), [executable verifier](verify_evidence.py) |

The complete gate ran the same Ruff, format, strict mypy and full pytest checks as
`make check`, using the existing locked `.venv` executables directly. No clean installation
or actual `make check` invocation is claimed. Pytest's 90-second faulthandler setting adds
diagnostics; it does not skip, relax or change any assertions. The 900-second external
deadline was not reached. [source.json](source.json) fingerprints 499 source/configuration
files; `SHA256SUMS` binds the durable bundle. Transient SQLite WAL/SHM and process locks
are excluded from the bundle index. Existing acceptance receipts remain untouched.

## What the populated regression establishes

The test-only [fixture helper](../../../backend/tests/integration/bitcoin_history_fixture.py)
uses controlled HTTP transports and simulated clocks only while constructing the initial
workspace. It records three public captures using the normal adapter and constructs a
prior history snapshot with three controlled finalized responses. Their title/setup-job
labels explicitly say CONTROLLED SOFTWARE EVIDENCE. Fifty-five unrelated completed jobs
push those inputs beyond the website's 50-row history window. A failed Bitcoin job has
no capture and must be excluded from discovery.

The actual [listener regression](../../../backend/tests/integration/test_bitcoin_history_listener.py)
then submits a Bitcoin history request over loopback HTTP. The unmodified Runner starts
the normal credential-free subprocess worker; no job result, discovery method, worker,
research engine or listener response is replaced. Assertions verify:

- Jobs finds the three completed captures and prior history beyond the UI history window.
- The worker reuses three finalized outcome receipts with **zero requested/deferred reads**
  and zero reconciliation failures. Independent checks compare original receipt bytes.
- Anchor `2026-07-01`, fit cutoff `2026-08-30` and holdout start `2026-09-29` persist.
  Exactly one event belongs to each partition; the last remains protected and unevaluated.
- Original outcome availability stays `2026-10-01T12:00:00+00:00`. The late fit label is
  not backdated to settlement. Model artifacts report zero fit events/date blocks, no
  fitted parameters and no prediction records.
- Both candidates honestly return `INSUFFICIENT_DATA`, with explicit receipt-time
  minimum-evidence refusals, no forecast metrics, trading scenarios or returns.
- After shutdown, one later capture of the original July event is added. The second real
  worker discovers four captures but retains three events and their original decisions.
  Prior outcome receipts deduplicate and the frozen partition does not move.
- Both completed jobs, events, reviews and text downloads survive another restart.
  Persisted/downloaded JSON agrees, report bytes agree and all referenced artifact hashes
  and sizes validate.

The browser cases separately use Playwright-managed Chromium 141.0.7390.37, fresh browser
contexts and actual backend server processes. The populated setup is controlled as above;
after setup all page interactions and worker execution are real. Both cases submit through
the form, inspect Review/Probabilities/Evidence & lineage, download JSON/text, stop/restart
the server and reopen saved history. Four screenshots and four downloads per case are
retained with traces and quiescent workspace copies. Page errors are empty. The older
four-workflow public-acquisition browser procedure was not rerun in this continuation.

**Fixture-origin limitation:** `data_kind=real` in fixture-derived artifacts and the UI's
existing REAL EVIDENCE banner describe the receipt-processing path. The controlled
responses are software evidence, never real market history. This label applies to every
populated screenshot, download, database and run artifact in this bundle; see the
[listener](listener/README.md) and [browser](browser/README.md) labels.

## Recorded stall diagnosis

The workspace sandbox denies ordinary socket creation and writes to an existing Unix
socketpair. The [bounded diagnostic](diagnose_async.py) executes actual socketpair and
asyncio operations without monkeypatching: [sandbox output](async-sandbox.log) shows
`PermissionError: [Errno 1] Operation not permitted` in asyncio `_write_to_self`, followed
by a one-second timeout for 50ms of executor work. Without the thread-completion wakeup,
the event loop can remain asleep in `select`, matching the previous collector/AnyIO dumps.

The same script in the environment permitted through the approval mechanism reports a
successful socketpair send/read and **0.0519 seconds** for that executor work:
[permitted output](async-permitted.log). The unchanged collector regression reproduces
the sandbox stall, with a 15-second dump and 35-second external timeout (exit 124):
[sandbox log](collector-sandbox.log). With socket operations permitted, all seven
collector tests pass in 3.09s: [permitted log](collector-permitted.log). The complete suite,
real listeners and browser checks then pass in that permitted environment. No polling
workaround, timeout increase inside the application, test suppression or policy weakening
was introduced. The sandbox was not bypassed.

The first new listener attempt correctly failed an erroneous harness assumption that the
API supplied `Content-Disposition`: [original failure](listener-attempt-1.log),
[JUnit](listener-attempt-1.xml). The page uses HTML download attributes. The harness now
checks actual API content types and bytes; Playwright separately executes actual downloads.
An initial independent verifier also omitted the application's `sha256:` digest prefix;
the raw bytes matched. Correcting that comparison produced the passing independent check.
No application defect or safety exception was needed for either correction. The first
`node --test` invocation reported only an aggregate one-file result in this environment;
the direct TAP execution above records all twelve individual assertion results.

## Reproduction and review boundary

Use an environment permitting loopback listeners, managed Chromium and asyncio socketpair
wakeups. The permission-denied sandbox is not a valid execution environment for these
checks; a denial is a failure, never a skip or a mocked replacement pass.

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
.venv/bin/pytest
node frontend/tests/acquisition.test.cjs
.venv/bin/python data/bitcoin-history-review/20261028T235347Z/verify_evidence.py
```

The [browser guide](../../../frontend/browser/README.md) provides installation and
execution commands; select `--grep 'Bitcoin retained history'`, new absolute evidence and
workspace paths, and omit the unrelated macOS public-denial option. It also documents
optional durable listener evidence collection. These checks ran on the working checkout;
the supervisor still owns independent clean-checkout review and all Git operations.

There is no outstanding page-interaction step for the two scoped history procedures.
Successful fresh public reconciliation, sufficient independently retained source/label
dates received before the frozen fit cutoff, empirical second-family evaluation,
continuous paper/shadow tracking, clean-install release evidence and the final V1
acceptance matrix remain separate unmet gates. No real-money order or live execution
activation was attempted. Stop for review before the next major milestone.
