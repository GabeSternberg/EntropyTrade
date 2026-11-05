# Prospective-evaluation acceptance completion — November 5, 2026

Scheduled autonomous session on `claude/vibrant-bohr-l2suow` from main `55b2bea`.
This bundle executes the browser, real-listener and complete-suite gates left
**outstanding** in the [October 31 evidence](../20261031/README.md), which could not run
there because socket creation and the Chromium launch were denied. This runtime permits
loopback sockets. No credentials, real orders, execution activation, risk-limit changes,
new market family or rewritten receipts are included. **V1 remains incomplete.**

## Defect found and corrected

The first browser attempt ([log](browser-attempt-1.log), [receipt](browser-attempt-1/controlled/receipt.json),
[Playwright JSON](browser-attempt-1/playwright-results.json)) passed real page inspection,
both JSON/CSV downloads, listener restart and byte-identical restarted downloads, then failed
at offline snapshot: `Recovery refused: unable to open database file`.

Cause: `api/recovery.py` (three readers) and `api/recovery_proof.py` (two readers) passed
`file:///…?mode=ro` to `sqlite3.connect` **without `uri=True`**. Python then treats the URI as
a literal filename unless SQLite was compiled with `SQLITE_USE_URI=1`. Earlier environments'
SQLite builds apparently enabled that default; this runtime's uv-managed CPython 3.13.18 with
SQLite 3.53.1 does not, so every offline snapshot/restore refused. The existing
`test_prospective_offline.py` reproduced the failure here before the fix. Other read-only
readers (`agents/evidence.py`, `storage/recorder.py`, `data/recording.py`) already passed
`uri=True`.

Fix (commit `f2f16dc`): pass `uri=True` to all five calls. New
`backend/tests/architecture/test_sqlite_uri.py` statically requires `uri=True` on every
URI-style `sqlite3.connect` in `entropytrade` (fails on the pre-fix tree, verified) and checks
a read-only WAL open still refuses writes. No assertion, marker or policy was relaxed.

## Browser acceptance (both procedures pass)

Command: the fresh-path command in [the workflow](../../../docs/prospective-evaluation.md),
evidence `browser/`, workspaces `data/cache/prospective-browser-20261105b-*`.
[Log](browser.log), [Playwright JSON](browser/playwright-results.json) (`expected: 2,
unexpected: 0, flaky: 0`), [JUnit](browser/playwright-results.xml) and traces are retained.

| Procedure | Receipt | Result |
|---|---|---|
| CONTROLLED synthetic diagnostics | [receipt](browser/controlled/receipt.json) | passed; 3 screenshots, 6 downloads (JSON/CSV identical after restart and after offline restore), offline CLI replay identical, 0 page errors |
| Authentic insufficiency | [receipt](browser/authentic/receipt.json) | passed; 3 screenshots, 6 downloads identical across restart/restore, 24 refused, no metrics, 0 page errors |

Screenshots were inspected: the controlled page shows matched rows, revision counts and
synthetic lineage; the authentic page shows `missing_or_ambiguous_prediction` refusals with
`data_kind: real`, original Open-Meteo/Kalshi source clocks and null predictions. The
"CONTROLLED monitor setup" recent-run title in both workspaces is the shared test scaffolding job
(`test_tracking.py`), not a label on authentic data.

**Browser build deviation (disclosed).** The pinned `@playwright/test` 1.56.1 expects managed
Chromium build 1194; `npm run install:chromium` failed here (`Download failure, code=1`, network
policy). The runtime's preinstalled Playwright-managed Chromium build 1243 (Chrome for Testing
153.0.8010.12) was exposed at the expected ignored path
`frontend/browser/.browsers/chromium-1194/chrome-linux/chrome` via a local symlink. Receipts
record the actual `browser.version()` 153.0.8010.12. No personal profile, channel, CDP endpoint,
route interception or security flag was used. Acceptance under the exact pinned build 1194 is
not claimed.

## Quality checks

- Ruff lint/format: [lint](ruff-lint.log), [format](ruff-format.log) (557 files).
- Strict mypy: [log](mypy.log), no issues in 557 source files.
- Frontend DOM tests: [log](frontend.log), 24/24 (presentation doubles, not browser tests).
- Original receipt/Bitcoin boundary hashes: [safety receipt](safety-receipt.json), all 73 unchanged.
- Complete pytest suite: see the section below.

FULL_SUITE_PLACEHOLDER

## Retention

Workspaces and snapshot archives remain under ignored `data/cache` (container-local; not
promised in a clean checkout). The tracked receipts, downloads, screenshots and traces are
independently inspectable. The failed attempt's unpacked `.playwright-artifacts-0` trace
intermediates (4.1 MB, duplicating its retained `trace.zip`) were removed before staging.

## Remaining gates (unchanged by this run)

Sufficient authentic independent history and validation, certified effective fees,
separately authorized provider verification, user-approved two-family evidence, multi-day
authentic operation and independent V1 release review remain open.
