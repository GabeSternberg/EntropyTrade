# Browser regression sweep and CI — November 5, 2026

Scheduled autonomous session on `claude/vibrant-bohr-b1kuuh`, stacked on PR #1
(`claude/vibrant-bohr-l2suow`, read-only SQLite URI fix), because offline restore in these
procedures needs that fix. Every procedure in `frontend/browser/` ran against the current
tree through real localhost listeners and managed Chromium. No credentials, real orders,
execution activation, risk-limit changes, new market family or rewritten receipts are
included. **V1 remains incomplete.**

## Final result (committed tree)

Runner: [`run_browser.sh`](#runner) with new absolute workspace/evidence paths per spec,
`PLAYWRIGHT_BROWSERS_PATH` unset so the config's isolated `.browsers/` path is used.
Chromium: preinstalled Playwright build 1243 (Chrome for Testing 153.0.8010.12) exposed at the
pinned build-1194 path by a git-ignored symlink, as in the
[PR #1 evidence](../../prospective-evaluation-review/20261105/README.md). Every receipt records
`browser.version()` 153.0.8010.12. A pass under exact build 1194 is not claimed.

| Spec | Bundle | Procedures | Result |
|---|---|---|---|
| `paper` | `final/paper` | controlled, authentic | **2 passed**, 0 page errors |
| `alerts` | `final/alerts` | 1 | **passed** (4 screenshots, 6 downloads) |
| `fees` | `final/fees` | controlled, authentic | **2 passed** |
| `provider` | `final/provider` | 1 (controlled provider HTTP) | **passed** (8 screenshots, 14 downloads) |
| `weather-history` | `final/weather-history` | 1 | **passed** |
| `forward-validation` | `final/forward-validation` | controlled, authentic | **2 passed** |
| `label-partitions` | `final-partitions/label-partitions` | 1 (130 controlled batches) | **passed** after the fix below |
| `shadow-history` | `final/shadow-history` | controlled, authentic, cohort | **3 passed** |
| `recovery` | `final-recovery/recovery` | 1 | **passed** after harness path fix (5 screenshots, 11 downloads) |
| `bitcoin-history` | `final/bitcoin-history` | empty, controlled | **2 passed** (retained-receipt case not selected) |
| `shadow` | `final/shadow` | 1 | **passed**, lifecycle only: all public acquisition failed (see below) |
| `prospective` | `final/prospective` | controlled, authentic | **2 passed** |
| `weather-labels` | `final/weather-labels` | 1 (authentic acquisition) | **failed: public source blocked** |
| `workbench` | `final/workbench` | 4 workflows in one test | **3 of 4 passed**; workflow 3 (fresh public acquisition) failed: sources blocked |

That is 19 passing tests across 12 spec files, plus 3 of 4 workbench workflows. Two tests fail
only because they need public network. All receipts report zero page errors.

### Network-dependent failures (environmental, not claimed as passes)

This runtime's egress proxy refuses public data hosts (`curl https://weather.com/...` →
`CONNECT tunnel failed, response 403`). The application behaved correctly in both cases: it
retained empty receipts with `ConnectError`/`GatewayError`, refused the labels/observations
and never backdated or invented data. The procedures assert successful authentic acquisition,
so they fail here. They need a runtime with public egress to Kalshi, Open-Meteo, NWS and
weather.com. `shadow.spec.cjs` passes because it explicitly treats acquisition as possibly
failing. Its receipt records nine acquisition failures, so it is not evidence of ingestion.

## Defects found and fixed

1. **Stale label-partition render (application).** First run2 failure: `locator.screenshot:
   Element is not attached to the DOM`. `weatherLabels()` is called from both the refresh
   button and the partition `change` handler. Overlapping calls could resolve out of order,
   and the older call would render one partition's requests while another was selected.
   Fix (`frontend/src/app.js`): a sequence number lets only the newest call render.
   `#weather-labels` now exposes `aria-busy` and `data-partition`. New DOM regression in
   `frontend/tests/acquisition.test.cjs` reproduces the defect against the previous `app.js`:
   rows for `00000001` are shown while `00000000` is selected. The spec waits for the settled
   render before asserting or taking screenshots.
2. **Run-to-run path collisions (harness).** Snapshot archives and imported-input copies were
   named `data/cache/<workspace basename>.zip`, and `recovery.spec.cjs` used a fixed
   `data/recovery/local-acceptance.zip`. That path was also *not git-ignored*. A second run
   with new workspace paths hit the earlier archive, and recovery correctly refused it
   (`snapshot requires a new archive outside the workspace` / `Acceptance paths must be new`).
   All seven specs now derive these paths from the unique workspace path.
3. **Boundary-outage screenshot (harness).** It captured the newest request rather than the
   HTTP 503 outage request (the same as the October 31 accepted image). It now targets the
   section containing the outage. The new image shows `0 verified scalar labels · 1 refused events`.

## Attempt record (all retained as logs)

| Run | What happened |
|---|---|
| `run1` | All 13 failed at launch. The environment's `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` overrode the config default. Runner misconfiguration, not an application result. |
| `run2` | 11/13 spec files passed. The `weather-labels` (network) and `label-partitions` (defect 1) specs failed, and `workbench` workflow 3 (network) failed. `app.js` was edited at about 21:37Z, during this run, so specs started after that served the fixed file. |
| `run3` | Runner had not created the workspace parent directory, so phase-file `ENOENT` occurred. Runner fixed. |
| `run4` | `label-partitions` passed. `forward-validation` was refused by the archive collision (defect 2). |
| `final` | Full 14-file sweep at `96ac0d2`. Only `recovery` (fixed-path collision with run2) and the two network tests failed. |
| `final-recovery` | `recovery` passed with the unique archive path. |
| `final-partitions` | `label-partitions` passed with the corrected outage screenshot selector. |

## Continuous integration

New `.github/workflows/ci.yml` runs on GitHub-hosted `ubuntu-24.04` with no secrets: locked
`uv sync` (Python 3.13, uv 0.11.32), Ruff lint/format, strict mypy, the frontend DOM tests and
the complete pytest suite. Run 1 failed because `UV_FROZEN` conflicts with `--locked`, which was
then fixed. [Run 3](https://github.com/GabeSternberg/EntropyTrade/actions/runs/42116073148) at
`96ac0d2` **passed: 1,320 pytest cases in 693.83s**, mypy clean, 25 frontend tests. Browser and
public-source acceptance are deliberately not part of CI.

## Local checks

Ruff lint/format and strict mypy (557 files) pass. `node --test frontend/tests/acquisition.test.cjs`
reports 25 passed, including the new regression.

## Retention

The committed bundle holds logs, receipts, Playwright JSON/JUnit and JSON/CSV downloads under
512 KB, plus one screenshot. [`MANIFEST.sha256`](MANIFEST.sha256) lists the SHA-256 of **every**
file produced, 1,440 files in total. Traces, screenshots, snapshot archives, copied workspaces and
models (about 850 MB in total) stay untracked in this container (ignored by `../.gitignore`, along with other un-committed per-run outputs) and will not survive it.
Receipts also record per-file screenshot/download hashes. Workspaces live in
`data/cache/browser-regression-20261105-*`.

### Runner

```bash
cd frontend/browser && unset PLAYWRIGHT_BROWSERS_PATH
mkdir -p "$WSROOT"
ENTROPYTRADE_BROWSER_EVIDENCE=$EVROOT/$tag/$name ENTROPYTRADE_BROWSER_WORKSPACE=$WSROOT/$name \
ENTROPYTRADE_BROWSER_PORT=$port ENTROPYTRADE_BROWSER_PYTHON=$REPO/.venv/bin/python \
  npx playwright test "$name.spec.cjs"
```
