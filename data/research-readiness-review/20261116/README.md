# Milestone E executed evidence — November 16, 2026

The implementation adds evidence-backed readiness proposals, explicit local owner review,
append-only control/review audits, persistent emergency halt epochs, degradation monitoring,
bounded offline investigations and settlement-only continuation for known held positions.
An approved proposal still has `execution_authorized=false` and `submission_enabled=false`.
It neither allocates funds nor changes the model, broker, paper limits or production gateway.
See [operations and policy](../../../docs/research-readiness.md).

**Final acceptance is pending.** Fresh complete regression, the final two-case Chromium run
against matching source fingerprints, final quality checks and GitHub CI must pass before
integration. `acceptance.json` distinguishes retained logs, earlier scoped tool reports,
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

Final frozen-source Ruff lint/format, strict mypy (**644 files**) and frontend DOM tests
(**78 tests**) pass; the small logs are retained here. Prior agents reported 70
storage/drain/recovery cases, 21 evidence
cases, 22 investigation cases and 14 monitoring cases in split 12- and 2-case passing runs.
Raw console logs for those older scoped reports were not located, so the packet labels
them as tool-result reports, rather than manufacturing complete logs or a full-suite pass.

The earlier controlled Chromium procedure passed in **474.27 seconds** with no page or
console errors. It used actual retained synthetic source wires and committed paper history:
23 cycles supplied 21 independent settled station/day events. The browser exercised owner
approval, rejection and rollback to a new pending proposal; logout, revocation and global
halt; owner release without automatic monitor resume; actual listener restart with expired
RAM sessions; offline snapshot/restore; mobile layout and Demo isolation. Exported revoked,
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

`retained-files.json` records SHA-256 and original development paths for the copied small
logs/receipts. Large screenshots, traces and controlled workspaces remain in `data/cache`;
their screenshot hashes are recorded in `acceptance.json`. Owner credential files, RAM
sessions and private fake test setup were not copied into this packet. The committed browser
harness can regenerate the acceptance evidence.
