# Operator readiness evidence — October 31, 2026

Implementation on the existing `supervisor/20261031-011453` checkout from `df304f9`.
No Git mutations, supervisor-control edits, credentials, real orders, submission activation,
risk-limit changes or new-family selection. **V1 and this milestone's environment-dependent
acceptance gates remain incomplete.**

## Implemented behavior

The existing collector/store/runner and private website now expose durable incidents for
stale collection, three repeated failed/incomplete collections and unresolved contracts
one hour after their frozen close. Detection/acknowledgement/recovery clocks are operational
clocks. Incident IDs, evidence, acknowledgement, recovery and recurrence survive restart
and offline workspace restore. Acknowledgement is monitor scoped, idempotent and CSRF
protected. Pausing/resuming cannot erase incidents or certify missing models/fees.
The runner checks even while a bounded worker is busy. See [operation](../../../docs/operator-alerts.md).

## Executed checks

| Check | Actual result and retained evidence |
| --- | --- |
| Backend Ruff | Pass: `ruff check backend`; [log](ruff.log). |
| Backend format | Pass: `ruff format --check backend`, 534 files; [log](ruff-format.log). |
| Strict mypy | Pass: 534 source/test files; [log](mypy.log). |
| Named frontend checks | Pass: all 22, including acknowledged/open/resolved presentation and literal hostile source text; [log](frontend.log). Direct `node frontend/tests/acquisition.test.cjs` executes named checks; the separate Node `--test` wrapper reports only its file aggregate. |
| Final focused pytest | Pass: **246 tests in 24.68s**, alerts, risk/collector controls, paper accounting, partial worker/restart behavior and workspace recovery; [log](targeted-verified.log), [JUnit](targeted-verified.xml). |
| Current alert tests | Pass: all **11 tests in 6.94s**, including idle/busy detection, simultaneous acknowledgement retries, recurrence, partial/unknown metadata, migration, scope/CSRF, authentic blocked inspection and corrupt lifecycle refusal; [log](alerts-current.log), [JUnit](alerts-current.xml). Included in the focused total, not additional independent cases. |
| Earlier broader focused run | Pass: 256 tests in 138.64s, including the **130-cycle collector/history/restart/restore** procedure and 13 other history cases; [log](targeted-final.log), [JUnit](targeted-final.xml). It predates the final background busy-worker checks and final metadata/restore review corrections; it is not a final complete-suite pass. |
| Offline paper acceptance | Both controlled and authentic account exports reproduce and restore identically. [Controlled receipt](offline/controlled-receipt.json), [authentic receipt](offline/authentic-receipt.json), [controlled export](offline/controlled-shadow.json), [authentic export](offline/authentic-shadow.json). These are offline checks, not listener/download/browser checks. |
| Offline alert lifecycle | Controlled seed → acknowledgement → reopen → recovery → recurrence → snapshot/restore passes with identical restored monitor export; [receipt](offline/alerts-lifecycle.json). The executable fixture refuses a busy workspace lease. |
| Original receipt integrity | All **68 original files unchanged**, [fingerprint](offline/original-source-fingerprint.json). [Safety receipt](safety-receipt.json) also retains Bitcoin boundary code/manifests; Git diff checks show no changes to those original paths, risk code, exchange gateway, submission gate or configuration. |
| Browser harness discovery | All three operator/paper procedures discovered without launching a browser; [log](harness-discovery.log). This is executable harness evidence only. |

The controlled account contains two simulated fills and one controlled settlement. The
authentic original-receipt account retains $1,000, zero fills, zero fees and zero settlements;
decisions explicitly refuse missing point-in-time model/fee evidence. Controlled signals,
outcomes and accounting are synthetic software proof, never authentic acquisition,
statistical accuracy, empirical returns or profitability.

## Complete-suite limitation

The unfiltered `pytest` invocation collected 1,151 cases at that intermediate source state,
passed the two architecture cases and stalled in the existing collector reconnect test.
It was interrupted; [log](pytest.log) is not a pass. A bounded isolated diagnostic also
remains in the asyncio event loop and exceeds its 90-second deadline, then its five-second
termination allowance; [trace](collector-diagnostic.log). This does not identify a new
application assertion failure and is not counted as passing the collector test.

[The bounded driver](run_bounded_pytest.py) attempts **every test file** with four independent
processes, a 90-second per-file deadline and retained logs/JUnit. Deadline expiry is always
incomplete/failing evidence; no file is excluded and test assertions/markers are unchanged.
The final [machine-readable summary](per-file-summary.json) records **228 files attempted
in 431.34s: 211 passed, six failed and eleven exceeded their deadlines**. The six failed
files contain eight listener cases; every failure is `PermissionError: [Errno 1] Operation
not permitted`. No other completed file has an assertion failure. All 14 shadow-history
cases, including the 130-cycle case, also pass in this all-file run. Each remaining deadline,
file name, exit status and available case count is preserved in the summary and per-file
logs, with no inferred passing cases. A complete unfiltered pytest pass remains required
in a permitted environment.

## Browser/listener limitation and remaining human acceptance

Supported installation with `PLAYWRIGHT_BROWSERS_PATH` set to the repo-local managed cache
succeeds; [installer log](chromium-install.log). An initial default-cache attempt could not
create `/home/gabriel/.cache/ms-playwright`; no outside-cache installation was used.

The **one** actual managed-Chromium launch fails before page interaction:
`crashpad/util/linux/socket.cc:45`, `setsockopt: Operation not permitted (1)`, SIGTRAP.
The first paper procedure fails at browser setup and the second is not run. The new alerts
procedure was added/discovered afterward and has not been launched here. See
[attempt log](browser-attempt.log), [Playwright JSON](browser/playwright-results.json),
[JUnit](browser/playwright-results.xml) and the retained trace under `browser/playwright-artifacts/`.
No browser screenshots, successful page interaction or real download acceptance are claimed.

A direct localhost socket-creation probe returns `PermissionError: [Errno 1] Operation not
permitted`. The complete all-file run separately records actual listener failures rather
than substituting memory HTTP checks. [Environment receipt](environment-blockers.json)
distinguishes these blockers. The denied browser launch is not retried, policy/launch flags
are not altered and no permission elevation is requested.

In a permitted environment, run the command in [the guide](../../../docs/operator-alerts.md)
using **fresh paths**. It selects both unchanged paper procedures and the new operator-alert
procedure through real localhost listeners. Retain screenshots, page error counts, download
hashes, actual listener restart and offline-restore comparisons. Run `make check` and the
22 named frontend checks as well. These acceptance steps remain outstanding; installation,
test discovery, HTTP doubles and offline replay do not satisfy them.

No fresh clean-install, external provider session, authentic model/fee certification,
empirical two-family validation or independent V1 release pass is claimed. Preserve forward
receipt clocks and frozen Bitcoin boundaries. Return for independent supervisor review;
do not start another major phase or silently promote these blocked gates.

[Implementation fingerprints](implementation-hashes.json) retain 560 final application,
test, frontend, lock and configuration hashes for independent review.
