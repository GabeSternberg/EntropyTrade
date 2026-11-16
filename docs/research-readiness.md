# Research readiness, owner review and monitoring

Milestone E records evidence and human decisions about **future readiness**. An approved
record leaves `execution_authorized=false` and `submission_enabled=false`. It does not
fund an account, change the paper broker's limits, activate a model or authorize an order.
Exchange account credentials and real-money order submission remain outside this workflow.

This extends the existing [research-to-paper workflow](research-paper.md), paper account,
Jobs SQLite database, alert history and research queue. It adds no parallel execution or
accounting system. The terminal-position polling limitation described in the Milestone D
document is superseded by the settlement-only drain described below.

## Configure the local owner

From the research checkout root, after installing the locked environment:

```bash
.venv/bin/python -m entropytrade.api.owner init \
  --file "$HOME/.config/entropytrade/owner.json" --owner-id owner

.venv/bin/python -m entropytrade.api.server \
  --workspace data/cache/research --port 43128 \
  --owner-file "$HOME/.config/entropytrade/owner.json"
```

Open `http://127.0.0.1:43128` and use **Owner access** to sign in. Setup requires an
interactive local terminal and asks for the passphrase twice without echoing it. There is
no HTTP setup endpoint, default passphrase or browser-supplied owner identity. Passphrases
contain 12–256 characters; their exact bytes, including surrounding spaces, matter.

The credential path must be absolute, outside the checkout and workspace, outside a
canonical collector chain, and free of symlink ancestors. Initialization creates a private
owner directory (0700) and a regular credential file (0600), and refuses to overwrite an
existing credential. The file contains a salted PBKDF2-HMAC-SHA256 verifier with 600,000
iterations. Keep it out of Git, research exports and workspace backups. An explicitly
configured invalid file refuses server startup. Starting without `--owner-file` permits
ordinary local research and safety reductions but leaves owner review and halt release
unavailable.

Owner sessions last 30 minutes, live only in server memory and are invalid after restart.
Logout invalidates the session; a changed credential fingerprint invalidates existing
sessions when checked. Cookies are instance-specific, HttpOnly and SameSite=Strict, and
session authorization is bound to the validated localhost audience. Login limits are five
attempts per minute and two concurrent password derivations. Owner validity is checked
again at privileged database commits, including after waiting for the database lock.

This is a **trusted local service boundary**. The server binds only to `127.0.0.1` and
retains its exact localhost Host/Origin and CSRF checks. Owner login protects readiness
review, rollback and global halt release; it does not authenticate every research endpoint.
Local HTTP cookies do not isolate mutually untrusted services by port. Use a trusted local
account and machine. Private HTTPS, remote identity enforcement and Windows/Tailscale
operation require the separate deployment work; this local command does not establish them.

## Freeze and review a proposal

In a selected paper deployment, open **Readiness**. The server builds a preview from its
immutable research origin, strategy/model/feature versions, chronological validation,
committed forward evidence, current fee applicability, paper account and operational
incidents. Saving a proposal freezes the facts and their evidence hash, the reviewed paper
prefix, material references, proposed limits and current control epoch. A blocked report
can be saved for inspection; saving does not assert eligibility.

The only money inputs are decimal-text proposed capital and maximum loss. The server
derives all other limits:

| Proposed bound | Current policy |
| --- | --- |
| Capital envelope | $10–$1,000, in exact cents |
| Maximum loss and drawdown | $0.01–min($50, proposed capital) |
| Per trade | min($5, proposed capital) |
| Per event | min($25, proposed capital) |
| Total deployed exposure | min($50, proposed capital) |
| Open orders / envelope contracts | 10 / 100 |
| Sum of approved virtual envelopes | At most $1,000 across the workspace |

These are proposed future bounds and review bookkeeping. They neither allocate real
capital nor replace the existing $1,000 virtual paper account or its deterministic broker
and risk controls. The browser cannot supply an Actor, fitted model, fee certification,
eligibility flag or risk-policy override.

An owner can approve or reject a proposed record with a reason. Approval requires fresh
successful checks: an active paper deployment, no workspace halt or open operational
incident, authentic provenance, intact source/model/paper evidence, current uniquely
applicable certified fees, sufficient prospective validation, and verified at-cost
loss/drawdown/exposure within the proposed bounds. Rejection records the owner decision
without turning a failed check into a pass. The UI treats unavailable checks as unavailable.

The server rechecks proposal revision, control epoch, current account/cycle/alert state,
material source fingerprint and owner validity transactionally. A stale review returns a
conflict and requires a refreshed explicit review. Successful approval supersedes a prior
approved record for that deployment and enforces the workspace virtual ceiling atomically.
Approval remains an audit decision with no activation path, including when a browser is in
its Real mode or a process environment requests LIVE mode.

Normal new paper cycles can extend an intact reviewed prefix. A material model, strategy,
source, feature, fee selection, risk policy, governance history or control-epoch change
requires new validation and review. Pause followed by resume changes governance history;
it cannot silently revive the old approval. Opening a proposal checks its frozen proof
against current evidence and invalidates it when material references or the reviewed prefix
have changed.

