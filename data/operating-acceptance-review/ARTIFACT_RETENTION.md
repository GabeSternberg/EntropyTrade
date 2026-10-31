# Generated acceptance artifacts and checkpointing

Keep generated evidence at its original local paths. The scoped `.gitignore` excludes
Playwright's `playwright-artifacts/` trees and workspace `*.zip` archives from new staging,
along with the previously excluded installations/package caches. Reports, receipts,
screenshots, downloaded JSON/text, JUnit, logs and verification scripts remain eligible
for the supervisor's checkpoint. This policy does not untrack existing files.

[The October 31 inventory](local-artifacts-20261031.json) fingerprints **1,096 files,
261,903,008 bytes** across the four permitted attempts. Its 362,515-byte manifest records
original repository-relative paths, byte counts, SHA-256 hashes, ignore-policy identity,
and the unchanged acceptance-receipt identities/statuses. Three failed attempts remain
failed; the serial operating pass remains distinct from incomplete V1 release acceptance.
The reported raw trace is 13,926,914 bytes and remains present at its original path.
The inventory includes final trace ZIPs, failed/interrupted raw traces, trace resources,
failure screenshots inside those trees and all workspace archives, including archives
larger than the reported blocker. Nothing is deleted, repacked, truncated or retimed.

Verify the retained files with standard-library Python from the repository root:

```bash
python3 tools/review_artifacts.py verify \
  data/operating-acceptance-review/local-artifacts-20261031.json
```

Verification rehashes every member and compares the complete selected-file inventory,
policy and acceptance receipts. Missing, changed or additional members fail. Symlinks
and paths outside direct review bundles are refused. This check does not rerun acceptance,
promote failed attempts or set V1 complete. The original executed browser reports and
source/restore checks keep their original clocks and scope.

For future stopped review bundles, create a **new** manifest before handing changes to
the supervisor; capture refuses to overwrite an existing manifest:

```bash
python3 tools/review_artifacts.py capture \
  --output data/operating-acceptance-review/local-artifacts-NEW.json \
  --bundle data/operating-acceptance-review/NEW
```

The manifest deliberately excludes installed environments and package/browser caches.
Retained source/install verification records historical matching; caches and installations
are not portable archival evidence. Do not run the original mutable verifier to pretend a
changed checkout is the original installation, or overwrite earlier verification receipts.

A Git checkout alone cannot inspect these local traces or restore these archives. A reviewer
must obtain the retained files separately, put them at their recorded relative paths and
run the verifier. A hash without its bytes establishes no independent trace/restore pass,
authenticity, empirical validation or profitability. The current repair verifies the local
bytes; no remote artifact upload, archival service or future availability is established.

## Existing tracked artifacts: separate review proposal

Four pre-existing tracked files elsewhere exceed 8,000,000 bytes:

| File | Bytes |
|---|---:|
| `data/debugging-review/20261031-provider-deadline/browser/playwright-artifacts/provider-provider-backed-w-a84c4-s-cancellation-and-recovery/trace.zip` | 9,032,210 |
| `data/provider-review/20261030-pricing/browser/playwright-artifacts/provider-provider-backed-w-a84c4-s-cancellation-and-recovery/trace.zip` | 8,272,941 |
| `data/public/kalshi-public/historical-trades/prints.sqlite` | 25,595,904 |
| `data/workbench-review/20261026T203717Z/browser-attempt-2/playwright-artifacts/workbench-four-documented--dbdf4-n-the-committed-application/trace.zip` | 8,532,066 |

They are unchanged and are not the new checkpoint candidates. Preserve them in this repair.
If repository size needs a separate migration, first create reviewed hashes and a verified
durable storage/retrieval path, update each consuming evidence/source reference, and test
clean-checkout retrieval and offline reproduction. Only then propose removing tracked
copies through a normal reviewed commit. The historical-trades database is source data
and requires its provenance and all consumers to be reviewed separately from browser traces.
Do not rewrite history, use `git rm --cached` as an automatic fix, or substitute a manifest
for required input bytes. No tracked-artifact migration is performed here.
