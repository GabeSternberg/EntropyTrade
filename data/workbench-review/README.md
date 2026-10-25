# Workbench review receipts — 2026-10-25

Latest bundle: [20261025T163400Z](20261025T163400Z/receipt.json). The full automated
suite, actual localhost listener/worker workflows and successful public weather/Bitcoin
acquisition now pass. **Browser acceptance remains blocked by unavailable browser access.**
The implementation remains uncommitted on `supervisor/20261025-014400`; the current user
instruction reserves all Git mutations and commit-based reproduction for the supervisor.
No branch, staging, commit, merge or push was attempted in this continuation. HEAD remains
`30bed8e30cf07201124deee609a21f7f01e47735` and does not contain this implementation.

The UI now shows acquisition completeness, HTTP receipts (successful responses separately),
listed contracts, observations and clocked failure summaries without expanding details on
all three result tabs. Text reports include the same summary and settlement/evaluation
limitations. Complete review status never implies successful acquisition or evaluation.

[Full check log](20261025T163400Z/make-check.log): Ruff lint/format pass, strict mypy
passes across 477 files, and **733 pytest tests pass in 154.68 seconds**. Locked setup and
entry-point help pass. Five new public-worker cases cover connection failures, HTTP errors,
partial/complete captures and empty listings, saved summaries and closed evaluation gates.
[Nine Node presentation checks](20261025T163400Z/frontend-check.log) cover failed/partial
acquisition on every tab, literal source text and synthetic banners. No tests were skipped,
xfail-marked, weakened or given relaxed warning handling. Local listeners/public HTTPS ran
with normal per-command approval; no sandbox bypass was used. See [command evidence](20261025T163400Z/checks.json).

| Retained run | Verified result |
| --- | --- |
| [Recorded weather](20261025T163400Z/recorded-weather/review.json) | 36 contracts, six events, three dates, zero eligible events/scalar labels; two INSUFFICIENT_DATA candidates; no probabilities, metrics or scenarios |
| [Synthetic weather](20261025T163400Z/synthetic-weather/review.json) | 192 permitted validation records, first 100 exposed; negative control zero fills in three scenarios; software proof only |
| [Public weather](20261025T163400Z/public-weather/public/capture.json) | 8 successful HTTP receipts, 24 listed contracts, 648 observations, zero acquisition failures; successful forward ingestion |
| [Public Bitcoin](20261025T163400Z/public-bitcoin/public/capture.json) | 3 successful HTTP receipts, 318 listed contracts, one Coinbase spot observation, zero acquisition failures; all settlement gates remain closed |
| [Denied-network Bitcoin](20261025T163400Z/blocked-network-bitcoin/report.txt) | Actual ordinary-sandbox worker: clocked KXBTC GatewayError and Coinbase ConnectError, zero HTTP receipts/contracts/observations; visibly incomplete report projection |

The first four runs were submitted through actual localhost HTTP, with isolated workers.
The fifth ran in a separate workspace under the ordinary network-restricted sandbox to
retain a real acquisition failure. No response receipts or data were invented. It was not
submitted through a browser or HTTP. All real-data reviews have zero fitted probabilities,
forecast metrics and execution scenarios. Current ingestion cannot supply historical
outcomes or empirical performance. Every review excludes final holdout; every Bitcoin
contract has `rules_known=false`, empty settlement sources and unresolved settlement basis.
Authority mentions remain separate lexical provenance, never verified settlement authority.

[HTTP lifecycle receipt](20261025T163400Z/http-lifecycle.json) verifies cancellation during
synthetic modeling, worker-slot reuse for a completed recorded run, shutdown with active
and pending jobs, interrupted history after restart and identical review/report HTTP bytes
for all four completed runs. HTTP export filenames are `http-review.json` and
`http-report.txt` under each run directory. Their hashes are retained across restart.
**These are HTTP-client exports, not browser downloads.** The [artifact verification](20261025T163400Z/artifact-verification.json)
rechecks all 51 workflow artifacts, protected projections and public input checksums;
public copies reload through the checksum-verifying adapter. Workflow outputs remain in
ignored timestamped cache workspaces. Training/holdout labels are not exported here.

[Browser receipt](20261025T163400Z/browser.json): no connected browser sessions were
available. Native Chrome was rejected with “Computer Use was not approved to use Google
Chrome”; the in-app browser returned “Browser is not available: iab”. Chrome access was
requested while independent work continued. No browser submissions, visual inspections,
screenshots or browser downloads are claimed. **Every browser acceptance step remains
pending**, including visible acquisition failures, cancellation and restart/history. The
[acceptance record](20261025T163400Z/acceptance.json) distinguishes automated evidence
from each unexecuted browser step. Follow [the procedure](../../docs/workbench.md#browser-acceptance-procedure)
after an approved browser becomes available.

The [source manifest](20261025T163400Z/source-state.json) and
[source patch](20261025T163400Z/source.patch) describe the current source/test/frontend/
config/build/documentation tree against the unchanged R4 base. The reverse patch check
and whitespace check pass. [Handoff](20261025T163400Z/handoff.json) explicitly defers
commit creation and reproduction from that commit to the supervisor; no Git write was
tried. No supervisor-control files or credentials were accessed for mutation.

The earlier [07:07 bundle](20261025T070710Z/receipt.json),
[06:47 bundle](20261025T064732Z/receipt.json) and [06:40 bundle](20261025T064014Z/receipt.json)
remain unchanged historical attempts. Their socket/network/staging denials and source
hashes describe those attempts, not this continuation.

To repeat, use a new empty timestamp directory and matching ignored cache workspace:
`verify.py` requires the installed loopback server and submits the first four HTTP runs;
`lifecycle.py before` prepares cancellation/restart checks, then restart the server and run
`lifecycle.py after`. `failure_capture.py` requires a network-restricted ordinary sandbox
and records that fact explicitly. It must not be used to claim successful ingestion.
`finalize_evidence.py` verifies the existing exported evidence against retained workspaces
and refreshes source hashes/patch; it never stages, commits, merges or pushes. These scripts
do not automate or satisfy browser acceptance. Run the full unchanged suite as documented
in the workbench guide, then refresh checksums after any receipt change.

Verify the retained bundle from this directory:

```bash
shasum -a 256 -c SHA256SUMS
```

Complete the pending browser procedure, let the supervisor commit the reviewed work and
verify reproduction from that commit, then return for review before integration. Official
Bitcoin outcomes/history, empirical Bitcoin modeling and continuous shadow remain later work.
