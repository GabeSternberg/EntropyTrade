# Point-in-time fee evidence

The continuous shadow worker and real research/experiment worker freeze server-managed fee
versions into each cycle/job. The same `FeePolicy`, decimal fee calculator, strategy interpreter
and risk engine are used. There is no order submission transport or browser fee editor.
Fee evidence alone cannot supply missing models, rules, depth, labels or empirical validation.

Each content-addressed version retains exact base64 source bytes and their SHA-256, URL,
HTTP status, media type and original receipt clock. A reviewed version also retains exact
series identifiers, coefficient/multiplier/maker assumptions, citations/passages, the engine's
rounding rule and a bounded half-open effective interval. Publication uses an atomic link
that cannot overwrite a prior version. Reads verify source and version hashes. Interrupted
staging files are ignored. Versions live under `workspace/runs/fee-evidence/` and participate
in verified offline workspace snapshot/restore. A corrupt version fails the worker/download;
it does not fall back to an older or guessed fee.

Selection requires exactly one applicable version known by the decision clock. Availability
is the latest source receipt **and local review** clock. Reviewing an old document today
cannot backdate its availability. Missing, conflicting, late, wrong-series, expired or
uncertified evidence refuses. Controlled versions only apply to synthetic data. Series
metadata alone cannot certify a coefficient or interval; conflicting captured series fee
fields also refuse a shadow decision. Reviewed versions with overlapping intervals refuse for overlapping decision clocks.
Immutable receipts are never deleted to make a replay pass. The catalog never chooses
the newest version as an implicit override.

Local administration uses the same exclusive workspace lease as the server. Stop the server
first. Commands accept only workspaces under this repository's `data/cache/`. Capture uses
fixed official URLs, bounded unauthenticated GETs, no redirects, no environment proxy or
credential access:

```bash
.venv/bin/python -m entropytrade.execution.fee_admin \
  --workspace "$PWD/data/cache/workbench" --capture schedule
.venv/bin/python -m entropytrade.execution.fee_admin \
  --workspace "$PWD/data/cache/workbench" --capture rounding
.venv/bin/python -m entropytrade.execution.fee_admin \
  --workspace "$PWD/data/cache/workbench" --list
```

For unattended operation, `--capture-due schedule rounding` captures each document only
when no successful copy was retained in the last 24 hours (or no failed attempt in the last
3 hours), reports per-document status/bytes/SHA-256/`is_pdf` as JSON, and never raises on a
network error (nothing is stored when no bytes arrive). The
[forward-collection workflow](forward-operator.md) runs it on GitHub-hosted runners, which
have the public egress cloud sessions lack, so official bytes accumulate in the chained
workspace for a later operator review. On 2026-11-06 (run `42136976908`) the schedule PDF
URL returned HTTP 429 with an HTML body from the runner as well, so no authentic PDF exists yet.

### Operator manual import of the official schedule (issue #6)

Automated clients, including GitHub-hosted runners, receive HTTP 429 for the official
schedule PDF. An operator may download it in an ordinary browser from
`https://kalshi.com/docs/kalshi-fee-schedule.pdf` and import the exact bytes (stop the
server first; the same workspace lease applies):

```bash
.venv/bin/python -m entropytrade.execution.fee_admin \
  --workspace "$PWD/data/cache/workbench" \
  --import-schedule /absolute/path/kalshi-fee-schedule.pdf \
  --downloaded-at 2026-11-06T14:30:00+00:00 \
  --note "Downloaded in Firefox from the official kalshi.com URL"
```

- Only a regular, non-symlink file of at most 8 MiB starting with `%PDF-` is accepted.
- The receipt carries explicit `manual_import` provenance (operator-attested download
  time, original filename and note). The system did not observe that download: its
  `status: 200` records the operator's attested successful download, and the website shows
  **OPERATOR MANUAL IMPORT (no system-observed HTTP)** instead of an HTTP status.
- `received_at`, and therefore availability, is the **local import clock**. The attested
  download time is informational and must not be later than the import; a timezone is required.
  An import can never make a fee known earlier than the moment it entered the workspace.
- The imported version is unreviewed and never selected. Certification remains the separate
  `--review` attestation, whose review clock again bounds availability.
