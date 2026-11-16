# Autonomous research lifecycle

EntropyTrade turns one research objective into durable, inspectable research jobs. Language
models only propose. Deterministic code derives requirements, checks evidence, acquires data
from approved read-only sources, and sets every status. Nothing in this lifecycle can place an
order. Production submission stays disabled.

## Readiness dashboard

| Milestone | Scope | Status |
| --- | --- | --- |
| A. Durable research and data requirements | Persistent jobs, typed hypotheses, machine-readable requirements, dataset inventory, missing-data reports, provider selection and budgets, website | Implemented |
| B. Acquisition and feature registration | Source catalog and evaluation, read-only acquisition, immutable datasets, feature materialization, forward-collection requests, automatic reevaluation | Implemented; verified live for KXHIGHPHIL |
| C. Modeling, backtesting and validation | Durable acquired-feature fitting, temporal validation, verified local evidence, contract replay and reports | Implemented; authentic validation and prospective evidence remain gated |
| D. Paper-trading lifecycle | Validated strategies in persistent paper accounts | Not started |
| E. Approval and live-readiness | Approval artifacts, promotion gates, degradation investigations | Not started; live trading stays disabled |
| F. Complete frontend workflow | End-to-end observation and management on the website | Partial (each milestone ships its own pages) |

## Using it

Start the private website from the repository root:

```sh
uv run entropytrade-web
```

Open **Autonomous Research** at `http://127.0.0.1:43128/#/research`. Describe an objective,
choose the market family, optional series, AI provider, budget, validation depth and data
acquisition permission, then **Start research**. The job page updates while the job runs and
keeps its state after you leave or restart the server. **Export report** downloads a JSON
report with a content hash.

## Job lifecycle

Each job is a row in `research/research.sqlite` inside the workspace. It moves through a fixed
state machine (`entropytrade.research.model.TRANSITIONS`):

`queued → generating_hypotheses → planning_data → (acquiring_data → registering_features → modeling) →
evaluated | awaiting_observations | awaiting_authorization`, with `recoverable_error`,
`failed` and `cancelled`.

- **Every step is idempotent and checkpointed.** After a restart, the job reruns its current
  step. Hypotheses are never duplicated.
- **Retries are bounded.** Transient failures, such as provider rate limits or timeouts, retry
  with exponential backoff up to the job's `max_retries`. Permanent failures, such as a missing
  credential, a rejected key or invalid output, fail the job immediately. Nothing is
  fabricated.
- **Budgets are hard limits.** Each job has limits for AI spend (USD), HTTP requests, bytes,
  runtime and retries.
- **Idempotent submission.** Submitting an equivalent unfinished request returns the existing
  job.
- **Waiting jobs make no AI calls.** A job waiting for observations is reevaluated on a
  schedule.

## Hypotheses

A hypothesis is a typed `HypothesisSpec`. It holds:

- its ID, version and objective;
- the market family and contract universe;
- its rationale and features, plus a separate label (labels can never be features);
- local decision times and timestamp semantics;
- candidate models and typed rule sketches (thresholds are fitted, never guessed);
- a validation plan, leakage risks and invalidation criteria;
- its provenance.

`claims_edge` is fixed to `False`.

- **Local templates** are deterministic family templates, ranked by the objective. They are
  labeled as such, not as model reasoning. Weather has five: forecast bias against the
  settlement high, revision momentum, provider disagreement, uncertainty mispricing, and
  near-expiry reaction.
- **Provider hypotheses** come from Gemini, Anthropic, OpenAI or a loopback OpenAI-compatible
  endpoint such as Ollama or vLLM. The provider is called once, in an isolated worker process
  (`entropytrade.research.worker`). The output must validate against
  `HypothesisProposalBatch`. Unknown candidate models are dropped. Proposed source URLs are
  never fetched.
- **Repeated searches are tracked.** A duplicate within a job is kept and marked `duplicate`.
  Every mechanism signature is counted globally, so later validation can account for repeated
  searches.

The research service can set only research statuses:

- `proposed`, `duplicate`, `rejected`, `permanently_unsupported`;
- `needs_more_data`, `awaiting_authorization`, `awaiting_new_observations`;
- `insufficient_evidence`, `backtest_eligible`.

Later statuses, from `historically_promising` through `live_active`, are refused by the store
until a later milestone's deterministic evidence gates exist.

## Requirements and inventory

The feature registry (`entropytrade.research.registry`) maps each feature to typed inputs:

- evidence kind and variable;
- required clock: issuance, receipt or any;
- fidelity and minimum vintages or sources.

A hypothesis's features and label become one `DataRequirement` per evidence kind and entity,
plus its execution needs: contracts, decision-time quotes and the fee schedule.

- A requirement is **predictive** for a hypothesis when that hypothesis's test needs it.
- It is **execution-only** when only an executable backtest needs it.

Feature names resolve exactly or through an explicitly reviewed alias, such as
`forecast_revision_f` for `revision_f`. An unknown name stays **unregistered**. Its declared
data needs are still recorded, and the hypothesis is marked `permanently_unsupported` until a
reviewed definition exists. An unknown name is never mapped to a different feature.

