# Persistent checkpoint blocker repair — October 31, 2026

Implemented in place on `supervisor/20261031-033238`; all Git mutations and the actual
checkpoint remain with the supervisor. No supervisor controls, application safety gates,
risk limits, receipt clocks, settlement rules or production execution paths are changed.

The reported 13,926,914-byte raw Playwright trace was untracked. Inspection also found
oversized finalized traces and workspace ZIPs in the other generated review bundles.
The staging index was empty; no unstage/remove operation was needed or performed.

[The scoped ignore policy](../.gitignore) now excludes generated Playwright artifact
trees and workspace ZIPs from future normal staging. All bytes remain at their original
local paths. [The 362,515-byte manifest](../local-artifacts-20261031.json) fingerprints
**1,096 files / 261,903,008 bytes** across the four attempts, anchors the ignore policy
and original acceptance receipts, and documents verification limitations. The first
three receipts remain failed/incomplete; the serial operating pass remains distinct
from incomplete V1 acceptance. No reports or old failed evidence are rewritten.

The [retention guide](../ARTIFACT_RETENTION.md) documents a new-manifest workflow and a
separate safe migration proposal for four existing large tracked artifacts elsewhere.
They remain unchanged. Reports, receipts, logs, standalone screenshots, downloaded
JSON/text and verification scripts remain eligible for the supervisor's review.

## Executed repair checks

[Quality receipt](quality.json) records exact commands, clocks and zero exit codes:

- Ruff lint and format pass for `backend` and `tools` (540 files already formatted).
- Strict mypy passes on 537 source files, including the new typed retention utility.
- [66 focused pytest cases](pytest.log) pass: 13 retention-integrity cases plus all
  53 existing acceptance-driver cases. [JUnit](pytest.xml) has no failures/errors/skips.
  Tests exercise changed/missing/additional evidence, unchanged failed receipts,
  no-overwrite capture, path confinement and symlink refusal. Controlled test bytes
  establish software behavior only.
- All 22 frontend checks and syntax checks for both previously repaired browser procedures
  pass. No browser assertions, limits or full-acceptance parser requirements are weakened.
- The standard-library verifier rehashes all 1,096 actual local artifacts successfully.

[The read-only audit](verify_checkpoint.py) and its [final receipt](verification.json)
check ordinary Git visibility without staging anything. Every manifest member is ignored
and untracked; **zero eligible changed/untracked files exceed 8,000,000 bytes**. The
largest candidate is 971,467 bytes. The index remains empty. This is a candidate-size
audit, not an execution or modification of the supervisor's actual checkpoint command.

The same audit rechecks all **1,578 original checkout/install fingerprints**, **73 original
receipt/boundary hashes**, **43 download hashes**, **26 screenshot hashes** and **six final
trace hashes plus ZIP integrity**. The original browser report still requires and passes
all six exact procedure identities. Original complete-suite JUnit still records **1,210
tests, zero failures/errors/skips**, with all original driver steps passed. These are
checks of prior execution evidence, not new page interactions or a full-suite rerun.
`verification-initial.json` retains the earlier audit before the final JUnit cross-check.

Reproduce byte retention and the read-only audit from the repository root:

```bash
python3 tools/review_artifacts.py verify \
  data/operating-acceptance-review/local-artifacts-20261031.json
python3 data/operating-acceptance-review/20261031-checkpoint-repair/verify_checkpoint.py
```

The second command requires the original local installation for its historical
checkout/install comparison. It prints a new receipt without changing earlier ones.

## Limitations and handoff

The original suite and six real-browser procedures were already recorded as passed;
this repair runs focused checks and audits retained evidence. It does not retry browser
launches, restore live workspaces, perform a new locked installation or claim a new
full-suite pass. Existing evidence and fresh authentic source bytes are preserved.

A fresh checkout lacks the ignored trace/archive bytes and installation. Independent
trace inspection or archived-workspace replay requires separately obtaining the files
and verifying their manifest hashes. Hashes alone do not prove authenticity or acceptance.
No remote artifact storage, future availability, empirical performance, provider session,
new family, V1 completion, actual checkpoint or Git mutation is claimed. The supervisor
can review and checkpoint this repair; no next major phase starts here.
