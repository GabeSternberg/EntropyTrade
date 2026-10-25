# Private research workbench

Run from a dependency-equipped checkout (Python 3.12+):

```bash
uv sync --locked
uv run entropytrade-web
# Open http://127.0.0.1:43128
# Alternative: uv run python -m entropytrade.api.server --port 43128
```

This is a single-user loopback website, not an authenticated network service. The server
always binds `127.0.0.1`; do not expose it through port forwarding or a public reverse proxy.
It uses buildless local assets and a standard-library HTTP server rather than adding a
second application framework. The research, modeling, experiments and SQLite Registry
remain the existing R2–R4 engines. No trading controls or credential access were added.

Describe an idea, choose a family and data mode, and start a run. The durable queue records
progress and saves a review with typed hypotheses/specifications, independent research
gates, candidate rejections, forecast metrics, simulated execution scenarios, permitted
validation probabilities and artifact hashes. The Evidence & lineage tab exposes exact
public contract rules, source receipts and acquisition failures when a public capture was
requested. Review JSON and text reports can be downloaded without exposing arbitrary files.
All dynamic text uses DOM text nodes, including user ideas and source rule text.
All result tabs prominently show public acquisition completeness, HTTP receipt counts
(including successful responses separately), listed contracts, observations and every
clocked acquisition failure. Text downloads include the same summary and settlement limits.
An empty response is not successful ingestion, and a completed review can contain an
incomplete capture. Forward ingestion never establishes empirical model performance.

## Modes and formulation

| Mode | Data | Formulation | Expected capability |
| --- | --- | --- | --- |
| Recorded / weather | Committed historical R2 evidence | Local templates | Reviewable real insufficiency: no eligible historical forecast/scalar labels |
| Public / weather | Actual current Philadelphia/Chicago listings + Open-Meteo/NWS receipts | Local templates | Forward point-in-time forecast proxies and rule lineage; no historical evaluation |
| Public / Bitcoin | Actual KXBTC listings + Coinbase BTC-USD ticker | Local templates | Distinct family adapter with receipt-clock spot/strike covariates; no historical evaluation |
| Synthetic / weather | Generated 240-date R4 fixture | Explicit fixed mock proposals | Existing fitting, calibration, validation and replay proof; never empirical evidence |

Local formulation uses no LLM. Supported signal words are forecast/temperature/weather,
revision, disagreement/dispersion, bias and Bitcoin/BTC/spot. Literal comparisons such as
`revision_f >= 1.25 and hours_to_close < 8` become exact Decimal conjunctions in a typed
specification. The comparison grammar consumes the complete input:
`[Test|Research] feature OP decimal [and feature OP decimal ...]`, where `OP` is one of
`>`, `>=`, `<`, `<=`, `==`. The introductory verb is optional; case and whitespace may vary.
XOR, unless, OR, negation, symbolic/implicit connectors, grouping and other surrounding
prose are rejected, rather than extracted comparisons being silently joined with AND.
Feature names and versions must exist in the selected adapter. Bare prose
selects a modeling signal and does not invent a numerical feature threshold. The complete
idea is saved; arbitrary prose is not fully interpreted. Unsupported signals, disjunction,
negation, malformed comparisons and out-of-scope execution semantics remain non-executable
proposals with reasons. Always inspect the resulting spec before interpreting a result.
Numeric tokens must be complete plain decimals with at most six fractional digits.
Excess precision (`1.2345678`), scientific notation (`1.2e3`, `1.2e-3`), thousands
separators (`1,000`) and suffixes are rejected as whole tokens; no numeric prefix becomes
an executable threshold. Supported values retain their exact Decimal representation.

The two local proposals compare registered weather regression and forecast-error model
families, using their existing feature sets. This is not feature ablation or a causal test.
Entry templates are informational YES, model probability above 0.55, 0.03 minimum net edge,
one fixed contract, fill-or-kill and hold to official settlement. These are declared research
defaults, not conclusions inferred from arbitrary prose. They cannot change risk limits.
Bitcoin has an explicit `forward_only` provider which refuses fitting/predictions until
independent temporal history and matched outcomes exist. Synthetic mode keeps the original
fixed R4 candidates and negative control; it does not interpret the submitted idea.

Provider-backed research remains available through the existing separately configured CLI;
the website deliberately offers no provider activation, keys or credential discovery.

## Public evidence and the second family

