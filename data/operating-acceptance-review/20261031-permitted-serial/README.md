# Private-workbench operating acceptance — permitted serial execution

Work stays on `supervisor/20261031-033238` from `2f8d9ad`. The supervisor owns all Git
mutations and independent sign-off. **Operating acceptance is verified; V1 remains incomplete.**
All 14 driver steps pass, with `acceptance_complete=true`. No real credentials, real orders,
live execution, new family, source backdating or changed risk/holdout boundaries are used.

Checkpoint retention correction: generated Playwright trees and workspace ZIPs remain
at their original local paths and are excluded from new staging. The
[manifest](../local-artifacts-20261031.json) hashes every retained artifact across this
run and all three failed attempts. [Verification and checkout limitations](../ARTIFACT_RETENTION.md)
apply to every trace/archive link below: a Git checkout alone lacks those local bytes.
Reports, receipts, screenshots and downloaded results remain eligible for checkpointing.
The existing execution/verification receipts below retain their original scope; the
retention repair does not rerun or rewrite them.

The actual command, through the standard approved runtime path, is:

```bash
python3 tools/local_acceptance.py \
  --output data/operating-acceptance-review/20261031-permitted-serial \
  --port 43294 \
  --uv-cache-seed /home/gabriel/.cache/uv \
  --npm-cache-seed /home/gabriel/.npm \
  --chromium-seed frontend/browser/.browsers \
  --test-seconds 900
```

Run one invocation at a time. Offline package/browser artifacts seed a **new** installation,
not an existing virtualenv or personal browser. The child environment excludes inherited
provider/exchange credentials and HOME. Supported approval permits real localhost/socketpair
operations and managed Chromium without modifying the sandbox or launch settings.

## Executed browser procedures

[Actual execution log](browser.log), [JSON report](browser/playwright-results.json) and
[JUnit](browser/playwright-results.xml) record **six passed in 5.4 minutes**, no skipped
procedures and no missing required identities. Playwright-managed Chromium is
`141.0.7390.37`. These are actual localhost/page interactions, not HTTP doubles or discovery.

| Procedure | Screenshots | Downloads | Executed behavior |
|---|---:|---:|---|
| [Operator alerts](browser/alerts/receipt.json) | 4 | 6 | Page acknowledgement of three incidents, listener restart, recovery, recurrence with fresh acknowledgement required, offline restore and identical restored download. Health/outcome signals are controlled. |
| [Controlled paper account](browser/controlled/receipt.json) | 2 | 4 | Two simulated fills, one settlement, $0.08 fees, $1,001.42 final simulated cash; account/evidence download, offline replay and identical reopened downloads. Synthetic software evidence only. |
| [Authentic paper refusal](browser/authentic/receipt.json) | 2 | 4 | Original receipts retain $1,000, zero fills/fees/settlements and explicit missing-model/fee refusals; offline replay and identical reopened downloads. |
| [Controlled provider](browser/provider-browser-receipt.json) | 8 | 14 | Consent, three typed hypotheses, deterministic real-data insufficiency, pricing/outage refusal, cancellation/interruption/restart, exact reopened bytes and zero-request missing-key failure. No external provider session. |
| [Local research/recovery](browser/recovery-browser-receipt.json) | 5 | 11 | Synthetic and recorded research, all result tabs, live read-only collection, paused/active monitor recovery, offline workspace restore, fresh post-restore cycle, cancellation and another restart. |
| [Authentic retained weather](browser/weather-browser-receipt.json) | 5 | 4 | Original receipt import, repeated immutable freeze, exact dataset selection, research, explicit four-event/two-date insufficiency and identical downloads after restart. No source-matched scalar highs or fitted empirical probabilities. |

Total: **26 screenshots, 43 downloads, six retained traces and zero page errors**.
[Final verification](verification.json) checks every screenshot/download hash, all six intact
trace ZIPs and **19 byte-identical download comparisons**. The execution parser requires
the six exact procedure identities, successful result records and consistent statistics;
none are skipped or missing.
Trace ZIPs and failure screenshots for earlier attempts are retained separately below.

## Installation and quality gates

[Driver receipt](acceptance.json) records exact commands, source fingerprints, timestamps,
exit codes and discovery/execution report hashes. Lock check, locked sync, 117-package
inventory, backend Ruff/format, strict mypy (535 files), 22 frontend checks, pinned npm
installation, supported Chromium provisioning, full/selected discovery and OS preflight
pass. The [complete pytest log](pytest.log) records **1,210 passed in 644.82s**, process exit
zero, with no failures/errors/skips; [JUnit](pytest.xml). This is the whole suite, with no
deselections or test retries. Slow cases trigger the unchanged 45-second traceback diagnostic;
their eventual passing results and complete JUnit remain authoritative. Individual case names
are logged. [Additional checks](additional-quality.json) pass driver Ruff/format and syntax
for both repaired browser procedures.

