# Agent research operations (R3)

R3 produces research proposals, not proven strategies or trading approvals. It never calls
the legacy fixture backtest. Existing TestModel demonstrations remain regression tests.

## Run against the recorded real weather coverage

From the repository root, after `uv sync --locked`:

```bash
uv run entropytrade research --config configs/research/weather.json --offline \
  --prompt "Research Philadelphia daily-high markets. Investigate forecast revisions and other signals." \
  --registry data/cache/research.sqlite --output data/cache/research-runs
```

This is explicitly **offline/mock** reasoning over actual recorded contracts and R2
coverage. It uses controlled TestModel outputs, not an LLM service. A second request such
as "Research Chicago model disagreement and probability reliability" changes the mock
focus and permitted city. These runs prove software integration, not autonomous reasoning.
Frozen examples, including full prompts, evidence, specs, verdicts and reports, are under
`data/r3-demo/`. Both have three hypotheses, two typed candidates with insufficient data,
and one proposal unsupported by the interpreter/orchestration. No empirical edge is claimed.

## Enable a real provider

Choose OpenAI or Anthropic and a model available to your account. Put a **research-only**
key into `ENTROPYTRADE_RESEARCH_API_KEY` using your normal secret environment setup. Never
put the key into JSON configuration, the prompt, a command argument, an artifact or Git.
There is no fallback to ambient OpenAI/Anthropic keys or exchange keys. Example:

```bash
uv run entropytrade research --config configs/research/weather.json \
  --provider openai --model gpt-4.1-mini --enable-provider \
  --prompt "Research Philadelphia daily-high markets. Investigate revisions, model disagreement and other falsifiable mechanisms." \
  --registry data/cache/research.sqlite --output data/cache/research-runs
```

For Anthropic, use `--provider anthropic --model MODEL_AVAILABLE_TO_YOUR_ACCOUNT` instead.
A missing key fails with a saved failure record and setup guidance; it never selects mocks
silently. Neither real provider has been externally verified in this environment because
no research key is configured. Actual OpenAI SDK/PydanticAI requests are tested through an
HTTP mock, including tool responses, all four structured roles and provider failure.
Anthropic configuration/guard tests do not constitute a real Anthropic session.

Run one research worker per process. PydanticAI's installed request permission switch is
process-wide: the isolated CLI enables it only during explicit research and restores the
fail-closed default afterward, including on failure. An in-process lock refuses concurrent
research workers. Do not embed live research in a concurrent execution/server process.
This is an application capability boundary, not an OS sandbox. It adds no trading path.

## Evidence and holdout policy

`configs/research/weather.json` selects an approved root, relative feature matrix and R2
result file. Paths and resolved symlinks must stay inside that root. Model versions must
match the feature matrix. Feature manifest/file hashes and referenced model artifact
bytes/hashes are verified without deserialization. Defaults limit input
to 100,000 rows (hard maximum 200,000), 32 MB compressed/64 MB decoded and a 20-second load
deadline. Use local bounded partitions. The load deadline is checked after bounded local
I/O; it is not an OS interrupt for a stuck filesystem.

`holdout_start` is mandatory. Rows on/after that target date are filtered before tool
projections. All outcome values and scalar labels are withheld, including on earlier dates;
only permitted-date scalar-label counts are exposed. The example boundary is September 4,
after the three-date R1 sample, which was too small to form an R2 holdout. When using a real
R2 holdout, configure its start date or an earlier boundary. A trusted operator chooses
this policy; the agent cannot alter it. Recorded final-holdout event IDs in an approved R2
result are independently excluded even if the date configuration is later. No tool accepts a filesystem path, arbitrary SQL,
shell command, URL or holdout query. No joblib file is opened.

One schema-validated `inspect_evidence` tool covers five topics:

- `coverage`: actual dates/cities/events, eligibility, source kinds, missing features,
  scalar-label counts, timing limitations and execution fidelity.
- `markets`: paginated actual recorded event/contract IDs, strikes, rule text, settlement
  authority, capture clock and known-at-decision flags. Same-event contracts share an
  underlying high; exhaustive coverage is not inferred. This is recorded discovery, not
  a live internet scan. Refresh through the R1 data commands when needed.
- `features`: registered names, versions, units, dependencies, transformations,
  availability/missingness rules and the explicit R2 probability prediction interface.
