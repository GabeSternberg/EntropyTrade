# Research integration readiness

Acceptance started November 17, 2026 (America/New_York; original evidence uses UTC).
**Authentic paper-trading experiments are not yet eligible.** A–F and deployment tooling
are implemented, but implementation does not establish a scientifically qualified strategy.
No Windows host, canonical collector or private research storage was accessed.

## What works

The existing job/store/adapter/model/replay/paper architecture now has a controlled integration
test from a natural-language objective through typed AI proposals, explicit acquisition
approval, immutable raw datasets, point-in-time feature materialization, fitting, independent
chronological validation, a paper-eligibility decision, a paper collection/accounting cycle,
pending prospective monitoring, process reconstruction and snapshot/restore.

Every dataset in that test is marked **synthetic at publication**. Only test boundaries
select synthetic evidence; production rejects all its paper proposals. There are no seeded
feature/model results, forced job transitions, fabricated historical returns or relaxed
holdout, fee, execution or prospective-observation requirements. Controlled HTTP/provider
responses verify software behavior; they do not verify an external AI service or market edge.

Verified handoff fixes consume existing published execution datasets without downloading them
again, schedule six-hour evidence reevaluation for incomplete evaluated jobs, preserve
hypotheses/permissions/frozen partitions, expose exhausted acquisition budgets, cancel provider
and source work on shutdown, and retain the writer lease until research workers stop. Direct
legacy-workbench URLs now initialize after deferred controller registration. The view stays
inert and its native form controls stay disabled until all panels/handlers are ready, so
early history clicks and text input cannot be lost. Controlled paper
browser monitoring uses one consistent test clock; recovery keeps strict byte comparisons.

## Authentic verification

The development container's bounded live attempt failed with `ConnectError` (32 requests,
zero bytes). An anonymous GitHub runner subsequently exercised the **same ResearchService**:

| Thirty-day source | Accepted records | Responses |
| --- | ---: | ---: |
| NWS Point Forecast Matrices via IEM | 862 | 5 |
| NWS final daily climate reports via IEM | 30 | 3 |
| Kalshi settled contract metadata | 180 | 1 |
| Weather Company settlement highs | 30 | 30 |

Four immutable datasets produced four feature artifacts. Original public bytes and reports
are retained in the [acceptance bundle](../data/research-integration-review/20261117/).
Downloaded source hashes, service reconstruction, five persisted refusals and local
snapshot/restore were verified; 78 immutable files remained byte-identical. A smaller
seven-day probe independently verified acquisition/reconstruction. No AI credential or local
model endpoint was configured, so authenticated external AI inference remains unverified.

## Remaining gates and their causes

| Gate | Precise cause / next action |
| --- | --- |
| Timely training labels | The authentic 30-day forecast-bias job has **zero** labels known before its historical training cutoff; eight training labels arrived late. Today's retrieval cannot establish past availability. Obtain independently timestamped historical receipts if they exist, or accumulate prospective labeled dates. |
| Historical execution | Public settled-market metadata has `retrieved_after_settlement` rules and supplies no historical sized books. Import verified original decision-time books/rules from a separate research copy if available. Never reconstruct them from candles or current quotes. |
| Fees | No authentic applicable certified fee versions were available. An operator must review retained official formula, rounding, scope and interval. Receipt/review clocks remain binding: reviewing today supports subsequent decisions, not backdated certification. |
| Prospective qualification | Synthetic cycles establish no genuine forward track record. The default policy requires at least 20 independent settled forward events on 10 dates plus its skill/uncertainty, execution and risk gates. Readiness remains pending until these pass. |
| Feature capability | Several default exploratory hypotheses reference weather-pipeline/market/ensemble features that the acquired Fahrenheit adapter cannot materialize/model. These receive explicit unsupported-feature statuses. Use supported PFM level/revision/CLI-bias inputs, or implement a separately reviewed compatible adapter; no silent name substitution. |
| External AI | Configure an actual dedicated research key or permitted loopback model endpoint and verify a bounded call. Controlled PydanticAI models and provider HTTP cover schemas, budgets, errors, cancellation and credential isolation only. |

Timely training/validation, execution evidence and fees currently block authentic **paper
eligibility**. The prospective minimum belongs to the subsequent **readiness review**:
an eligible paper deployment first collects those forward observations. Provider credentials
are required for provider-generated hypotheses; explicit local templates remain available.
Unsupported adapters block their affected hypotheses, not the supported PFM research path.

Protected outcomes also remain excluded from trailing bias inputs. A newly deployed bias
candidate may lack five eligible prior observations in its 21-day window; it must wait for
fresh permitted evidence. The controlled positive forward-scoring path uses forecast
revisions and does not open protected outcomes to make the bias candidate execute.

The thirty-day probe also has too little history after chronological partitioning. The
ordinary request defaults to 240 days, but a longer window alone cannot fix label clocks:
labels must actually be known before the relevant fitting/calibration cutoff.

## Actions requiring the Windows PC

1. Inspect the observed WSL/Tailscale installation and existing collector status, then deploy
   the reviewed commit in a **separate research checkout**, following the
   [Windows guide](windows-research-server.md). Complete its owner/TLS, stop/start, reboot,
   backup/offsite-download and independent restore acceptance. Do not alter the collector's
   tasks, chain, clocks or configuration.
2. During a naturally idle collector interval, use the guide's
   [read-only encrypted history export](windows-research-server.md#back-up-collector-history-without-operating-the-collector).
   Restore an inspection copy, select a compatible recorded workspace archive and restore a
   separate research copy. The existing local-evidence consumer reads its verified
   `runs/weather-datasets` snapshots. A busy or unverifiable chain must refuse export.
3. Inspect actual book/rule/label coverage and original clocks in that copy. Import only
   verified eligible evidence, then let scheduled inventory reevaluation run. PC access
   alone does not guarantee enough historical data; unsupported collector coverage requires
   a separately reviewed future change, never an automatic deployment.

Fee review and AI-provider configuration can occur on another trusted research host; they
do not intrinsically require this PC. Live submission remains disabled throughout.

## Regression and safety acceptance

Final suite results, source fingerprints, failure/rerun distinctions and the separate review
of leakage, reproducibility, permissions and financial safety are recorded in the
[acceptance bundle](../data/research-integration-review/20261117/README.md).
Changes are reviewed in [PR #35](https://github.com/GabeSternberg/EntropyTrade/pull/35).
