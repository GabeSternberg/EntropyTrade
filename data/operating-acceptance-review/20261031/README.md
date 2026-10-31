# Private-workbench operating acceptance — October 31, 2026

Implemented on designated `supervisor/20261031-014049` from `b8d2538`. **Operating
acceptance and V1 remain incomplete.** All Git operations and independent sign-off belong
to the supervisor. No credentials, real orders, live activation, raised risk limits,
new family, historical backdating, supervisor-control edits or Git mutations were used.

The existing locked driver now includes **both paper procedures and alerts** alongside
research/recovery, controlled provider integration and authentic weather history. It records
discovery separately, checks OS socket capabilities before dependent execution, stops browser
execution after its first failure and records blocked/unexecuted gates. Preparation cannot
set `acceptance_complete=true`. Eight driver contract cases cover selection, denied socket
creation, denied socketpair send, descriptor closure, export inputs, child credential
exclusion, blocked execution, preparation, browser failure and successful orchestration.
Fake processes in these contract cases are never claimed as installation/browser acceptance.

## Executed results

| Check | Actual result and evidence |
|---|---|
| Fresh locked Python installation | **Pass, scoped preparation:** [final receipt](locked-reviewed/acceptance.json), [lock check](locked-reviewed/lock-check.log), [sync](locked-reviewed/locked-sync.log), [117-package inventory](locked-reviewed/installed-packages.log). New virtualenv built from the working-tree export and offline package artifacts; no existing environment reused. |
| Backend Ruff lint/format | **Pass:** [lint](locked-reviewed/ruff.log), [535-file format](locked-reviewed/format.log). |
| Acceptance-driver Ruff lint/format | **Pass:** [commands/results](driver-quality-reviewed.json), [lint](driver-ruff-reviewed.log), [format](driver-format-reviewed.log). |
| Strict mypy | **Pass, 535 source/test files:** [log](locked-reviewed/mypy.log). |
| Frontend assertions | **Pass, 22 named checks:** [log](locked-reviewed/frontend.log). |
| Fresh pinned npm and supported Chromium provisioning | **Pass:** [npm ci](locked-reviewed/npm-ci.log), [managed installer](locked-reviewed/chromium-install.log). Only npm artifact cache and the Playwright-managed distribution are seeded; no personal browser/configuration is copied. Installation does not establish launch capability. |
| Selected browser discovery | **Six tests in five files:** [list](locked-reviewed/browser-discovery.log), [JSON](locked-reviewed/browser-discovery/playwright-results.json), [JUnit](locked-reviewed/browser-discovery/playwright-results.xml). Both paper procedures, alerts, provider integration, local recovery and authentic weather research are selected. **No page interaction executed.** |
| Fresh focused pytest | **394 passed in 40.52s; zero failures/errors/skips:** [command/environment/deadline](focused-reviewed-command.json), [log](focused-reviewed.log), [JUnit](focused-reviewed.xml). Includes all eight driver cases, all eleven alert cases and the unchanged accounting/collector/fee/execution/risk/replay/workspace recovery/property checks. This is not the complete suite. |
| Offline paper reproduction, reopen and restore | **Both pass:** [verification receipt](offline/receipt.json), [controlled export](offline/controlled-shadow.json), [authentic export](offline/authentic-shadow.json), retained workspace archives. Original/exported canonical JSON matches after reopen and verified offline restore. Controlled account has two simulated fills and one settlement. Authentic receipts retain $1,000, zero fills/fees/settlements and explicit missing-model/fee refusals. |
| Offline alert acknowledgement and lifecycle | **Pass:** [receipt](offline/receipt.json), [final export](offline/alerts-final.json), [archive](offline/offline-alerts.zip). Acknowledgement retries are idempotent; reopen preserves acknowledgements; three incidents recover; recurrence creates a new unacknowledged failure incident; restored export hash is identical. These are controlled health/outcome signals and store operations, not page clicks or authentic outcome evidence. |
| Source/export integrity | **All 1,578 hashes match checkout and installed export:** [comparison](source-verification.json). All **68 original receipt files** are exported intact and remain unchanged; all **five Bitcoin boundary implementation/manifest hashes** match earlier evidence: [safety receipt](safety-receipt.json). The original v1 account fixture also copies byte-for-byte. |
| Overall scope | [Verification summary](verification.json): `operating_acceptance_complete=false`, `v1_complete=false`. Browser workflows, screenshots and full-suite attempts in this milestone: **zero** after the capability denial was confirmed. |

