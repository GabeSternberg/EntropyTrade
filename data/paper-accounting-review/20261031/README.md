# Durable simulated paper accounting — October 31, 2026

Implemented on the designated `supervisor/20261031-002357` checkout from `92a0ec2`.
No Git mutations, supervisor-control changes, credentials, exchange orders, live activation,
risk-cap increases or new market family. **V1 remains incomplete. Independent acceptance
and all Git operations belong to the supervisor.**

The continuous collector now reuses PaperBroker, Ledger, reviewed fee versions and official
binary-outcome reconciliation for an isolated per-monitor simulated account. Original
shadow observations/intentions stay separate from simulated decisions, fills, positions,
cash, fees and settlement. The website exposes the account and per-cycle execution audits,
plus current-account and full-evidence downloads. See [the operating guide](../../../docs/paper-accounting.md).

Executed current-source evidence:

| Check | Result and durable evidence |
|---|---|
| Ruff lint/format | Pass; [lint](final/ruff.log), [format](final/format.log), 531 formatted files. |
| Strict mypy | Pass, 531 files; [log](final/mypy.log). |
| Accounting and related regressions | **293 passed in 61.89 seconds**; [log](final/accounting-and-recovery.log), [JUnit](final/accounting-and-recovery.xml). Includes all 19 new accounting unit cases, two full integration/recovery cases and existing tracking, frozen models, fee evidence, workspace recovery and shadow collection checks. |
| Frontend assertions | All **21 named assertions** pass in a direct Node invocation; [log](final/frontend-direct.log). Ordinary `node --test` also exits successfully but reports a single file-level case in this environment; the attempted unsupported `--test-isolation=none` flag is retained separately and is not a pass. |
| Test discovery | **1,130 tests collected**; [collection log](final/collection.log). Collection is not execution. |
| Synthetic accounting and offline restore | [Controlled export](final/controlled-export.json), [receipt](final/controlled-receipt.json): five paper cycles, two fills totaling three contracts, fee transition, exhausted depth, one settlement despite repeated outcomes, no positions left, exact reopened export after snapshot/restore. All success is CONTROLLED SYNTHETIC software evidence. |
| Authentic refusal and offline restore | [Authentic export](final/authentic-export.json), [receipt](final/authentic-receipt.json): exact original receipts, no new acquisition, missing models/fees, zero fills, zero fees and no settlement; exact reopened export after snapshot/restore. No historical availability was invented. |
| Offline reproduction | Both full exports replay successfully through `python -m entropytrade.tracking.accounting`; each local fixture cycle additionally checks artifacts and original/paper decision replay. This verifies computation and account continuity, not source truth. |
| Source fingerprint | [561 source/configuration hashes](final/source-hashes.json) identify the final implementation. Previously tracked data bytes are unchanged (`git diff --numstat -- data` is empty). |

The accounting tests cover later sized-book causality and minimum latency, stale/future/
closed/crossed/missing receipts, improvement clamps on YES and NO, IOC reductions/FOK
refusal, side-specific liquidity non-reuse across restart and opposite-side changes,
execution-time fees/conflicts/expiry, minimum edge, fee-inclusive per-trade/per-event/total
deployment caps, protected/model/fee refusals, atomic/idempotent commits, paused and stale
workers, uncommitted outboxes, missing/corrupt accounts, duplicate/conflicting settlement,
receipt-time payouts, full collector integration and legacy/current workspace restore.

The complete-suite attempt was started and interrupted after it stalled in the first
existing collector test; [its log](pytest.log) is incomplete and **not a pass**. A separate
bounded per-file run attempted the remaining existing files with 120-second external
deadlines and four processes. Exact results, XML and stacks are in
[per-file results](per-file/results.json). Per-file totals: 208 files passed,
six listener files failed on socket denial, eleven files
reached their deadlines and the first collector file remained interrupted/unverified.
The broad checks ran during implementation; the final targeted 293-case pass above
identifies current-source verification. The new integration file is
covered by that targeted run, not the earlier file-discovery list. Listener failures show
`PermissionError: [Errno 1] Operation not permitted` during socket creation. Other timeout
stacks are retained, including async waits, worker completion, MLflow/research and the
130-cycle history fixture; a deadline alone does not prove an environmental cause. They
remain unverified and require the complete suite in a permitted environment. The broad
targeted attempt including that slow history fixture was also interrupted; its partial
`final/targeted.log` is not the final passing targeted check. No tests/assertions were weakened.

Managed Chromium installed using the existing supported `npm run install:chromium`
procedure with the repository-managed browser path. The initial two-case invocation
launched Chromium twice before the test bodies; both failed at
`crashpad/util/linux/socket.cc:45`, `setsockopt: Operation not permitted`, SIGTRAP.
No page interaction or localhost browser listener ran. [Playwright results](browser/playwright-results.json),
[JUnit](browser/playwright-results.xml) and both traces in `browser/playwright-artifacts/`
retain the failure. **Zero screenshots, browser downloads or new UI acceptance passes are
claimed.** The denial was not retried after inspection; no launch flags, permissions or
test assertions were bypassed. The new `npm run test:paper` harness stops on its first
failure. Run both procedures on actual localhost listeners in a permitted environment
with fresh workspace/evidence paths before accepting browser behavior.

Earlier `*-setup.json` receipts describe intermediate implementations and are superseded
by `final/`. The initial file named `authentic-setup.json` was produced without `--authentic`
and is explicitly labeled CONTROLLED SYNTHETIC in its contents; it is not authentic
evidence. `real-refusal-setup.json` and `final/authentic-*` use the actual authentic option.
Those earlier receipts and original input bytes are preserved without reclassification.

Remaining acceptance: the complete pytest suite, actual new browser inspection/downloads
and independent supervisor review. This reused the installed environment; no fresh clean
install was performed. Authentic fitted models/labels, certified effective fees, empirical
validation on two distinct families, authorized external-provider execution and final V1
release review remain open. Account equity is at cost; no empirical performance or
profitability is established. Preserve Bitcoin and its frozen validation windows, continue
authentic forward collection and defer another family or major phase to user approval.
