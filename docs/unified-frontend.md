# Unified research website

Milestone F connects the existing research, experiment, paper, monitoring and review
interfaces through persistent links and a workspace index. It retains the legacy Research
Workbench and CIS 1990 demonstration. Scientific checks and simulated accounting remain
owned by their existing backend services.

## Follow a research objective

Use **New research** in the Strategy Lab or command palette to enter an objective and
select a provider. The saved research job retains its actual queue, acquisition, modeling
and validation states. Missing provider credentials produce an explicit failure; choosing
an AI provider never silently selects local templates.

The job's tabs expose hypotheses, requirements, sources, acquisitions, reusable features,
experiments, forward collection, paper eligibility and events. Select an experiment to
inspect that exact recorded model, backtest, validation and refusal history. Paper
eligibility remains subject to the deterministic gates described in
[research modeling](research-modeling.md) and [paper deployment](research-paper.md).

From a paper deployment, open its account, monitoring, readiness or execution evidence.
Research lineage links return to the exact originating experiment. An alert links to its
own monitor, and readiness links retain the selected immutable proposal. Approval and
halt release still use the [owner workflow](research-readiness.md); every trading flag
remains disabled.

## Counts and recorded status

Overview, Strategy Lab and Backtesting use `GET /api/workspace/summary`. The endpoint
counts all rows in the existing SQLite stores rather than counting capped history lists.
Each component exposes at most ten recent references. Autonomous jobs and experiments,
legacy research, course runs, monitors, actual paper accounts, alerts and readiness
records remain distinguishable.

An absent optional store is **not started**. Unreadable, incomplete or changing metadata
is **unavailable**, displayed with an unknown value rather than a fabricated zero. A
monitor without a committed account does not become a funded account. Recorded real and
synthetic data kinds remain explicit; the summary does not combine profit across them.

The summary reads stored metadata. Completion, a model artifact reference or an approved
review state does not establish current scientific eligibility or profitability. Open the
detail page for verified reports, source integrity and current gates. Backtest and
validation states are shown separately, including blocked and refused results.

Components use independent read transactions; their counts are not a single atomic
snapshot across databases. A concurrent change can make a component temporarily
unavailable. The endpoint creates no schema, refreshes no alerts, trains no model and
changes no application record. Closed WAL databases are read without creating sidecars;
active SQLite readers may use the existing volatile SHM coordination index.

## Links survive reload and navigation

| Record | Link |
| --- | --- |
| New objective | `#/research?new=1` |
| Exact experiment | `#/research/{job}?tab=experiments&experiment={hash}` |
| Experiment's paper eligibility | `#/research/{job}?tab=paper&experiment={hash}` |
| Paper account or evidence | `#/paper/{monitor}?tab=account` or `tab=evidence` |
| Monitoring | `#/paper/{monitor}?tab=monitoring` |
| Exact readiness record | `#/paper/{monitor}?tab=readiness&proposal={hash}` |
| Selected alert | `#/ops?tab=alerts&monitor={monitor}&alert={alert}` |
| Saved legacy run | `#/workbench?job={job}` |
| Saved course run | `#/cis1990/{job}` |

The router validates supported selections. An unavailable selected record produces an
explicit refusal rather than silently displaying a different experiment, proposal or
course run. Tab and picker changes update the link, and browser back/forward restores the
selection. While another proposal loads, the previous record's export and review controls
are removed.

## Workspace, Demo and legacy operation

**Real** selects persisted workspace records; their individual provenance can still be
synthetic. The source chip says **Workspace data · persisted**. **Demo** selects fictional
browser-generated examples. Demo mode prevents new API dispatch from the interface,
including the legacy workbench's saved controls and background polling. Server research
jobs continue while the interface displays Demo; use their explicit cancel controls when
you intend to stop them.

The Research Workbench initializes when opened in visible Real mode. Its job and monitor
handoffs await initialization. Leaving the workbench or hiding the browser tab suspends
its polling, and activation epochs discard stale responses and controls. Returning to
visible Real mode refreshes its token and current records. CIS 1990 keeps its existing
course workflow and saved evidence views.

## Acceptance and remaining gates

See [executed frontend acceptance](../data/unified-frontend-review/20261117/README.md)
for the final checks and controlled browser procedures. Positive computed examples use
explicitly synthetic source wires; history-count probes are recorded metadata, not
scientific evidence. Authentic point-in-time history, certified fees, provider live
verification and sufficient prospective validation remain separate requirements. No
real-money route or physical Windows collector change is part of this milestone.