- Manual imports do not count toward the unattended `--capture-due` cadence, so automated
  capture keeps seeking independent system-observed official bytes.
- Automated receipts serialize exactly as before; every previously retained fee version keeps
  its content hash (regression: `test_previously_retained_versions_keep_their_exact_hashes`).

The agent cannot perform the browser download or the review; both remain human actions.

A capture is always **unreviewed**, including HTTP 200. HTTP failure bytes are evidence of
failure, never a fee certificate. The current authentic official PDF attempt returned HTTP
429; the [receipt and original bytes](../data/fee-evidence-review/20261030/README.md) are retained.
No authentic schedule was certified in this milestone. The vendored rounding reference and
the legacy cent-rounded calculator may differ: do not assert compatibility without examining
the applicable official document. Unsupported rounding/formulas explicitly refuse review;
this milestone does not change the fee engine to approximate them.

If official documents become accessible, an operator must independently review their formula,
rounding, exceptions, exact series scope, multiplier and effective interval. The local command
`--review /absolute/path/review.json` records that operator attestation; it is not automatic
PDF extraction or an LLM's judgment. It accepts exactly these fields:

- `source_versions`: retained authentic version IDs, including the official fee schedule.
- `series`: exact series tickers, without prefix matching or family-wide inference.
- `schedule`: the existing `FeeSchedule` fields, with exact decimal strings.
- `effective_from`, `effective_to`: UTC interval supported by the cited documents.
- `rounding`: `cent_ceiling_per_fill`, only when supported by the actual document.
- `review`: the operator's explanation of applicability and exceptions.
- `citations`: source SHA-256, document `locator`, verbatim `passage`, and `supports` values
  covering `coefficient`, `rounding`, `series`, `multiplier` and `interval`.

The command assigns the review and policy availability clocks. Imported certification,
review clocks, arbitrary endpoints and controlled sources cannot enter this command. There
is deliberately no browser endpoint to install/review a version. A local operator attestation
is a trust boundary; checksums prove retention, not the truth of that interpretation.

The website shows source HTTP status/clocks, series/interval, review/citations, coefficient
and rounding details, decision selection/refusal, and version/original-byte downloads.
Research jobs download **Experiment fee evidence**, frozen for that job. A later catalog
change cannot alter a completed review. Shadow exports freeze per-decision selections;
`decision-inputs.json` includes full versions, captured series metadata and held reservations.
Existing fee-inclusive monetary caps apply across restarts. No fills or profits are claimed.

Real experiments persist full fee versions in the experiment configuration and portable
`replay-inputs.json`. The replay uses the applicable schedule separately at decision and
simulated execution clocks, including a fee transition during latency. Conservative
scenarios retain the existing explicit coefficient stress. Protected sample shells retain
only identity/clocks; their features, labels, books and prediction records are excluded from
portable inputs. Frozen model outputs are data; offline replay never loads executable models,
requests a provider or polls a source:

```bash
.venv/bin/python -m entropytrade.tracking.replay /path/to/shadow/cycle
.venv/bin/python -m entropytrade.experiments.fee_replay /path/to/experiment
```

These commands check artifact hashes and compare deterministic decisions/results. They
certify software repeatability, not source truth, settlement authority or profitability.
Legacy explicit fee-policy callers remain compatible. The private website and continuous
worker use the immutable evidence path; legacy synthetic demos remain visibly synthetic.

Run actual browser acceptance with the existing managed Chromium installation:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium
env -i PATH=/usr/bin:/bin TZ=UTC \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/fee-evidence-review/NEW/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/fee-browser-NEW" \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs --grep 'point-in-time fees'
```

Use fresh paths and an environment permitting loopback listeners and Chromium. The two
procedures separate CONTROLLED synthetic eligible-intention/risk fixtures from authentic
original receipt replay with absent models and uncertified fees. Both inspect the page,
download and checksum versions/original bytes/shadow exports, restart the actual server,
and compare reopened downloads. The authentic flow also submits ordinary research and
downloads its frozen fee evidence and insufficient-data review. Setup is test-only;
production has no fixture switch. Managed Chromium is used with unchanged launch policy.
See [executed evidence and limitations](../data/fee-evidence-review/20261030/README.md).