- `models`: approved R2 artifact IDs, fit/calibration status, refusals, and validation-only
  metrics when all validation events are permitted. Never holdout/walk-forward metrics,
  raw prediction records, split IDs or arbitrary model deserialization.
- `history`: recent hypotheses, full prior candidate specs, criticisms and deterministic
  statuses from the same application registry. Use small pages for full specs. Exact
  normalized hypothesis search counts remain indexed across all recorded runs; numeric
  threshold variants share a signature. Paraphrases are not a solved semantic-dedup problem.

Arguments allow topic, exact ticker, offset and page size (1–20). Results are capped at
24,000 characters; request a smaller page when needed. There are at most 32 evidence calls
including five deterministic bootstrap calls. Every returned envelope has a content-based
evidence ID. Raw descriptions and prior agent text are labeled untrusted evidence; they
cannot grant tools or change schema/validation permissions. Citations must refer to an
actually retrieved envelope. This proves provenance of retrieval, not truth of every claim.

## Workflow, gates and persistence

Ordinary Python orchestration coordinates PydanticAI Research → Hypothesis → Quant → Critic.
Every role receives the original request, current evidence and preceding typed outputs.
The research role must actually use a tool. Hypotheses include mechanism, family, window,
variables, direction, test, necessary evidence and falsification. The critic receives full
hypotheses, specs, assumptions and coverage and must judge every candidate exactly once.
The final analyst report is computed from coverage and verdicts; agent prose is explicitly
an unverified proposal. It never computes or invents P&L, Brier, fees or execution results.

Independent gates check citations, actual universes, feature/source/model references,
feature versions, run identity, historical rule/settlement evidence, point-in-time feature
availability, independent event/label counts and execution depth. Unsupported fields or
semantics remain explicit proposals. Statuses are REJECTED, UNSUPPORTED, INSUFFICIENT_DATA
or READY_FOR_EXPERIMENT, with a separate structurally_valid flag. The critic cannot override
these gates. READY_FOR_EXPERIMENT is research eligibility, never profitability or approval.
Minimum counts are conservative gates, not a statistical power calculation.

Budgets: 16 model requests, 24 successful agent tool calls, one structured-output retry,
3,500 output tokens/request, 90,000 input and 14,000 output tokens/run, 100,000 context
characters, 30-second provider request timeouts and a 180-second workflow timeout. SDK
transport retries are disabled. A $2 estimated-cost limit is enforced when pricing is
available; missing cost stops further requests. Token/cost checks use provider reports and
can overshoot on the last response; this is not a prepaid billing guarantee. No unbounded
self-directed loop or automatic experiment search exists.

The existing SQLite Registry stores immutable agent_research_runs plus an indexed search
history. No strategy lifecycle promotion occurs. Each UUID run includes requested and
returned provider/model identities, prompt/instruction/code versions, timings, usage,
inputs/source hashes, bounded tool calls, all stage prompts/outputs, hypotheses, full specs,
spec hashes, critiques, deterministic decisions, report and sanitized failures. Provider
nondeterminism is preserved, not hidden by a supposedly deterministic run ID. Reusing an
explicit run ID with identical inputs returns the original result; changed inputs refuse.
SQLite is authoritative; artifacts are atomically rewritten/recovered from that record.
JSON/Markdown artifacts have checksums. Exceptions record type/stage, not potentially
secret provider messages or headers. Keep the registry path the same across sessions to
retain prior research. R2 MLflow artifacts remain accessible through approved diagnostics;
R3 uses SQLite for narrative lineage rather than duplicating it in another service.

## Integrated experiments and remaining data needs

The current real coverage remains six city/day events, three dates, 36 contracts, zero
eligible forecast events and zero source-matched scalar highs. Both real fitted models
and executable historical depth are absent. Collect actual forecast vintages, historical
rules and Weather Company settlement evidence; NWS CLI cannot replace that authority.

R4 now provides `research-and-test`: bounded YES/NO StrategySpecs, temporal model predictions,
chronological capacity/risk/fee-aware replay, validation rankings and registry/MLflow lineage.
The standalone `research` command still performs no backtest. See [experiment operations](experiments.md).
Real data remains insufficient; the full integration proof uses explicitly synthetic data
and mocked agents. The next approved direction is a minimal local research website.
