# V1 acceptance evidence — October 30, 2026

**complete=false.** This milestone implements retained weather history through the
browser on the designated branch. All Git operations and independent sign-off remain
with the supervisor. No real-money orders, new family or credential access occurred.
External-provider verification is deferred until separately authorized credentials.

| Requirement | Current milestone evidence | Result / remaining work |
|---|---|---|
| Browser receipt ingestion → dataset selection → research/backtest → downloadable results | [Managed Chromium harness](../frontend/browser/weather-history.spec.cjs), [current browser receipt](../data/weather-history-review/20261030/browser-committed/weather-browser-receipt.json), [guide](weather-history.md) | **Scoped authentic-receipt workflow passes.** Ordinary localhost/worker, explicit dataset selection, all tabs, downloads and restart execute. This replays original authentic captures; no new acquisition or empirical performance is implied. |
| Immutable datasets, provenance and deterministic replay | `weather/history.py`, `data/dataset.py`, archive exports and feature pipeline; `test_weather_history.py` | **Scoped checks pass.** Reversed/duplicate input replay is identical; checksums, publication/staging recovery, revision conflicts, first receipt clocks and original acquisition failures are preserved. 4 events, 2 dates, 24 contracts, 48 decisions and 648 observations replace dependence on the legacy six-event sample. |
| Source-matched labels, known-at-time fitting and holdout protection | Existing `verified_targets`/`_examples`; retained fixed partitions; controlled scalar/binary receipt and overnight regressions | **Software checks pass; empirical gate incomplete.** Wrong-source highs cannot substitute; binary outcomes cannot invent scalar labels. Corrections require their original availability; fitting uses timely labels. Fixed 48/12/30-day calendar membership and inherited protections persist across snapshots; protected labels cannot enter bias features. Authentic scalar highs remain absent. |
| Deterministic experiments and realistic accounting | Existing research/StrategySpec/model/R4 engine; authentic browser insufficiency; separately labelled synthetic fitting regression | **Integrated refusal path passes.** Authentic samples yield no fitted probabilities, scenarios, fills or performance claims. Existing minimums, fee/depth/risk gates stay enforced. Sufficient empirical fitting/backtests and certified effective fees remain open. |
| Durable restart, cancellation and offline restore | `test_weather_history_listener.py`, browser downloads/restart; recovery snapshot validation | **Scoped checks pass.** Frozen dataset references, interrupted/cancelled requests and completed result bytes persist; offline restore includes verified snapshots. Broader pre-existing shadow/provider recovery remains covered by the suite. |
| Two meaningfully distinct empirically validated families | Existing weather and optional Bitcoin adapters | **Incomplete.** No family selected; Bitcoin dates remain frozen. Authentic forward ingestion and synthetic fitting do not satisfy empirical two-family validation. |
| Provider-backed research with authorized research credentials | Prior controlled provider integration and pricing evidence below | **Deferred external verification.** No credentials accessed. Existing server configuration, explicit per-run consent and credential isolation remain enforced. |
| Required quality gates and browser artifacts | [Current evidence bundle](../data/weather-history-review/20261030/README.md) | **Pass:** Ruff/format (514 files), strict mypy (511 files), all **1,058 pytest tests in 353.35s**, 18 frontend cases and the actual Chromium procedure (5 screenshots, 4 downloads, zero page errors). Actual managed-Chromium screenshots/downloads are distinct from controlled/unit checks. The existing environment is reused; no new clean-install pass is claimed. |
| Safety and release review | Existing submission boundary and risk tests; unchanged Bitcoin/family/credential boundaries | **V1 incomplete.** No live execution or risk cap changes. Independent supervisor review and a final verified release matrix remain required. |

The prior evidence below remains historical and keeps its original scope and limitations.

# Historical V1 evidence — October 29, 2026

**complete=false.** The current milestone connects provider-backed research to the existing
private website. This matrix records scoped software and operating evidence; it is not
independent release approval. All Git operations and final review belong to the supervisor.
No real credentials, external provider session, real orders or new family were used.

The [current evidence bundle](../data/provider-review/20261029/README.md) contains a fresh
locked installation, source fingerprints, test reports, Playwright-managed Chromium
screenshots/traces/downloads and offline provider/recovery snapshots. Controlled OpenAI
HTTP responses verify software integration; they never count as an external provider pass.
The unmodified server also demonstrates a missing research key with zero provider requests.
Earlier evidence retains its original code, timestamps and limitations.