Before anything is acquired, the inventory reads every existing evidence store:

- research acquisitions;
- the configured research evidence;
- retained weather snapshots;
- Weather Company label batches;
- shadow-monitor captures;
- fee evidence;
- sanitized canonical-collector status files.

A dataset satisfies a requirement only when all of these match: kind, variable, entity, clock,
fidelity, provenance (authentic, never synthetic or demo), and the research window. Historical
values with only receipt clocks never satisfy an issuance-clock requirement.

## Website and API

- **API.** `GET /api/research`, `/api/research/jobs`, `/api/research/jobs/{id}`,
  `/api/research/jobs/{id}/report` and `/api/research/inventory`.
- **Writes.** `POST /api/research/jobs` and `/api/research/jobs/{id}/{cancel|resume}` require
  the same-origin CSRF token, like every other write.
- **Demo Mode** shows one labeled fictional job generated in the browser and makes no research
  API calls.

## Credentials

Keys live only in the server environment. Neither the browser nor the request schema can carry
them.

| Provider | Server variable |
| --- | --- |
| Gemini | `GEMINI_API_KEY` |
| Anthropic | `ENTROPYTRADE_RESEARCH_ANTHROPIC_API_KEY` |
| OpenAI | `ENTROPYTRADE_RESEARCH_OPENAI_API_KEY` |
| Local OpenAI-compatible | `ENTROPYTRADE_LOCAL_LLM_URL` (loopback only), optional `ENTROPYTRADE_LOCAL_LLM_KEY` |

A Claude Code, ChatGPT or Codex subscription does not provide API credits.
The original `ENTROPYTRADE_RESEARCH_API_KEY` remains a fallback for OpenAI or Anthropic;
provider-specific keys take precedence, allowing both to be configured on one server.
Ambient SDK variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) remain ignored. Only the
selected provider's research keys enter its isolated worker. A configured credential is
not proof of an authenticated call; the catalog reports live verification as outstanding.
Invalid local endpoint URLs are reported as unconfigured and never contacted.

## Sources and evaluation (Milestone B)

Approved sources are reviewed data in `configs/research/sources.json`; acquisition code exists
only for the adapters they name. For every unmet requirement the service evaluates each source
that offers its kind and variable and records a decision with its checks: identity, access and
authorization, licensing, entity mapping, clocks, settlement authority, historical coverage,
adapter and cost.

| Source | Provides | Clock | Decision for KXHIGHPHIL |
| --- | --- | --- | --- |
| `iem-nws-pfm` (NWS Point Forecast Matrices, IEM archive) | daytime-maximum forecast vintages and revisions | issuance (WMO header and issuance line) | acquire |
| `iem-nws-cli` (NWS Daily Climate Reports, IEM archive) | reference daily highs | issuance of the final report | acquire |
| `weather-company-labels` | settlement-authority daily highs | receipt | acquire |
| `kalshi-settled-markets` | contract terms and finalized results | receipt (rules as retrieved after settlement) | acquire |
| `open-meteo-previous-runs` | historical forecast values | **unknown** | reject: values without availability clocks would be hindsight |
| `kalshi-orderbook-forward`, `nws-hourly-forward` | decision-time quotes, hourly forecasts | receipt | forward collection by the canonical collector |
| `open-meteo-ensemble`, `nws-station-observations` | ensemble members, intraday observations | receipt | forward collection after a reviewed collector change |
| `kalshi-fee-schedule` | fee schedule | receipt | human capture and certification |

A model may name a source, but only an exact catalog ID is ever considered, and no proposed
URL is fetched. PFM point mappings are verified only for Philadelphia; other stations are
rejected for that source until a mapping is verified against a retained product.

## Acquisition

Acquisitions are durable rows keyed by a hash of source, adapter version and parameters.

- **Read-only and allowlisted.** HTTPS GET only, to the catalog's host and path prefixes, with
  no credentials, no redirects, per-response and per-job byte caps, per-host pacing, and up to
  three attempts for transient errors (timeouts, 429, 5xx).
- **Preserved bytes.** Every response body is stored once in `research/raw/` by SHA-256, with
  its URL, status, receipt clock and selected headers.
- **Fail-closed parsing.** A product whose header and issuance line disagree, a PFM point whose
  coordinates do not match, a misaligned table column or a same-day CLI report is refused, not
  repaired. A parse failure publishes nothing and keeps the bytes.
- **Immutable datasets.** `research/datasets/sha256-*` holds records, receipts, parameters and a
  manifest with checksums and coverage. Identical content resolves to the same ID.
- **No repeat downloads.** Planning first checks the inventory, then fetches only dates no
  earlier acquisition from that source covered. Later jobs reuse earlier datasets.
- **Permissions.** `approved_sources` acquires automatically; `ask` waits for **Approve** or
  **Deny** per acquisition while independent work continues; `none` only inventories.
- **Budgets and cancellation.** Requests and bytes count against the job. When a job's budget or
  life ends, unstarted shared acquisitions stay queued for other jobs. A restart requeues an
  interrupted fetch.

## Features

