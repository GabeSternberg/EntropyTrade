# Existing PR reconciliation and remaining V1 work

November 6, 2026. This is consolidation of the existing backlog, with no new feature phase.
The live completion/resume record is [issue #25](https://github.com/GabeSternberg/EntropyTrade/issues/25).
It records each final reviewed head, CI outcome, merge commit and exact next action.

Dependency order:

- A: #1 → #2.
- B: #4 → #8, reconciled with tested A contents first.
- C: #5 → #7 → #9 → #10 → #11 → #12 → #13 → #14 → #15 → #16 → #17 → #18 →
  #19 → #20 → #22 → #23 → #24, reconciled with tested A/B contents first.

Original commits and empirical evidence remain recoverable. Integration uses merge commits,
without force pushes, rebasing or squashing. Each child is re-evaluated after its parent:
the base, effective diff, reviews, checked head and resulting tree must still agree.
The existing offline CI workflow from #2 was promoted unchanged to #1 to check the first parent.
Historical test logs are preserved as historical results; they do not certify a changed head.

Fresh review fixes:

- #4: resolve dated revisions before unclocked observations so input order cannot erase a
  final result; validate every supplied update clock; compare effective volume across legacy
  and fixed-point catalog fields. Permutation, malformed-clock and numeric-format regressions
  cover the failures. The screen remains descriptive and never selects a family.
- #17: report non-list portal `results` as malformed diagnostics instead of crashing or
  describing missing stations. The label parser, refusal text, frozen audits and original
  receipt bytes remain unchanged.
- #18: pin the verified authentic weather capture used by the station-diagnostic test. The
  retained workspace also contains an interrupted capture without a manifest; selecting the
  first filesystem entry caused an order-dependent CI failure. Existing assertions remain.
- #22: an already exceeded snapshot budget remains binding when that dimension's measured
  growth is flat or negative. This changes no budget, calendar, evidence or collection cadence.

## Remaining V1 backlog

Merging code does not satisfy these gates:

| Gate | Remaining action and evidence |
|---|---|
| Authentic history and forward validation | Accrue enough independent station/day events within the fixed fit/calibration/validation calendar; retain source-matched official labels, timely forecast vintages, actual contracts, sized books and effective fee evidence. Repeated polls are not independent events. Do not touch protected holdout data or backdate availability. |
| Certified effective fees | [Issue #6](https://github.com/GabeSternberg/EntropyTrade/issues/6): automated official-PDF acquisition still returns HTTP 429. Manual import retains operator provenance at the import clock, but certification requires separate human review of actual official bytes, scope, coefficients and effective dates. |
| Authorized provider verification | Use a separately authorized research provider and dedicated research credential; retain bounded inputs, outputs, costs and failures. Exchange credentials are separate. Offline or synthetic tests do not establish provider acceptance. |
| Approved second major family | The screen/discovery tools and retained comparison support a written user choice. Compare accessible point-in-time history, settlement semantics, modeling feasibility, execution costs and realistic validation before any implementation. No family has been selected by this reconciliation. |
| Sustained authentic paper/shadow operation | Preserve and continue the canonical snapshot onto main, verify restart/recovery and disabled submissions, then observe multi-day operation. Bounded verification windows and successful software tests do not establish this gate. |
| Evidence storage runway | [Issue #21](https://github.com/GabeSternberg/EntropyTrade/issues/21): measured growth remains shorter than the frozen validation calendar. Durable storage, dataset-layout changes or budget changes require the pending decision. Existing evidence is not deleted to create room. Seven-day workflow artifacts are not durable archival storage. |
| Public acquisition/browser acceptance | Re-run the weather-label and fresh-public-acquisition procedures where the relevant public hosts and supported browser are accessible; retain actual downloads, screenshots, clocks and failures. Preserve the disclosed historical Chromium-build deviation. [Issue #3](https://github.com/GabeSternberg/EntropyTrade/issues/3) describes the cloud egress restriction; GitHub runners provide a collection workaround. |
| Independent final V1 acceptance | Review the complete release evidence against the existing acceptance matrix after the empirical, provider, fee, family and operation gates are met. Code consolidation does not declare V1 complete or approve trading. |

## Collector continuity during reconciliation

The forward collector was temporarily disabled through the Actions API while intermediate
versions were integrated; offline CI stayed enabled. The verified source at the start of
reconciliation was run **42261256002**, on #24's original head, continuing **42243733103**.
It retained 61 cycles, zero acquisition failures in the new cycle, zero fills, and submissions
disabled. Its workspace checksum was
`sha256:94d7707a1ae245f04952968e082fee768a4bbd177f65ba72ff1cca5efaa03399`.

After the complete tested stack reaches main, re-enable workflow **408759938** and seed main
with `continue_from_run` set to the newest verified canonical run, `seconds=540`, `fresh=false`.
Verify the restored checksum and lineage, the new main snapshot and disabled submissions.
Issue #25 records whether this has completed and the resulting run ID. Do not dispatch an
older branch, create an empty replacement chain or assume a scheduled run migrated evidence.

No production submission, real-money order, risk-limit increase, fee certification or
credential use is authorized by this reconciliation.