Acquisition uses the existing read-only Kalshi SDK gateway and forecast archive. Its
transport permits only HTTPS GETs to fixed market/source paths, rejects authentication
headers, follows no redirects and bounds each transport to 20 requests, 2 MB per response
and 12 MB total decoded bytes. Capture has a 120-second overall deadline. Partial acquisition
records failures and marks the universe incomplete; it never substitutes fixtures.
See the primary [Kalshi market endpoint](https://docs.kalshi.com/api-reference/market/get-markets)
and [Coinbase ticker definition](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-ticker).

Bitcoin demonstrates the same `AdapterRegistry` → `ContractSample` → protected research
projection → `PredictionProvider` → experiment-engine path as weather. It records actual
rule text rather than assuming a weather rule or strike resolves from the spot quote.
CF Benchmarks mentions are retained separately as `authority_mentions`, with their exact
text and original rule field. They are lexical provenance, including negated and ambiguous
mentions; they never populate verified `settlement_sources`. Bitcoin settlement basis
remains `unresolved`, sources stay empty and `rules_known=false`, even for an affirmative
mention. The same closed gate applies when reloading earlier captures. No averaging
interval or settlement outcome is inferred. Coinbase spot is only a covariate: trade time and local receipt must
both be known by the decision, and each must be within five minutes. A current quote
never supplies historical executable depth. Close-date grouping is explicitly a statistical
grouping date, not a parsed settlement definition.
All Bitcoin samples keep `rules_known=false`: this adapter has no verified complete
resolution parser for comparator, reference index, averaging interval, timezone, rounding
and exceptional outcomes. An authority mention alone cannot open that gate. The exported
contract details expose the same flag, including for ambiguous or apparently detailed text.

Weather reuses full-local-day hourly maximum construction, including existing receipt and
publication gates and complete local-day checks. Missing hours stay missing. Forward
captures do not backfill earlier decisions. Exported forecast receipts, market receipts,
normalized rows and capture summaries are checksum-bound to the public manifest; loading
rechecks raw references, input hashes, decision clocks and configured family membership.
No protected holdout outcomes or fitted training labels appear in the review projection.
Weather source responses, including HTTP errors and NWS point discovery, also appear in
the public receipt list with raw-body hashes and receipt clocks. Connection/stream errors
have timestamped failure events and no fabricated HTTP receipt. Missing provider vintages
mark a partial capture incomplete even when another provider supplied usable features.

## Storage and worker lifecycle

Default state is ignored `data/cache/workbench/`: `jobs.sqlite` stores the last 50 runs
shown in the UI (older rows remain on disk), `registry.sqlite` stores existing research
and experiment lineage, and `runs/<UUID>/` retains inputs, artifacts, local MLflow and
`review.json`. `--workspace` accepts only a subdirectory of this checkout's `data/cache`.
Prompts and evidence are private local files; no telemetry is added. Retained runs consume
disk until the owner archives/removes the workspace while the server is stopped.

One server owns the workspace lock. Up to eight pending/running jobs can exist, with one
isolated worker at a time and a ten-minute worker deadline. Workers receive an environment
allowlist with local MLflow paths and CPU limits; no inherited credentials or HOME setting.
Cancelling a job prevents a late worker result from overwriting it. Server shutdown kills
its active worker; restarting marks unfinished jobs interrupted, rather than silently
rerunning network work or searches. Submit a new job to retry. Partial artifacts remain
available locally. Terminal results cannot be overwritten by subsequent worker updates.

HTTP requests require an exact localhost Host and same origin; writes additionally require
the per-server CSRF token, JSON content type and a size-bounded closed request schema.
Only fixed assets, jobs, cancellation and protected review/report routes exist. This does
not defend against malicious code already running as the same OS user.

## Browser acceptance procedure

This procedure requires a listener-capable environment with an available browser.
It is not satisfied by calling a handler in memory or running a worker directly.
Record UTC start/end clocks, job IDs, inspected tabs, screenshots and downloaded filenames
in a timestamped receipt. A successful public capture requires actual HTTP response receipts,
listed contracts and observations; an incomplete capture is a separate failure-path result.

1. Launch `uv run entropytrade-web --workspace data/cache/workbench-browser-review` and
   open `http://127.0.0.1:43128`. Submit recorded weather with
   `revision_f >= 1.25 and hours_to_close < 8`. Inspect the typed specification, real
   insufficiency, empty probabilities and excluded holdout. Download Review JSON/Text report.
2. Choose Software demo. Wait for synthetic modeling/replay, inspect candidate gates,
   simulated scenarios and validation probabilities. Confirm the synthetic banner in every
   tab and zero simulated fills for the negative control. Download both artifacts.
3. Choose weather + Fetch public sources now, then Bitcoin + Fetch public sources now.
   Inspect actual receipts, failures, rules and feature clocks in Evidence & lineage.
   Check Bitcoin's `rules_known=false`. Partial/failed capture must remain visibly incomplete;
   neither current capture may acquire historical labels, model performance or fills.
   Inspect Bitcoin's separate unverified authority mentions and empty settlement sources.
   Record each successful family capture separately from acquisition failures; a failed
   connection cannot satisfy successful ingestion acceptance.
   On each of the three result tabs, verify the acquisition heading, receipt/contract/
   observation counts and uncollapsed failure summaries. Check the same counts, clocks,
   failure summaries and unresolved settlement limitations in downloaded text reports.
4. Start another synthetic run and cancel it while active. Confirm terminal cancellation,
   then submit a recorded run to verify the worker slot is released. Stop the server during
   another active/pending run; restart with the same workspace. Reload the page, check
   interrupted history and reopen each completed run. Compare parsed downloaded JSON and
   report bytes against the retained reviews/reports, and checksum both downloads with the
   timestamped browser receipt.

## Verification on 2026-10-25

The latest [review bundle](../data/workbench-review/README.md) is `20261025T163400Z`.
The implementation remains uncommitted on `supervisor/20261025-014400`; the current
instruction reserves **all Git mutations, including commits**, for the supervisor.
No branch, staging, commit, merge or push was attempted in this continuation.

`uv lock --check`, `uv sync --locked` and the installed entry-point help pass. With normal
per-command approval for localhost listeners, the full unchanged `make check` passes:
Ruff lint/format clean, strict mypy clean across 477 Python files, and **733 pytest tests
passed in 154.68 seconds**. No skip, xfail, policy change or test weakening was used.
The five new public-worker cases distinguish connection failures, HTTP errors, partial
captures, complete ingestion and empty listings; they verify persisted reports and closed
settlement/evaluation gates. Nine additional dependency-free Node presentation checks pass
for visible failed/partial captures, literal source text and synthetic banners on all tabs.
These DOM checks do not replace real browser acceptance.

```bash
UV_CACHE_DIR=data/cache/uv-verification UV_OFFLINE=1 \
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 \
PYTEST_ADDOPTS=--tb=short make check
node --test frontend/tests/acquisition.test.cjs
```

The installed server actually ran at `http://127.0.0.1:43128` with isolated workspace
`data/cache/workbench-browser-review-20261025T163400Z`. Actual HTTP submissions exercised:

| Run | Observed result | Interpretation |
| --- | --- | --- |
| Recorded weather | 36 contracts, six events, three dates; zero eligible events/scalar labels; two INSUFFICIENT_DATA candidates | Historical insufficiency, without fitted probabilities, forecast metrics, scenarios or fills |
| Synthetic weather | 192 permitted validation records, first 100 exposed; negative control zero fills in all three scenarios | Software replay only; no empirical performance claim |
| Public weather | 8 successful HTTP receipts, 24 listed contracts, 648 observations, zero acquisition failures | Successful forward ingestion; two INSUFFICIENT_DATA candidates, no historical evaluation |
| Public Bitcoin | 3 successful HTTP receipts, 318 listed contracts, one Coinbase spot observation, zero acquisition failures | Successful distinct-family ingestion; every rule gate stays closed and settlement sources remain empty |
| Ordinary sandbox Bitcoin failure | Zero HTTP receipts/contracts/observations; clocked KXBTC GatewayError and Coinbase ConnectError | Actual incomplete acquisition in an isolated worker, not a browser submission |

Weather and Bitcoin captures ran at 16:33:55–16:34:00 UTC. Neither capture has historical
labels, fitted probabilities, forecast validation metrics or simulated execution results.
Every review keeps final holdout unevaluated. The additional denied-network attempt at
16:43:01 UTC separately proves incomplete acquisition and the new text summary; no response
receipt or market data was invented for that failure.

Actual HTTP controls also cancelled a synthetic run during modeling, reused its worker
slot for a completed recorded run, stopped the server with another active and pending job,
then restarted the same workspace. Both unfinished jobs became interrupted. All four
completed runs reopened through HTTP, with identical review/report bytes and checksums
across restart. These exports are HTTP-client downloads, **not browser downloads**.
All 51 workflow artifact hashes and protected review projections are rechecked in the bundle;
public inputs reload through the checksum-verifying adapter. No training/holdout labels
are copied into the review bundle.

**Browser acceptance is still blocked.** Computer Use listed no connected browser sessions,
rejected native Chrome with “Computer Use was not approved to use Google Chrome,” and
reported “Browser is not available: iab” for the in-app browser. Chrome access was requested
while the unaffected work continued. No screenshots, visual inspections, browser submissions
or browser downloads are claimed. Every browser step above remains pending, including
visible failure presentation and browser cancellation/restart/history. The successful public
captures and automated checks do not satisfy that requirement.

The bundle includes exact commands, source hashes, a reviewable source patch and retained
receipt/artifact checksums. Reproduction from a commit remains for the supervisor after
creating the requested implementation commit; HEAD is still the R4 base
`30bed8e30cf07201124deee609a21f7f01e47735`. No Git write was tried. Earlier blocked attempts
remain unchanged and describe their own environment, not this successful listener/network
verification. Complete browser acceptance and commit-based reproduction before integration.
Continuous shadow, official Bitcoin outcomes/history and Bitcoin training remain later work.
