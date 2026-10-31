# Paper accounting review correction — October 31, 2026

Implemented in place on `supervisor/20261031-002357` from `d8bbb94`. All Git operations
and independent acceptance belong to the supervisor. Request re-review of this milestone;
**V1, complete-suite acceptance and current browser acceptance remain incomplete.**

Execution now plans the exact marketable slices using the same function as PaperBroker
after risk sizing. The final `execution_net_edge` check compares total expected proceeds,
less exact planned cost, individually rounded taker fees and existing per-contract reserves,
against minimum edge times executable quantity. Full-intention conservative checks and
monetary caps remain. An edge refusal records neither order nor fill, retains the plan and
failed risk check, and leaves cash/fees unchanged. Original decisions remain separate.

Later raw references now use `paper-execution/`, including nested series-fee receipts.
Local replay verifies both capture summaries, directory containment, committed raw
references/hashes, nested fee-receipt identities and later saved books against raw bytes
and receipt clocks. It rejects aliases, wrong hashes, nested fee mismatches, missing or
escaping paths and self-consistent forged later books. This does not certify source truth.

Executed checks in the existing installation:

| Check | Result and evidence |
|---|---|
| Accounting, collector, risk, replay and recovery | **375 passed in 26.59s**; [log](affected.log), [JUnit](affected.xml), [exact command](affected-command.json). Includes the full unit/integration accounting files, tracking/model/fee/workspace checks, execution R4, paper risk, replay, property accounting, recovery proof, shadow and market/book accounting. |
| Retained shadow history | **13 passed, 1 deselected in 5.35s**; [log](history.log), [JUnit](history.xml), [exact command](history-command.json). The previously stalled 130-cycle case is explicitly deselected, not passed. |
| Ruff lint | Pass for the Makefile's `backend` scope; [log](ruff.log). Additional repository-wide lint also passes; [log](ruff-root.log). |
| Ruff format | Pass, **531 backend files**; [log](format.log). An additional repository-wide format check fails on the pre-existing Python fence in `docs/data-platform.md:146`; [exact failure](format-root.log). The unrelated document is unchanged. |
| Strict mypy | Pass, **531 files**; [log](mypy.log). [Quality commands and exit codes](quality-commands.json) retain both the broad exploratory command and canonical gates. |
| Controlled boundary examples | [Frozen examples](edge-examples.json) show two-contract intention → 0.01 executable contracts refusing at actual net edge −0.75 despite preliminary edge 0.23; five → three refusing a 0.230001 minimum and passing equality at 0.23. These are CONTROLLED SYNTHETIC software evidence, never empirical performance. |
| Prior accounting-export compatibility | Both original retained exports pass offline accounting replay: [controlled, five cycles](final-prior-controlled-export.log), [authentic refusal, one cycle](final-prior-authentic-export.log). No receipt or historical result is rewritten. This is accounting consistency, not local raw-reference certification or browser acceptance. |
| Source identity | [563 source/configuration/documentation hashes](source-hashes.json) identify the final source. Original tracked data bytes are unchanged. |

The regressions cover multiple fractional reductions, integer reductions immediately below,
at and above the minimum, and multiple price levels for both YES and NO. The successful
multi-level case checks all three fills and their separately rounded fees. The collector
integration gives initial/later series and book responses different bytes/hashes, resolves
every raw and nested fee reference, compares exact bytes, then performs six tampering
checks with recomputed artifact hashes. It also completes official settlement, restart and
offline account-chain reproduction. Current-source controlled workspace snapshot/restore
and upgrade from workspaces predating paper accounts pass in the same run.

Earlier evidence and receipts are preserved. Those prior test/export results describe their
original checkpoint. New inputs use `shadow-paper-inputs-v2`; v1 inputs also run the corrected
edge gate, while safe older chains retain their original audit shape. A regression replays
the actual retained five-cycle controlled export without adding historical audit fields;
another verifies that v1 cannot bypass the corrected edge gate. Unsafe old fills and
incorrect raw references still refuse rather than being rewritten.

The extra retained-export diagnostic initially exposed an audit-shape incompatibility;
[that failed attempt](prior-controlled-export.log) and [initial results](prior-exports.json)
are preserved. The versioned input change fixes safe-chain compatibility. Final old-export
checks are recorded separately in [final commands/results](final-prior-exports.json).
The `pre-compat-*` logs describe the earlier source, not the final verification in the table.

No browser launch or complete-suite execution is repeated in this correction. The previous
[milestone evidence](../20261031/README.md) retains the exact denied Chromium launch
(`crashpad/util/linux/socket.cc:45`, `setsockopt: Operation not permitted`, SIGTRAP), socket
listener failures, interrupted collector and other per-file deadlines. It also retains the
supported managed-Chromium installation and launch-failure traces. The existing executable
[Playwright harness](../../../frontend/browser/paper.spec.cjs) still needs actual localhost
page interaction, screenshots, downloads and restart inspection in a normally permitted
environment. The full suite, including the deselected long history case, also remains a
supervisor/human acceptance step; targeted success is not a substitute for those gates.

No credentials, real orders, live execution, raised risk limits, fabricated historical
availability, new family, frozen boundary changes, supervisor-control edits or Git mutations.
No fresh clean install or profitability claim. Authentic models/labels, certified effective
fee evidence, empirical two-family validation and final independent release acceptance
remain open. Preserve Bitcoin work; further family selection needs user approval.
