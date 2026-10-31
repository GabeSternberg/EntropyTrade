# Sustained shadow-history milestone — October 30, 2026

Implementation on designated `supervisor/20261030-194338`, starting at `8eab397`.
All Git writes and independent acceptance remain with the supervisor. **V1 is incomplete.**
No credentials, orders, live activation, new family or risk-limit changes were used.

The private workbench selects explicit history and later-outcome partitions of at most
128 inputs each. It preserves receipts and global calendar/model protection, verifies
saved decision replay separately from causal source/book bindings, and carries actual
shadow clocks, sized books and later labels into R2/R4 inputs. Original shadow samples,
probabilities, specs, decisions and fee versions are downloadable. Forward probabilities
stay forward. Protected labels and post-close decisions cannot become modeling evidence.
Missing labels, stale depth and uncertified effective fees remain explicit refusals.

## Verification

The final complete suite passes **1,073 tests in 472.99s**, with zero failures, errors or skips. Ruff lint/format
(518 files), strict mypy (515 files), 21 named frontend assertions, JavaScript syntax and
two-procedure Playwright discovery pass. This reuses the existing environment and is not
a new clean installation. The final aggregate is recorded in [verification.json](verification.json).

The preliminary suite passes 1,071 tests in 476.08s (`pytest.xml`, `pytest.log`). A later
run is deliberately interrupted after 315 passes (`pytest-final.xml`, `pytest-final.log`)
to add the post-close modeling exclusion. Neither preliminary nor interrupted evidence
is relabelled as final. `clock-final.xml` separately records 13 focused passes and one
explicitly deselected sustained case before the final complete run.

`final-source.json` freezes 538 application/test/configuration files. Final comparison
must report no changes. `source-before-clock-correction.json` retains the preceding source
fingerprint. Quality logs ending in `complete-final` describe the final code.

## Controlled software evidence

[Controlled proof](controlled-proof.json) runs 130 actual collector/store cycles with
explicitly CONTROLLED wire data and simulated clocks, reopens the store after cycle 64,
exposes all 130 inputs as partitions of 128 and 2, and verifies all 130 saved decision
replays. The later page contains October 27 targets; selecting it first still freezes
the October 25 global anchor. The earlier page receives matching October 27 binary
receipts without moving original decision/availability clocks. Offline restore preserves
all cycles and immutable snapshot bytes. The original controlled workspace and restore
remain under the repository cache at the paths in the receipt.

[Controlled research](controlled-research-proof.json) runs the ordinary deterministic
worker against the selected 128-sample dataset. Both candidates honestly refuse fitting
and backtesting: one independent event, no matched scalar highs or certified fees.
This is not authentic empirical validation, a model accuracy estimate or profitability.

The complete suite includes an actual localhost/ordinary-worker test with 130 cycles,
partition selection, CSRF/invalid-selection refusals, research, checksummed downloads,
tamper refusal and offline restore. This is HTTP integration evidence, not browser evidence.
Additional tests reject rehashed forged clocks/features/books/source classifications,
exclude positive protected binary labels and post-close modeling rows, and preserve
missing-label, stale/future-depth, uncertified-fee and forward-partition refusals.

## Authentic insufficient-data evidence

[Current authentic proof](authentic-current/authentic-proof.json),
[snapshot](authentic-current/authentic-snapshot.json),
[review](authentic-current/authentic-review.json),
[shadow inputs](authentic-current/authentic-shadow-inputs.json) and
[offline archive](authentic-current/authentic-workspace.zip) retain original October 29
receipts, direct ordinary-worker results and offline restore. All 68 original source
files are unchanged. There are four events on two dates, 24 contracts, 48 decision samples,
20 verified sized books, zero matched scalar highs, zero fitted probabilities and zero
backtest scenarios. Both original shadow replays pass. No new acquisition or performance
is inferred. Earlier authentic preparation bundles remain in this directory with their
original identities rather than being overwritten.

## Outstanding browser acceptance

Supported installation of repository-local Playwright-managed Chromium succeeds.
The one launch attempt fails before page interaction:

`third_party/crashpad/crashpad/util/linux/socket.cc:45` —
`setsockopt: Operation not permitted (1)`, SIGTRAP.

[Exact browser report](browser/playwright-results.json),
[JUnit](browser/playwright-results.xml) and the trace under `browser/playwright-artifacts/`
retain the failure. The first procedure fails at launch and the second does not run.
No screenshots, page interactions, browser downloads or current browser pass are claimed.
The denied attempt is not repeated. The preliminary localhost socket denial is also
recorded in the aggregate; complete pytest uses the normal approval mechanism with an
empty credential-free environment. No sandbox policy or browser flags were changed.

A supervisor/human must run both procedures in
[`shadow-history.spec.cjs`](../../../frontend/browser/shadow-history.spec.cjs) in a permitted
environment, using fresh evidence/workspace paths and the command in the
[operating guide](../../../docs/shadow-history.md). Inspect partition selection, research,
all result tabs, three downloads, offline restore and byte-identical reopened downloads.
Inspect the retained screenshots and hashes and require zero page errors. Discovery and
DOM/HTTP tests cannot satisfy that acceptance step.

External provider checking awaits separate credential authorization. Certified effective
fees, sufficient authentic fitting/outcomes, empirical two-family validation, a clean
release installation and independent final V1 acceptance remain open. Select no family
and start no next major milestone without review.