## Final provenance and offline recovery

[The executable verifier](verify_results.py), [its successful log](verification.log) and
[verification receipt](verification.json) cross-check actual reports and durable bytes.
[All 1,578 source/input fingerprints](source-verification.json) match both checkout and
fresh installation. [All 68 original receipt and five Bitcoin boundary hashes](safety-receipt.json)
match the prior safety baseline; nothing is retimed or regenerated.

[Offline restore of the exact stopped paper browser workspaces](paper-offline-restore/receipt.json)
passes: both canonical restored exports equal the actual browser downloads and both account
chains reproduce. Controlled/authentic archives and restored JSON remain under
`paper-offline-restore/`; [the executed script](restore_paper_downloads.py) and
[log](paper-offline-restore.log) are retained. This is additional offline verification, not
another browser procedure. The alert procedure's actual snapshot is retained as
[workspace.zip](browser/alerts/workspace.zip).

[Final stopped recovery, provider and weather workspaces](workspaces/receipt.json) are
snapshotted and every archive member checked against its manifest by
[this executed script](retain_workspaces.py); [log](retained-workspaces.log). They preserve
208, 77 and 134 files respectively, including the fresh authentic receipts acquired after
restore. The initial recovery archive/manifest also remain under `browser/`. The recovery
procedure's first fresh public capture retains eight successful source receipts, 12 listed
contracts and 648 observations at its original October 31 receipt clocks. History remains
incomplete; those fresh receipts establish no fitted model, empirical returns or historical
availability. Installed environments and package/browser caches are ignored; archives,
source inventories, reports, screenshots, traces and downloads are retained for review.

## Concrete failures retained and repaired

1. [Attempt 1](../20261031-permitted-attempt-1/acceptance.json): three browser procedures
   pass; provider reopening downloads the preceding failed job's review; two procedures
   do not run. [Diagnosis](../20261031-permitted-attempt-1/failure-diagnosis.json) and trace
   show that a shared `failed` badge was accepted before the new run loaded. The helper now
   waits for the exact requested title and verifies both download URLs against its submitted
   job ID. Every original byte-equality check remains. Its subsequent full suite exits
   **-11 (SIGSEGV)** without a complete JUnit report. The underlying native-crash cause is
   not established; overlapping verification was present. It is not a complete-suite pass.
2. [Attempt 2](../20261031-permitted-attempt-2/acceptance.json): five browser procedures
   pass; the weather helper rejects metadata outside the installed repository. The
   [diagnosis](../20261031-permitted-attempt-2/failure-diagnosis.json) retains the exact
   `ValueError`. Browser setup now stages metadata under installed `data/cache/`, then
   copies it with exclusive creation to the surrounding evidence directory. The original
   helper's confinement guard and all source bytes/clocks remain unchanged. The overlapping
   suite has one HTTP read-timeout failure and 41 passes before deliberate SIGINT; its
   cleanup errors and incomplete JUnit/log are retained, not treated as passes.
3. [Attempt 3](../20261031-permitted-final/acceptance.json): alert acknowledgement times
   out under the unchanged 10-second expectation. The [trace diagnosis](../20261031-permitted-final/failure-diagnosis.json)
   records a successful acknowledgement request taking 17,605.483 ms. Two superseded
   verification runs were still active; resource contention is possible, not proven as
   the cause. This suite is deliberately interrupted. No limits/assertions are relaxed.

All superseded processes are stopped/finished before the current serial run. Its alert
procedure passes unchanged. Pytest verbosity is increased solely to retain the last case
name on a future crash. The final serial suite passes without reproducing the native crash;
its underlying cause is still not established. No application, model, fee, settlement or
risk code changes. Earlier failed reports/logs/traces are never overwritten by the serial pass.

## Remaining release scope

V1 remains **complete=false** despite the verified software operating pass. Separately
authorized external-provider verification, sufficient authentic source-matched model/backtest
history, certified effective fees, empirically validated distinct families and independent
release review remain open. Controlled provider/accounting/health results cannot satisfy
these gates. Preserve authentic forward collection and frozen Bitcoin windows. Another
major market family requires user approval. No next major phase begins here.
