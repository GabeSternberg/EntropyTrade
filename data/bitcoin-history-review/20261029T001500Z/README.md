# Real Bitcoin reconciliation and history blocker — October 28 ET / October 29 UTC

**Intermediate acceptance evidence. Second-family empirical acceptance and V1 remain
incomplete.** Work started clean on `supervisor/20261028-201233`, HEAD `97074a3`.
No Git mutation, credential access, continuous collection, paper/shadow activation or
order submission was performed. All Git writes remain the supervisor's responsibility.

## What executed

| Requirement | Executed evidence | Result |
| --- | --- | --- |
| Official results for retained contracts | [Original network receipts](real-reconciliation/history/outcomes/receipts.json), [CLI output](real-reconciliation.log) | Four exact public GETs returned HTTP 200, matching finalized NO results, binary zero payouts and settlement timestamps. Original receipt clocks are retained at 2026-10-29 00:13:36 UTC. |
| Inventory of retained source history | [All eight captures](retained-inventory.json), [replay script](replay_real.py), [immutable snapshot](real-all-captures/history/manifest.json) | Three captures have recognized samples; five have none. One is a repeated poll. Deduplication leaves four events across three target dates, with earliest original decisions preserved. |
| Point-in-time labels/features and fixed boundaries | [Independent verifier](verify_evidence.py), [passing result](verification.json), [log](verification-final.log) | Checksums, earliest decisions, outcome receipt clocks after settlement, event/close identity, closed execution gates, fit cutoff 2026-12-24 and holdout start 2027-01-23 verified. No receipt is backdated. |
| Deterministic real-input evaluation | Two independent [first](deterministic-replay-1/experiments/) / [second](deterministic-replay-2/experiments/) replays of identical dataset/research/config | Same experiment identity and serialized results as the original run: two INSUFFICIENT_DATA candidates, no probabilities, scores, execution scenarios or P&L. This is deterministic refusal, not fitted empirical evaluation. |
| Browser-visible reasons and durable downloads | [Browser receipt](browser/retained-history-browser-receipt.json), [Playwright results](browser/playwright-results.json), [log](browser.log), screenshots/trace/downloads in [browser](browser/) | One actual Playwright-managed Chromium test passed in 19.1 seconds. Real localhost server and unchanged subprocess worker; form submission, all three tabs, four screenshots, four checksummed downloads, stop/restart and identical reopened downloads. Zero page errors. |
| Current source access | [One-shot script](probe_sources.py), [capture](source-feasibility.json), [raw manifest](current-public-bitcoin/manifest.json) | Three HTTP 200 receipts from public Kalshi/Coinbase; 318 listed contracts and one spot observation. Three eligible forward samples on October 28–30, all still unsettled at capture. This separate probe is not part of the four-label browser/evaluation snapshot. |

Browser setup copied verified real source/outcome receipts into a **new** workspace using
[bitcoin_history_retained.py](../../../backend/tests/integration/bitcoin_history_retained.py).
Imported setup jobs explicitly say receipt replay, not new acquisition. No controlled wire
responses, simulated clocks, intercepted requests or replacement workers were used in
this browser case. The frozen workspace, downloaded JSON/text and Chromium trace remain
under `browser/`. Visual inspection of `retained-history-probabilities.png` confirmed
readable counts, dates and empty probabilities. The older empty/controlled browser checks
remain in their original bundle; the four October 26 procedures were not rerun here.

## Concrete blocker and user decision

The evaluated real snapshot has **4/40 fitting events on 3/20 dates**: a shortage of
**36 events and 17 dates**. All four finalized targets are NO; both fitting classes are
required. There are **0/20 validation events on 0/10 dates**, with zero validation labels.
The fresh source probe adds three forward covariates with pending targets; it supplies
no additional fitting labels or validation observations.

Public access worked in this session. The blocker is **elapsed, independently retained
point-in-time history**, not a current missing credential or failed endpoint. The existing
path is technically feasible for forward accumulation: capture original active-market
rules plus Coinbase observations on separate dates, then reconcile official results before
the fixed fit cutoff. The result class mix, domain overlap and later endpoint availability
are not guaranteed. No sustained collector was activated or certified here.

Validation is fixed to **2026-12-24 inclusive through 2027-01-23 exclusive**. As of this
October 28 ET run those dates have not occurred. Even ideal timely collection cannot
provide ten independent validation dates before **2027-01-02**. That is a calendar lower
bound, not a completion promise; adequate events, both classes, in-domain covariates and
finalized receipts are also required. Protected dates must not be moved to obtain a pass.

Kalshi's [historical tier](https://docs.kalshi.com/getting_started/historical_data) and
[exact archived-market endpoint](https://docs.kalshi.com/api-reference/historical/get-historical-market)
can provide later outcomes. They do not supply our original Coinbase/active-rule receipt
clocks. Downloading historical prices/results today cannot turn them into earlier receipts
in this adapter. No sufficient certified archive was found among retained inputs; no paid
archive, credentials or historical availability claim was introduced. A different archive
or partition would require a separately reviewed provenance design and must preserve the
existing protected partition.

**Decision needed:** authorize an operating period of original forward capture and result
reconciliation through the frozen validation window, or keep empirical second-family
acceptance blocked while a separately reviewed archive is supplied. Do not claim the
gate is closed from this insufficiency result. Continuous paper/shadow and final V1
acceptance remain deferred. There is no outstanding human browser interaction step for
the scoped retained-real-receipt procedure; supervisor review and clean-checkout verification
remain outstanding.

## Checks and reproduction

Current logs: [full make check](make-check.log), [targeted Bitcoin tests](bitcoin-tests.log),
[strict mypy](mypy.log), [12 frontend checks](frontend.log),
[managed Chromium installation](chromium-install.log). Final gate counts are also recorded
in `validation.json`. These checks run on this working checkout, not a clean install.
`make check` passed Ruff lint/format, strict mypy across 483 files and **754 pytest tests
in 269.06 seconds**, without skips. All 19 targeted Bitcoin tests and all 12 frontend
checks passed. The independently replayed real experiment identity is
`sha256:fb7f2b47d6773396126a5288b93eb71e0918527997a6cf300942f81693833609`.

The ordinary workspace denies socket creation with `PermissionError: [Errno 1] Operation
not permitted`; that initial capability probe was executed once. Network, asyncio, listener
and Chromium commands ran only after the supported approval mechanism permitted their
required socket operations. No sandbox bypass or repeated denied browser launch occurred.

Two verifier/setup mistakes are preserved: `source-feasibility.log` contains an initial
wrong configuration import before any network request; `verification.log` contains a
tuple-versus-JSON-array comparison failure. The corrected scripts executed successfully;
saved deterministic JSON was byte-identical even on the first comparison attempt. Neither
failure required changing application semantics, thresholds or tests.

From a listener/browser-capable environment, run the normal `make check` and:

```bash
node frontend/tests/acquisition.test.cjs
.venv/bin/python data/bitcoin-history-review/20261029T001500Z/verify_evidence.py
```

For a new browser run, follow [the harness guide](../../../frontend/browser/README.md),
set `ENTROPYTRADE_BROWSER_RETAINED` to the absolute `real-all-captures/history` path,
select `--grep 'REAL retained receipts'`, and use new absolute workspace/evidence paths.
Replay/capture scripts refuse existing acquisition outputs. Old artifacts are not rewritten.
`source.json` and `SHA256SUMS` bind the final source and retained evidence.