Research features are materialized as immutable artifacts in `research/features/sha256-*` with
their definition hash, input dataset lineage, decision schedule and window. Every value records
the latest availability clock of its inputs, and publication fails if any input became
available after its decision time. Missing inputs give null. The settlement label is a separate
artifact and never a decision-time feature. A changed artifact supersedes the earlier one, which
stays on disk.

- `nws_pfm_max_f`: latest PFM daytime maximum issued by the decision.
- `nws_pfm_revision_f`: latest minus preceding vintage, both issued by the decision.
- `nws_cli_bias_f`: mean of CLI high minus the PFM issued at the same lead, over earlier days
  whose CLI report was issued by the decision (at least five).
- `settlement_high_f`: Weather Company authority label (outcome only).

## Forward collection and reevaluation

When evidence can only accrue prospectively, the job records a forward request keyed by an
equivalent-requirement hash, so collection is never duplicated across jobs. The request names
the existing collector that covers it (from `configs/data/collector.json` and
`configs/data/weather-forward.json`) or states that a reviewed collector change and human
deployment are needed. The job waits in `awaiting_observations` and is reevaluated every six
hours without AI calls, and identical data is never downloaded again. When enough genuine
observations exist, the requirement becomes satisfied and the job continues.

The website never starts a collector or a second canonical chain.

Forward requests expose a separate `operational_status`. `planned` means a checked-in
configuration covers the need; it is not evidence of installation. `blocked` requires a
reviewed collector change or operator action. `failed`/`stalled` retain recorded errors.
`sufficient` uses the current job's requirement assessment, independent of shared request
counts. `deployed` and `collecting` are deliberately not asserted without verified installed
configuration and recent original receipts. Sanitized status summaries supply neither proof.

### Canonical collector coordination

The canonical collector runs on the Windows/WSL machine, and this repository cannot read it.
To show its progress here without moving evidence:

1. On the collector host, restore a verified snapshot into a scratch workspace (never the live
   `data/cache/chain`).
2. Run `uv run python -m entropytrade.research.collector_status --workspace <restored copy>
   --output status.json`. The file has covered-date counts per kind, entity and source, and a
   content hash. It has no prices, forecasts, labels, credentials or file bytes.
3. Copy `status.json` into `<workspace>/research/collector-status/` on the research machine.

These summaries appear in the inventory, but never satisfy a requirement on their own: raw
evidence must arrive through a verified snapshot. Do not update the collector checkout while it
is collecting; deploy code changes there only after review, between collection windows.

## Live evidence (2026-11-16)

A live run against the public sources, in scratch workspace
`data/cache/research-live-b-1794795091` (not committed):

- **Job.** `6601d1be-d415-4632-b0ae-3fc92c691417`, KXHIGHPHIL/CLIPHL, local templates, quick
  depth, window 2026-10-16 to 2026-11-14.
- **Requests.** 39 public GETs, 4.6 MB of preserved bytes.
- **Datasets.**

  | Source | Records | Notes | Dataset |
  | --- | --- | --- | --- |
  | PFM | 845 forecast vintages | 0 refused | `sha256:c9b02bae…` |
  | CLI | 30 final reports | 31 same-day reports refused | `sha256:ca534f4f…` |
  | Weather Company | 30 official labels | | `sha256:674fd6e3…` |
  | Kalshi | 180 settled contracts | rules name The Weather Company | `sha256:1b1c29c6…` |

- **Features.**

  | Feature | Non-null rows | Independent dates |
  | --- | --- | --- |
  | `nws_pfm_max_f` | 60 of 60 | 30 |
  | `nws_pfm_revision_f` | 60 of 60 | 30 |
  | `nws_cli_bias_f` | 49 of 60 | 25 |
  | `settlement_high_f` | 30 of 30 | 30 |

- **Forecast-bias hypothesis.** Its predictive evidence is complete (3 of 3). It is
  `awaiting_authorization` because the fee schedule needs human certification, and decision-time
  quotes are awaited from the canonical collector (0 of 20).
- **Repeat check.** Reevaluation made no new requests.
- **Defects found and fixed.** This run exposed two defects that the replay fixtures had hidden:
  compressed Kalshi bodies were not decoded, and a parse error could leave an acquisition
  running. Both are fixed and covered by tests.

## Limitations

- The provider path is verified with scripted models at the PydanticAI boundary. No live
  provider call was made.
- Provider costs come from the installed pricing data. A model it cannot price is refused, as
  in the existing research pipeline.
- Features for quotes, depth, ensembles, intraday observations and provider disagreement have no
  research materializer yet; those hypotheses cannot become backtest-eligible.
- Contract rules acquired after settlement do not certify the rules known at decision time.
- No model, backtest, validation or paper trading runs here (Milestones C–E). Backtest
  eligibility is not evidence of an edge.


## Modeling integration (Milestone C)

After registering features the same worker advances `modeling`, one frozen hypothesis
experiment per step. Missing, unsupported, late or insufficient inputs produce persistent
scientific refusals. Experiments and their complete history appear in the **Modeling &
validation** tab and JSON report. Successful predictive analysis does not imply executable
profitability or deployment eligibility. See [modeling scope and acceptance](research-modeling.md).