The [offline script](offline_checks.py), [exact invocation](offline-command.json) and
[log](offline.log) use the final fresh environment. Exports and archives remain durable here;
installation directories and package/browser caches are ignored. Offline byte equality
never establishes browser downloads or actual localhost restart behavior.

## Retained export failures and repairs

No failing result was rewritten or assertion weakened:

1. The first provision-only export, [locked](locked/acceptance.json), omits the existing
   v1 account fixture. Its isolated unchanged compatibility test fails with `FileNotFoundError`:
   [log](locked/initial-export-fixture.log), [JUnit](locked/initial-export-fixture.xml).
2. The next export, [locked-final](locked-final/acceptance.json), includes that exact fixture
   but still copies only public weather captures. Fresh focused verification records
   **393 passes and one failure in 40.00s**: [command](focused-command.json), [log](focused.log),
   [JUnit](focused.xml). Authentic alert replay needs the original saved `result.json` and
   decision inputs alongside the captures.
3. The final export, **locked-reviewed**, copies the two complete original cycles plus the
   original compatibility fixture, retaining their provenance and bytes. Its 394-case run
   and offline authentic/controlled procedures pass. No source receipt, saved decision,
   result, historical audit or test expectation was regenerated to repair missing inputs.

Earlier provision receipts remain preparation-only regardless of their independent gates.
The aggregate summary refers exclusively to `locked-reviewed` and the final checks.

## External blocker and outstanding acceptance

The actual direct OS probe at **2026-10-31T05:41:21.038364+00:00** fails on both localhost
socket creation and `socketpair()` with **`PermissionError(1, 'Operation not permitted')`**.
[Exact result and scope](environment-blockers.json) are retained. This is the same restriction
as the preceding milestone's [Chromium launch failure](../../operator-readiness-review/20261031/browser-attempt.log)
at `crashpad/util/linux/socket.cc:45`, `setsockopt: Operation not permitted`, SIGTRAP, and its
recorded collector/full-suite stalls. That launch/stall is **not retried**. No sandbox change,
launch-flag change, permission escalation or HTTP-only substitute is used.

The new driver's preflight is covered by contract tests. The actual denial here comes from
the initial direct capability probe; all three fresh provisioning invocations deliberately
use `--prepare-only`, which does not repeat the socket probe, launch Chromium or run pytest.
Focused pytest and offline proofs are separately invoked and recorded above.

In an environment permitting localhost listeners, asyncio socketpairs and managed Chromium,
the operator/supervisor must run:

```bash
python3 tools/local_acceptance.py --output data/operating-acceptance-review/NEW-NAME
```

Use a fresh output path and **omit `--prepare-only`**. Optional offline artifact seeds are
documented in [local recovery](../../../docs/local-recovery.md). The exact preparation run
used here is reproduced with:

```bash
python3 tools/local_acceptance.py \
  --output data/operating-acceptance-review/NEW-PREPARATION \
  --uv-cache-seed /home/gabriel/.cache/uv \
  --npm-cache-seed /home/gabriel/.npm \
  --chromium-seed frontend/browser/.browsers \
  --prepare-only
```

Require the complete pytest suite and all six actual browser workflows, including page
acknowledgement, recovery/recurrence, listener restart, offline restore and identical
downloaded bytes alongside research-to-results. Retain screenshots, traces, download hashes,
page-error counts, listener logs and source fingerprints. Discovery/offline success cannot
satisfy these steps. Stop retries in this restricted environment.

The [current V1 matrix](../../../docs/v1_acceptance.md) keeps separately authorized actual
provider verification, authentic model/fee validation, two-family empirical evidence and
independent release acceptance open. Continue authentic forward collection, preserve original
receipt clocks and frozen Bitcoin boundaries, and obtain user approval before selecting
another major family. Return these implementation/acceptance repairs for supervisor review;
no next major phase or successful operating milestone is claimed.
