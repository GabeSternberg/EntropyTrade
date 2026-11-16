# Autonomous research lifecycle

EntropyTrade turns one research objective into durable, inspectable research jobs. Language
models only propose. Deterministic code derives requirements, checks evidence, acquires data
from approved read-only sources, and sets every status. Nothing in this lifecycle can place an
order. Production submission stays disabled.

## Readiness dashboard

| Milestone | Scope | Status |
| --- | --- | --- |
| A. Durable research and data requirements | Persistent jobs, typed hypotheses, machine-readable requirements, dataset inventory, missing-data reports, provider selection and budgets, website | Implemented |
| B. Acquisition and feature registration | Source catalog and evaluation, read-only acquisition, immutable datasets, feature materialization, forward-collection requests, automatic reevaluation | Not started |
| C. Modeling, backtesting and validation | Deterministic model fitting and realistic backtests on acquired features | Not started |
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

`queued → generating_hypotheses → planning_data → (acquiring_data → registering_features) →
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
| Anthropic or OpenAI | `ENTROPYTRADE_RESEARCH_API_KEY` |
| Local OpenAI-compatible | `ENTROPYTRADE_LOCAL_LLM_URL` (loopback only), optional `ENTROPYTRADE_LOCAL_LLM_KEY` |

A Claude Code, ChatGPT or Codex subscription does not provide API credits.

## Limitations

- The provider path is verified with scripted models at the PydanticAI boundary. No live
  provider call was made in this milestone.
- Provider costs come from the installed pricing data. A model it cannot price is refused, as
  in the existing research pipeline.