**Revoke** is a local safety reduction and needs no owner session. **Rollback** requires an
owner and selects an earlier proposal from the same deployment. It rebuilds a fresh pending
proposal using that prior envelope and today's evidence, and revokes the source proposal.
It does not swap the model, restore old account state, resume a monitor or approve the new
record. A different strategy/model needs the normal research validation and paper-promotion
workflow; suspended and cancelled deployments remain terminal.

## Scientific evidence and its limits

Readiness uses actual retained forward predictions and official outcomes, with original
feature, decision, model-availability and receipt clocks. Production requires real source
provenance. An internally injected synthetic test policy is not exposed through an HTTP
request or production CLI switch.

The current evidence policy requires at least 20 independent station/day events across at
least 10 target dates. Multiple strikes on one event do not become independent events.
Every matched forecast needs a genuine sized two-sided decision-time quote with a valid
spread, no future receipt/exchange timestamp and at most 60 seconds of quote age. The
recorded midpoint is the quoted-probability benchmark. Missing quotes or overdue/refused
outcomes cannot be dropped to improve the score. Expected outcome maturity uses the venue's
frozen expected expiration when later than close, otherwise close, with a one-hour grace.

Reports include Brier score, log loss, reliability and skill against that benchmark. The
95% interval uses 1,000 fixed-seed whole-date bootstrap resamples with equal event weights.
The lower Brier-skill bound must exceed the declared `1e-6` margin plus the `1e-12` numerical
guard. Published diagnostics use declared precision; original probabilities and raw receipt
bytes remain unchanged. `evidence_as_of` is the last committed prefix clock, not the time a
page was opened.

These intervals are not adjusted for repeated strategy/model search. A quoted benchmark is
not an executable fill. Paper fills remain simulations; open exposure, equity and drawdown
are valued at cost rather than marked to market. An apparently positive score or historical
backtest alone cannot authorize deployment. The existing exact-touch strategy's adverse
stress-scenario refusal, authentic historical-data coverage, fee certification and sufficient
genuine prospective evidence remain independent requirements. Controlled acceptance proves
software behavior, not authentic profitability or a deployable trading edge.

## Monitoring and investigations

The selected deployment's **Monitoring** pane shows the evidence clock, checks, reference
review and its current status, signals, durable incidents and investigation links. The
existing shadow runner also evaluates autonomous research deployments in the background.
It processes at most one changed or aged deployment per health check, rotates fairly across
deployments, uses a 60-second cache-age threshold and reserves capacity near approaching
trained research decision points. Legacy polling intervals do not reserve this future capacity
and cannot suppress the E checks indefinitely. This is bounded background work, not a promise that every deployment
is assessed every 60 seconds. Manual refresh requests a fresh assessment.

Monitoring freezes an initial qualified scientific reference automatically as a proposal;
this is never an owner approval. The latest compatible owner-reviewed reference takes
precedence. Making additional unreviewed proposals cannot continually reset the baseline.
Forecast deterioration is assessed on genuinely later target dates, partitioned into all
complete nonoverlapping date blocks. Each block needs the same independent-event/date and
quote coverage requirements. A significantly negative upper Brier-skill bound triggers
`forecast_degradation` and suspension with investigation. An earlier bad block remains
authoritative even if a later block looks better; an incomplete tail cannot clear it. A new
validated, separately reviewed reference is required to reset that comparison. `stable`
means no significant deterioration was detected in the completed comparison; it is not a
new positive skill claim.

Failed source, model, receipt or prefix verification produces `readiness_integrity`;
verified at-cost loss, drawdown or exposure outside the reviewed bounds produces
`risk_limit_breach`. Before a compatible owner review, monitoring uses the default $100
capital / $10 loss proposal and its server-derived exposure bounds. These are readiness
monitoring thresholds, separate from the paper broker's existing caps. Critical integrity
or risk signals suspend active/paused autonomous deployments. Missing or incomplete
evidence stays pending/blocked rather than green, and insufficient labels cannot resolve
an open degradation episode.

Incidents retain evidence and lifecycle events, deduplicate while open, and survive restart.
Acknowledgement records that the operator saw an incident; it neither resolves the condition
nor resumes a monitor. Existing collection-freshness, repeated-failure and unresolved-outcome
incidents remain visible alongside the E signals.

Open incidents can enqueue one diagnostic research job per deployment, incident episode and
pinned policy. The exact request is frozen before enqueue, and a deterministic destination
ID survives crashes between enqueue and linking, restarts, retries and terminal job states.
A pending outbox remains visible when the queue or verified scope prevents safe enqueue.
The request is confined to the existing frozen strategy/model universe and uses
`local_templates`, AI budget $0, zero HTTP requests/bytes, runtime at most 120 seconds,
zero retries, acquisition `none` and paper preference `never`. It does not inherit provider
credentials or change the original research job's selected provider. Its output is a
bounded offline investigation, not fresh acquired evidence, a promotion or reapproval.

## Halt, release and settlement-only continuation

