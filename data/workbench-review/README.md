# Workbench acceptance receipts

Latest continuation: [20261026T042230Z](20261026T042230Z/README.md), on reviewed commit
`c6d6d8b3e2c2e01ba2bde26424c556db66845f16`. Chrome access was denied again in this
new continuation, so all four browser procedures remain pending; no browser workaround
was attempted. The bundle binds current-source locked setup and full backend/frontend
checks to an isolated read-only export. It preserves UTC command clocks, a 2,332-file
manifest and log checksums. All 260 existing receipt checksums passed before this
documentation update. This does not replace the supervisor's independent clean-checkout
sign-off or the unexecuted browser gate. No application source or tests were changed.
The unchanged full gate passed Ruff lint/format, strict mypy and **734 pytest tests in
184.23 seconds**; JavaScript syntax and all **nine frontend tests** passed with no skips.

Previous attempt: [20261026T041240Z](20261026T041240Z/README.md), on reviewed commit
`ff3bcc9df40534396c774146405b4658f22f9753` from an initially clean working tree on
`supervisor/20261025-014400`. The workbench, Bitcoin forward adapter and SQLite acceptance
repair are committed. Local `main` remains R4's `30bed8e`; remote freshness was not checked.
The committed repair's exact patch and two Python files match the historical candidate
hashes. Its original receipts remain immutable records of an uncommitted overlay on
`99e2fbc`, not final clean-checkout verification of `ff3bcc9`. No branches, index
entries, commits, merges or pushes were changed in this continuation.

**Browser acceptance remains blocked. V1 is incomplete.** Computer Use lists no connected
browsers, denies native Chrome access and reports the in-app browser unavailable. No new
browser job IDs, screenshots, visual inspections or browser downloads are claimed. All
steps in [the browser procedure](../../docs/workbench.md#browser-acceptance-procedure)
remain pending. Automatic approval review rejected a repeat Chrome probe because Chrome
access had already been denied; no further browser attempts or workaround followed.
Return for review with this specific blocker.

The [historical bundle](20261025T191200Z/README.md) binds the earlier `99e2fbc` commit/tree to a manifest of 2,268 unchanged exported
files, a new virtual environment, locked setup, full unchanged backend checks and frontend
checks. An ordinary sandbox run retains five localhost bind-denial failures; the normal
per-command listener-capable baseline rerun then stalled in SQLite close and was terminated.
The [candidate checks](20261025T191200Z/candidate-checks.json) and source patch separately
identify the then-uncommitted acceptance fix. Its full `make check` passed: Ruff lint/format,
strict mypy across 477 files and **734 pytest tests in 155.88s**. JavaScript syntax and
all nine frontend presentation cases pass. No tests or policies were weakened. A source export is not the
supervisor's final independent clean-checkout sign-off. Early interpreter/cache setup failures
and an invalid ignored-directory Ruff attempt are retained and excluded from acceptance.

All 245 existing receipt checksums passed before this documentation update. The earlier
receipt verified 197 pre-existing checksums.
[Retained evidence revalidation](20261025T191200Z/retained-evidence.json) verifies five
reviews, 51 workflow artifacts, public manifests, protected projections and HTTP lifecycle
history without altering historical inputs or receipts. Original job IDs, UTC clocks and
export hashes remain available in the [16:34 run receipt](20261025T163400Z/receipt.json)
and [HTTP lifecycle receipt](20261025T163400Z/http-lifecycle.json).

| Retained run | Evidence and limit |
| --- | --- |
| Recorded weather | 36 contracts, six events, three dates; no eligible historical forecast/scalar-label pairs; explicit insufficiency |
| Synthetic weather | 192 permitted validation records; excluded holdout; negative control zero fills in all three scenarios; software demonstration only |
| Public weather | 8 successful HTTP receipts, 24 contracts, 648 observations; forward ingestion only |
| Public Bitcoin | 3 successful receipts, 318 contracts, one spot observation; unresolved settlement, empty verified sources, all rule gates closed |
| Failed Bitcoin worker | Zero receipts/contracts/observations and two clocked acquisition failures; incomplete acquisition |

The retained HTTP lifecycle checks cover active cancellation, worker reuse, interrupted
restart history and matching review/report exports. HTTP exports are not browser downloads;
DOM-double presentation tests are not visual acceptance. Neither public family has historical
probability evaluation or real-data returns. See [PROJECT_CONTEXT.md](../../PROJECT_CONTEXT.md)
for the remaining V1 gates. Official Bitcoin history/outcomes and continuous paper/shadow
remain later work.

Historical attempts are immutable: [16:34](20261025T163400Z/receipt.json),
[07:07](20261025T070710Z/receipt.json), [06:47](20261025T064732Z/receipt.json) and
[06:40](20261025T064014Z/receipt.json). Their earlier statements about uncommitted source,
socket/network permissions and browser access describe those attempts, not the current
reviewed commit. The old verification scripts remain historical tools, not a reason to
rewrite those receipts or claim browser success.

Verify the current receipt files from this directory:

```bash
shasum -a 256 -c SHA256SUMS
```

The supervisor handles the final reviewed commit, independent clean-checkout verification
and all Git integration. Stop for review; do not start another major milestone.
