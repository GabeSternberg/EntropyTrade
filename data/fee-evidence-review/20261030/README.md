# Point-in-time fee evidence — October 30, 2026

Implemented in place on designated `supervisor/20261030-205940` from `99870f2`. The
supervisor owns all Git operations and independent review. **V1 remains incomplete.**
No credentials, orders, live activation, risk-limit loosening or new family selection.
Original source receipts and Bitcoin validation boundaries are preserved.

The shared FeePolicy and fee calculator now consume immutable server-managed evidence in
continuous cycles and real research/experiment jobs. Versions retain exact official bytes,
receipt/review clocks, series scope, coefficients, citations and bounded effective intervals.
Series metadata, failed documents and unsupported rounding cannot certify a fee. Newly
reviewed documents cannot become historically available. Missing/conflicting/late/inapplicable
and expired evidence refuses. Controlled evidence cannot qualify real data. Captured series
conflicts also refuse, while corrupt source/version hashes fail the cycle or download.

See [the operating guide](../../../docs/fee-evidence.md) for commands, local operator review
trust boundaries, limitations and portable replay. Publication is atomic and never overwrites
a prior version. The local command owns certification and review clocks; the browser exposes
inspection/downloads only. A human interpretation of an accessible official schedule is still
required. No authentic fee policy was certified here.

## Executed acceptance

| Requirement | Evidence | Result |
| --- | --- | --- |
| Missing/conflicting/late/inapplicable/expired evidence | `backend/tests/unit/test_fee_evidence.py`, shadow decisions plus complete R4 candidate evaluation | Refused before intentions/scenarios; inputs round-trip offline. Exact effective boundaries and later-known conflict clocks tested. |
| Series metadata cannot certify; unsupported/failed evidence | Same unit file; `fee_evidence.FeeVersion` and local admin | Explicit document/citation/scope/interval/rounding/receipt validation, original HTTP 429 refusal, series-only refusal, controlled-to-real refusal and review-clock injection rejection. Authentic certification requires the retained official schedule PDF. |
| Fee-inclusive reservation caps across restart | `test_fee_inclusive_reservations_survive_store_restart`; CONTROLLED browser setup/export | Four $20 intentions reserve fees as well as notional. Fifth same-event intention is rejected rather than crossing the $100 event cap. Reopened stores retain earlier reservations; no risk cap changes. |
| Fee changes during experiment latency | [CONTROLLED portable experiment](CONTROLLED-experiment/results.json), [verification](controlled-experiment-verification.json), executable `controlled_experiment.py` | Two immutable versions change during latency. Existing calculator/interpreter/risk/ledger simulate 20 controlled fills; saved inputs reproduce both candidate results offline. No empirical claim. |
| Actual managed Chromium, localhost inspection and downloads | [CONTROLLED receipt](browser-final/controlled/receipt.json), [authentic receipt](browser-final/authentic/receipt.json), Playwright reports/traces | Both procedures pass. Five screenshots, fourteen checksummed downloads and zero page errors. Original bytes match their version SHA-256/base64. Actual server restart preserves reopened version/source/shadow downloads byte-for-byte. |
| Authentic research remains honest | Authentic browser review/fee downloads and screenshots | Original shadow receipts keep clocks and missing model/fee gates. Ordinary legacy-weather research finishes with zero fitted probabilities, scenarios or tested candidates. Its fee download freezes the unreviewed official receipt, never a substituted coefficient. |
| Offline restart/restore and reproducibility | [Offline verification](offline-verification.json), `verify_offline.py`, two workspace archives | Fee versions compare equal after snapshot/restore. Five controlled and three authentic cycles replay; the restored authentic two-candidate experiment reproduces its original refusal. No sources/providers/executable models requested. |
| Fresh official source receipt | [Summary](fresh-capture.json), [version](fresh-source-version.json), [original bytes](fresh-source.html) | Unauthenticated official PDF GET returns HTTP 429 at `2026-10-31T01:08:59.041209Z` (October 30 local time). Response bytes retained, no certification. Prior October 2 receipts remain unchanged. |
| Provenance/safety and quality | Source hashes, original-receipt check, lint/type/frontend logs, final full pytest report | See final verification receipt for exact results. Existing installation reused; no clean-install/release pass claimed. |

The browser harness is `frontend/browser/fees.spec.cjs`. It uses Playwright-managed Chromium
with a fresh context and actual server/worker subprocesses. Controlled intentions are seeded
only by `tests.integration.fee_fixture` using synthetic data and existing evaluators/store;
they are **not** proof of an authentic collector/model becoming eligible. The separate
authentic workspace imports original receipts, appends a clearly labeled offline decision
reevaluation, and never edits original response bytes/clocks or presents it as new acquisition.
The authentic flow submits ordinary research through the website. No request interception,
Computer Use, personal Chrome, production fixture switch or loosened launch policy is used.

The supported managed Chromium installer succeeded. Normal approved, credential-free browser
and localhost execution passed twice: initial evidence remains under `browser/`, final
checks under `browser-final/`. Neither run encountered a browser/socket denial. An initial
sandboxed public GET stalled with no receipt and was explicitly interrupted (exit 130);
`source-attempt.txt` records this. The separate bounded approved GET retained its real 429
response; no fabricated body/clock was substituted and no denied browser launch was retried.

The first full-suite attempt exposed three controlled collector adapters that did not accept
the newly frozen fee-version argument. It was interrupted after 45 passes/three failures,
with its report retained as `pytest-initial-interrupted.*`. Adapters now explicitly forward
the argument and the existing model integration requires both the certified-fee gate and
new missing-evidence reason. No assertion, policy or risk boundary was weakened. The final
full-suite report is separate. The 29 targeted fee/shadow checks pass; the source freeze
covers 550 application/test/configuration files. Original tracked receipt paths compare
unchanged against the starting designated checkout.

## Final quality results

[Final verification](verification.json): **1,109 pytest passes in 641.26 seconds**, no failures
or skips; Ruff lint/format across 529 files; strict mypy across 526 files; all 21 named frontend
assertions; 29 targeted fee/shadow tests; both actual managed-Chromium procedures. Five
screenshots and fourteen downloads have matching receipt hashes and zero page errors.
Both restored workspaces and the separate controlled experiment reproduce offline. All 550
frozen source/configuration hashes match, and every previously tracked data file remains
unchanged. See `pytest-final.xml`, `pytest-final.log`, `ruff.log`, `format.log`, `mypy.log` and
`frontend.log`. This uses the existing installation and is not a fresh clean-install pass.

## Limits and next review

All controlled market/probability/fee values remain software fixtures, separately labeled
and stored. The actual official schedule remains inaccessible. Its HTTP error cannot prove
coefficients, exceptions, effective intervals or compatibility with the legacy cent rounding.
Unsupported formulas/rounding fail closed. Browser provenance/replay checks prove retention
and consistency, not the truth of an operator's document interpretation or settlement source.

The authentic weather data/model/label and empirical two-family release gates remain open;
Bitcoin receipts and frozen windows stay intact. No profitable strategy, real fill or
real-money order is claimed. External provider verification awaits separately authorized
research credentials. No new clean install or independent final V1 acceptance was attempted.
There is no outstanding human browser procedure for these two executed cases; independent
supervisor review and authentic fee/model/empirical evidence remain required. Stop for review
before another major milestone. No Git mutations were performed.
