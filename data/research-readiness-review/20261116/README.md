# Milestone E executed evidence — November 16, 2026

The implementation adds evidence-backed readiness proposals, explicit local owner review,
append-only control/review audits, persistent emergency halt epochs, degradation monitoring,
bounded offline investigations and settlement-only continuation for known held positions.
An approved proposal still has `execution_authorized=false` and `submission_enabled=false`.
It neither allocates funds nor changes the model, broker, paper limits or production gateway.
See [operations and policy](../../../docs/research-readiness.md).

**Final software acceptance passes.** [GitHub CI](https://github.com/GabeSternberg/EntropyTrade/actions/runs/43947708763)
passes all **1,952 tests in 1,121.19 seconds**, plus Ruff/format, strict mypy and Node.
The checked source is `a2ea64cfc71404bc9458f26e55739d7dac27a8fa`; subsequent
completion changes contain documentation and retained evidence only.
The accepted two-case Chromium run completes in **497.10 seconds**, with matching source
fingerprints over all 664 application/acceptance files and no page or console errors.
`acceptance.json` distinguishes retained logs, earlier scoped tool reports,
historical browser passes and intentionally interrupted attempts. Scoped totals overlap;
they must not be added together as a complete-suite result.

The retained final owner/HTTP boundary log passes **23 tests in 8.48 seconds** on Python
3.13.14. These include exact owner identity and passphrase handling, expiry/rotation and
logout/restart, login limits, CSRF and request-body restrictions, SQLite refusal responses,
callback failure handling and shutdown lease retention. Final review corrected two boundary
issues: privileged commits now recheck expiry after credential and fee I/O, and shutdown
refuses to release the writer lease while a monitoring callback is still running. An
independent reviewer accepted that assigned scope after a separate 21-case run and actual
blocked-thread/fair-cursor checks. The subsequent mixed legacy-monitor scheduling correction
passes **4 tests in 74.43 seconds** on Python 3.13.14: a 60-second legacy monitor cannot
indefinitely suppress settlement-only work or background readiness, while approaching
autonomous trained decision points retain their reserved capacity.

Final-source Ruff lint/format, strict mypy (**645 files**) and frontend DOM tests
(**79 tests**) pass; the small `accepted-final-*` logs are retained here, alongside earlier
quality logs. The final source includes selected-proposal UI isolation and legacy collector
compatibility corrections. **28 collector compatibility tests pass in 10.55 seconds**;
an independent four-case review also passed. These use isolated local workspaces and do not
establish access to the physical Windows collector. Prior agents reported 70
storage/drain/recovery cases, 21 evidence
cases, 22 investigation cases and 14 monitoring cases in split 12- and 2-case passing runs.
Raw console logs for those older scoped reports were not located, so the packet labels
them as tool-result reports, rather than manufacturing complete logs or a full-suite pass.
The final readiness-service suite passes **16 tests in 323.00 seconds** on Python 3.13.14;
its actual console log is retained as `service-final.log`.

The earlier controlled Chromium procedure passed in **474.27 seconds** with no page or
console errors. It used actual retained synthetic source wires and committed paper history:
23 cycles supplied 21 independent settled station/day events. The browser exercised owner
approval, rejection and rollback to a new pending proposal; logout, revocation and global
halt; owner release without automatic monitor resume; actual listener restart with expired
RAM sessions; offline snapshot/restore; mobile layout and Demo governance isolation. Exported revoked,
restarted and restored readiness JSON all have SHA-256
`7999a550d3445c14aa2655b7a0fe58e20780dfbcdfce7128d3602ee04b70f6f8`.
The original receipt and one identical export are retained here. This historical run predates
the final monitoring-pane and source-fingerprint checks and is not final-source acceptance.

The production-refusal case in the first final browser candidate also passed with matching
before/after source hashes and no page/console errors. Production refused the same synthetic
evidence, and an unconfigured owner could not release the halt. Its companion controlled case
was interrupted after review found the privileged-expiry gap. The run-level interruption
receipt is retained; that combined run is explicitly **not accepted**. Likewise, the local
full-suite and service attempts were deliberately interrupted for source corrections after
40 and 2 passing cases. Neither is presented as a completed pass.

The second final browser candidate passed the production-refusal case in **34.56 seconds**
and failed the controlled case's 90-second status poll. The trace records the actual review
POST returning HTTP 200 with `status=approved` and submission disabled after **60.65 seconds**.
The browser investigation identified a heavy concurrent read begun before the commit returning
stale proposed status under concurrent full-suite/service load. The acceptance harness is
being corrected to await the POST response before starting a fresh GET. Both cases retained
matching before/after source hashes and clean page/console logs; those facts do not turn
the failed combined run into acceptance. Its receipts and a small trace-derived summary
are retained here; a fresh third two-case run remains required.

The third browser candidate found a real UI selection issue: old proposal controls and its
download stayed visible while a newly selected proposal loaded. The downloaded IDs differed
after restart, while the actual requested proposal in the database retained identical payload.
The corrected UI immediately clears old controls during selection changes. A deferred-response
test verifies that behavior, and the browser harness now checks the exact export link and
downloaded record ID. This failed candidate remains recorded as failed.

The fourth candidate completed every functional lifecycle assertion, including restart and
offline restore, with all three exports identical at SHA-256
`22770ad45ed9a9b33c10c1c8b7aecab6c9245ca322ffda59f488d07199b6f180`.
It still **failed acceptance** because source changed during the canonical legacy compatibility
correction. The start/end fingerprint gate correctly refused that run. Receipts and small
analysis/interruption records preserve the failures; none is relabeled as final acceptance.

The fifth fresh two-case run **passes final browser acceptance**. Both cases retain source
SHA-256 `807fccad2485930cb13a2b971ab55267d25c282c0e67493a346f0d33b0489af5`
before and after execution. The controlled case exercises the entire corrected lifecycle,
the actual Monitoring pane, 375-pixel mobile view, restart and offline restore. Its 23 cycles
contain 21 independent settled events. All three exported readiness records are identical at
SHA-256 `13f3f7167526a10d32d1937e2dc0feb6a7c114ae6fddfba6818faca84f0ceca7`;
one unchanged export is retained here. The production case refuses the same synthetic source.
The small accepted summary, original receipts and Playwright results are retained; seven
screenshot hashes are recorded. Python 3.13.14, Node 24.22.1 and Chromium 141.0.7390.37 ran the
procedure. Test listeners and private fake owner directories were cleaned up afterward.

The original 1,948-case local full run **finished with 1,947 passing and one failing case
in 2,203.83 seconds**. The unchanged legacy sustained-partition listener's HTTP POST to
`/api/weather/datasets` timed out during concurrent heavy work, followed by a cleanup error
while request work continued. Its actual
failure log and a JUnit-derived summary are retained. The same unchanged test subsequently
**passes alone in 38.09 seconds**; its actual scoped log is retained. The failed broad run
remains recorded as failed. This is classified as a concurrent-load test timeout; no
production fix or test-timeout relaxation was applied. This full run predates the
canonical compatibility correction; focused 28-case coverage checks that difference. All
15 monitoring and 16 service cases passed in that broader run.
[Final-source GitHub CI run 43947708763](https://github.com/GabeSternberg/EntropyTrade/actions/runs/43947708763)
passes all **1,952 cases**, including four new canonical legacy compatibility tests.
That complete final-source CI run satisfies the regression integration gate. No complete local
or CI pass is claimed by this packet yet.

The monitoring cases use actual retained forward observations and account commits. They
cover fixed post-reference degradation windows, incomplete-tail preservation, raw/model
corruption, separate deployment histories, owner-reviewed envelopes, realized loss/drawdown,
at-cost exposure, durable suspension and a single bounded offline investigation through
repeat/restart/cancel/crash. Settlement-only cases preserve the original held contracts and
cash history, use fresh official outcome receipts, refuse new decisions/fills and honor
claim epochs. These controlled results prove software behavior only.

All positive scientific/account examples are **synthetic**. No authentic strategy is
currently eligible. Genuine forward history and point-in-time books, human-certified fees,
authenticated provider verification and prospective validation remain open. The unchanged
exact-touch strategy cannot pass adverse execution stress. No live orders, exchange account
credentials, canonical collector access or physical Windows configuration occurred.

`retained-files.json` records SHA-256 and byte counts for the copied small
logs/receipts. Large screenshots, traces and controlled workspaces remain in `data/cache`;
their screenshot hashes are recorded in `acceptance.json`. Owner credential files, RAM
sessions and private fake test setup were not copied into this packet. The committed browser
harness can regenerate the acceptance evidence.