The top-bar paper halt is a local safety reduction with a required reason. It pauses active
monitors, interrupts running claims, invalidates pending/approved readiness records and
advances the workspace control epoch. Workers cannot commit account changes or approvals
from an earlier epoch, even after a later release. Existing cash, fills, positions, original
receipts and audit history remain intact. HALT prevents new decisions; it does not invent
liquidations or reset bankrolls.

An operator-owned `HALT` sentinel at the research workspace root also latches the stop when
observed. A symlink sentinel counts as present. The application never unlinks it, and
removing it does not clear the already persisted halt. Inspect the cause, remove the
operator-owned sentinel manually when appropriate, then use an authenticated owner session
to release the exact current epoch with a reason. A still-present sentinel refuses release.
Release does not resume any monitor; eligible paused monitors need a separate explicit
resume. Cancelled/suspended deployments cannot be resumed by release or rollback.

Held positions can continue to receive official settlement while paused, suspended,
cancelled or globally halted. The server claims an explicit `reconcile_only` cycle from
the persisted account and frozen contracts. It fetches bounded official outcome GETs only;
it skips forecast/source acquisition, model loading/scoring, order-book and fee acquisition,
new decisions, fills and reservations. Even an unreadable current model binding cannot
prevent a trusted drain of an otherwise verified known position.

First polling is due at the frozen expected expiration when later than close, otherwise at
close. Unresolved retries are no more frequent than hourly, including after a claimed
worker dies before making an attempt. Due paper decisions take priority, and approaching
trained decision points reserve the bounded worker's capacity. A workspace halt removes
that new-decision reservation so settlement can continue. The existing 1,000-cycle budget
still applies; settlement is not guaranteed while the service is stopped, source requests
fail or its bounded capacity is exhausted.

Only matching frozen terms, official final binary results and valid publication/receipt
clocks can settle the existing ledger. The outcome becomes available at the new actual GET
receipt time; it is never backdated to contract close or the original prediction. A drain
matures the original forecast without creating another forecast/poll observation. It does
not make a failed forecast capture healthy. Both replay and recovery require the strict
settlement proof whenever either the reconciliation schema or mode marker is present.

## Audit, shutdown and recovery

Readiness proposals are content-addressed immutable JSON. Separate append-only,
hash-linked control/review events retain owner/system identity, reasons, revision, frozen
guard and review transitions. Per-cycle controls freeze the claim mode and epoch. These
records, incident history and investigation outboxes live in the existing `jobs.sqlite`.
Optional E tables are created lazily for E activity; unused legacy/collector workspaces do
not acquire them merely by constructing a store. Canonical collector-chain paths are
rejected before readiness writes. This work does not access or change the Windows collector.

The existing collector can still start its legacy workbench API from canonical staging
workspaces, including `chain/.work-*`. Those servers activate no E monitoring callback or
readiness state. Requesting an E operation there still refuses before research/readiness
writes; ordinary research and owner-review operation belongs in the separate research workspace.

Use [offline workspace recovery](local-recovery.md) after stopping the server and waiting
for all workers and the exclusive lease to exit. The E health callback means
`ShadowRunner.close()` can wait `timeout + 5` seconds: about **245 seconds** with the current
240-second worker timeout. A future deployment unit needs `TimeoutStopSec` of at least
300 seconds and must verify complete service shutdown; a five-second stop deadline is not
appropriate. This does not change any canonical collector service or its shutdown policy.
If the diagnostic thread has not stopped at that deadline, close refuses to release the
workspace lease. Confirm that the process and its workers have exited before recovery or
starting a replacement writer.

For a new archive name and a destination that does not exist:

```bash
.venv/bin/python -m entropytrade.api.recovery snapshot \
  --workspace data/cache/research --archive data/recovery/research-e-001.zip

.venv/bin/python -m entropytrade.api.recovery restore \
  --archive data/recovery/research-e-001.zip --workspace data/cache/research-e-restored

.venv/bin/python -m entropytrade.api.server \
  --workspace data/cache/research-e-restored --port 43128 \
  --owner-file "$HOME/.config/entropytrade/owner.json"
```

Recovery verifies all-or-none optional schemas, control/review audit chains, virtual capital
accounting, frozen scientific claims and paper prefixes, investigation scope/destination,
and strict reconciliation/accounting evidence before publishing the destination. A blocked
proposal retains the partial facts it actually established; restore cannot upgrade it to
eligibility. It neither refits models, reruns bootstrap/scoring, reprices historical fees,
fetches data nor turns an old approval into live authority. Original logical rows, receipt
bytes, clocks, HALT sentinel and terminal/paused states survive; normal startup interrupts
unfinished work and uses fresh receipts rather than manufacturing missed decisions.

Owner credentials and RAM sessions are outside the workspace archive. Reconfigure the
private owner file separately on a recovery machine. Existing local snapshots are private
0600 plaintext ZIP archives, not encrypted offsite backups; keep their returned SHA-256 and
the matching project/lock version privately. Encryption, offsite transport, Windows boot,
private remote access and independent physical-machine restore remain deployment checks.