| Requirement | Evidence | Result and remaining work |
|---|---|---|
| Private usable website: prompt → multiple typed hypotheses → deterministic experiments → results/downloads | `api/server.py`, `jobs.py`, `worker.py`; [provider browser harness](../frontend/browser/provider.spec.cjs), [current receipts](../data/provider-review/20261029/locked-final/browser/provider-browser-receipt.json) | **Scoped browser workflow passes.** Real localhost/page interaction exercises explicit consent, three typed hypotheses using controlled provider HTTP, deterministic real-data insufficiency, all tabs and identical downloads after restart. Synthetic probabilities remain labeled software evidence. Real external-provider reasoning remains separately blocked. |
| Two meaningfully distinct supported families with concrete real-data paths and realistic validation | Existing weather capture and [optional Bitcoin history](bitcoin-history.md) | **Incomplete.** Authentic forward paths exist; neither missing historical source-matched weather fitting/outcomes nor insufficient Bitcoin validation counts as a supported empirical family. Bitcoin's four retained fitting events on three dates, one class and future validation dates remain unchanged. No replacement family selected. |
| Source clocks, as-of joins, leakage checks and protected holdouts | `agents/evidence.py`, `experiments/workflow.py`, existing feature/model/tracking protections; temporal tests and retained source artifacts | **Scoped software checks pass.** Research tools expose permitted projections without outcomes; deterministic gates keep protected events excluded. Provider reviews preserve source/model identities, prompt hashes, run clocks and tool receipts. Actual forward collections never backfill historical availability. Final independent leakage audit and sufficient empirical history remain open. |
| Deterministic reproducible backtests and realistic accounting | Existing R4 experiment/backtest, execution/fee and risk engines; complete-suite regression evidence; browser synthetic workflow | **Software capability present; empirical gate incomplete.** Typed candidates use the same model/fee/depth/chronology/risk gates. Real recorded weather remains insufficient; no real fitted probability, empirical return or profitable strategy is claimed. Effective fees remain uncertified. |
| Provider-backed bounded research with separately authorized credentials | `agents/provider.py`, `pipeline.py`, `api/runner.py`; controlled serialization/job/browser tests; [external check receipt](../data/provider-review/20261029/external-provider-check.json) | **Website integration passes controlled checks; external check BLOCKED.** Operator provider/model configuration plus fresh per-job consent are required. Public configuration is frozen; only opted-in workers receive the dedicated research key. Existing request/tool/token/cost/deadline limits remain. Missing credentials, outages, malformed output and deadlines yield saved failures without experiments or mock fallback. A separately authorized actual provider session remains required. |
| Durable continuous shadow decisions, versions, quotes, intended orders, risk checks and outcomes | Existing tracking store/worker/replay; [current recovery browser receipt](../data/provider-review/20261029/locked-final/browser/recovery-browser-receipt.json), retained workspace archive | **Scoped operating workflow passes.** Browser inspection, pause/resume, interruption, restore, fresh authentic collection and subsequent cancellation/restart execute. Actual model/fee blockers leave intentions absent; eligible reservations/outcome release remain controlled evidence. Zero real submissions/fills; no performance claim. |
| Restart, cancellation and offline recovery | [Provider offline verification](../data/provider-review/20261029/provider-offline-verification.json); browser receipts; existing workspace leases and restore checks | **Scoped checks pass.** Provider snapshot/restore preserves 56 files and logical jobs/registry rows across completed, failed, cancelled and interrupted jobs. Pending opted-in jobs recover as interrupted without automatic billable retries. Existing source/worker lease, frozen binding, reservation and original-receipt protections remain. Broader browser recovery also passes. |
| Safety and credential boundaries | Same-origin/CSRF, request allowlists, worker environment tests, existing submission/risk boundaries | **Scoped checks pass.** Browser requests cannot carry keys, provider URLs, code or model paths. Ambient SDK/exchange keys and HOME do not enter workers; ordinary and shadow workers remain credential-free. Synthetic/provider combinations are refused. No risk limits, execution activation, holdout dates or settlement semantics changed. Final independent review remains necessary. |
| Locked install and complete tests | [Locked setup/browser receipt](../data/provider-review/20261029/locked-final/acceptance.json), [completed suite](../data/provider-review/20261029/complete-suite/receipt.json), [aggregate verification](../data/provider-review/20261029/verification.json) | **Scoped pass after documented export repair.** Fresh offline locked Python/npm setup uses package artifacts and managed Chromium, never an existing virtualenv. Ruff/format, strict mypy (505 files), 15 frontend cases, both real-browser procedures and all 1,033 pytest cases pass. Two original vendored citation documents were added before the final complete-suite rerun; application/test/fee code stayed unchanged. Earlier failed driver reports remain failed, not rewritten. |
| Repeatable operation and limitations | [Workbench](workbench.md), [agent research](agent-research.md), [recovery](local-recovery.md), [roadmap](roadmap.md) and executable locked acceptance driver | **Documented.** Loopback single-user operation; keys require separate authorized setup. Provider cost can be unknown for the first request; unknown cost stops further requests. Cancellation cannot undo an already issued provider charge. Hosted operation, broader serializers/depth scheduling and structural scanning remain deferred. |
| Independent final release acceptance | This matrix plus final code and durable evidence | **Pending.** Supervisor must independently cross-check the actual browser/test/source artifacts and all empirical requirements. Controlled/synthetic or blocked paths cannot satisfy real-data release requirements. |

Full suite: **1,033 passed in 373.42 seconds; zero failures, errors or skips**. The final source/input fingerprint comparison and
exact browser/test counts are retained in the current bundle: 11 screenshots, 19 browser downloads, zero page errors; all 1,474 source/input hashes match checkout and installation. No final release completion
is implied by a complete software suite or a successful recovery workflow.

The retained collector timeout is diagnosed without changing the collector or its test:
sandbox socketpair sends fail with `EPERM`, preventing asyncio executor wakeups; the
credential-free diagnostic and unchanged reconnect test pass through normal approved
execution. The first clean-export attempt additionally omitted existing `data/public`
fixtures and research documents, and used a TMPDIR too long for Chromium's Unix sockets.
The driver now copies the original required inputs, including the exact two vendored fee references used by the old tests, and allocates a short temporary root.
Original denial, timeout, missing-file and browser-crash receipts remain preserved.

Return this substantial intermediate milestone for supervisor review. The next provider
acceptance task, only after separate credential authorization, is one bounded actual
provider-backed website run with typed outputs or an honest saved provider failure,
downloads, source/holdout evidence and recorded cost/usage. Authentic fitting/outcomes,
certified fees, empirical two-family validation and independent V1 review remain open;
no frozen Bitcoin boundary may be moved to satisfy them.
