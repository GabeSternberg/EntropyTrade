# Research-to-paper deployments

Milestone D connects an exact completed Autonomous Research experiment and model to the
existing persistent paper monitor, accounting, risk and evidence system. It does not enable
live submission or establish an authentic profitable strategy.

## Workflow

Open a completed research job and its **Paper eligibility** tab. Each fitted model has a
server-derived proposal with exact experiment/model/strategy references and deterministic
checks. The browser submits only those references; it cannot submit fitted coefficients,
risk limits, provenance assertions or a fee policy. Requests retain the existing same-origin
and CSRF protections. `paper_preference=never` is respected.

Production requires authentic source evidence, verified immutable artifacts, a supported
data-only model export, untouched chronological validation, twenty independent evaluation
events, all three sized-book replay scenarios, complete accounting, positive uncertainty
bounds, and an accepted robustness result. Every attempted historical order must have actual
post-decision execution receipts at its fixed execution clock. Missing evidence leaves the
result incomplete, with null headline P&L rather than profitable subset accounting. Current
certified applicable fees are required at promotion and checked again at each decision.

Repeated creation of the same proposal returns the existing deployment, including cancelled
or suspended deployments. A material model, strategy, proof or risk-policy change needs a new
validated proposal. Promotion freezes its origin, selected model, exact strategy, fee proof
and deterministic monetary limits; restart and verified backup/restore retain these refs.
No synthetic source can pass the production promotion policy. Test listeners explicitly
inject a controlled policy and mocked sources; production has no request/CLI fixture switch.

## Exact model and source compatibility

C fitting now emits bounded JSON exports for climatology, raw forecast, forecast error and
ridge. Paper workers load only those verified data fields; they never deserialize joblib.
Unsupported tree exports refuse. Feature definitions, coefficient order, calibration,
series/station scope, model availability and artifact hashes must match the frozen strategy.

The new forward adapter materializes the actual registered PFM/CLI features from approved
IEM archive sources. Hourly weather forecasts never substitute for PFM maxima. Requests are
allowlisted anonymous GETs, with no proxies/redirects, at most eight requests, 32 MB and sixty
seconds per capture. Raw bytes and original clocks are retained. Unavailable sources or
missing feature values produce risk refusals rather than fallback predictions.

Models use the single earliest decision point actually fitted by C. Research monitors align
their next capture to that frozen local-time horizon and permit only a sixty-second bounded
operational delay. Off-horizon contracts cannot consume the book-request budget. Source
acquisition precedes the final decision-book receipt; future receipts never become earlier
inputs. Fitted-artifact publication and actual deployment clocks also bound every prediction.
Nothing backfills missed decisions after a restart.

A later real book can affect execution only; it cannot create another model decision. New
real experiment configurations explicitly require recorded execution evidence. The official
legacy replay loader preserves old serialized configurations and results under the named
legacy snapshot-sensitivity policy. Legacy reproduction certifies repeatability, not actual
fills or profitability. New paper eligibility refuses that legacy execution assumption.

## Accounting and controls

The existing `ShadowRunner`, `PaperBroker`, deterministic risk engine and transactional
accounting handle incoming observations, later-book simulated fills, partial capacity,
fees, positions and official outcomes. The research source uses the same components, not a
second account implementation. Per-monitor virtual bankroll is $1,000, with the existing
$25 per-trade, $100 per-event and $500 deployed caps. The browser cannot override them.

The dashboard shows actual committed simulated fills, open positions, cash, fees, realized
P&L, equity/peak/current drawdown **at cost**, source versions and execution/risk logs.
Open positions are not marked to market. Account timestamps remain visible; stale data
never becomes a zero exposure or a newly observed return.

Pause and resume preserve the account. Cancel and suspend are terminal for that deployment;
late worker results cannot publish fills, account changes or approval state. They preserve
open positions and history. **Terminal deployments currently stop outcome polling too:**
retained open positions may remain unresolved. There is no invented liquidation fill or
bankroll reset. [Milestone E](research-readiness.md) adds bounded settlement-only
continuation for known held contracts after pause, cancellation, suspension or halt.

Source/spec/binding corruption or a changed deterministic risk profile suspends execution.
Promotion fee artifacts must still exist for restore even when their historical effective
interval has expired; recovery verifies the frozen evidence without repricing the past.
Read-only verification reconstructs exact features and predictions from original receipts
without changing the source files.

## Current strategy and external limitations

The currently generated C strategy uses an exact-touch limit with zero slippage allowance.
The one-cent adverse conservative scenario cannot fill that policy. Thus it fails the
unchanged positive-all-scenarios promotion gate by construction. This is a strategy-policy
rejection, independently of insufficient real history or uncertified fees. No stress limit
or paper gate was relaxed to create a positive production candidate. A different execution
policy would need to be preregistered, versioned and revalidated as a new experiment.

Authenticated AI-provider inference, sufficient authentic point-in-time history, human fee
certification and genuine prospective validation remain external gates. Positive end-to-end
paper acceptance uses clearly controlled synthetic forecasts, markets, fees and clocks.
It proves software behavior, not observed market fills, real returns or deployable edge.

The Windows canonical collector is not accessed, reset or changed. Research stores reject
canonical-chain paths before writes, and use verified copied evidence only. No exchange
credentials or live-order transport are introduced. Milestone E approval/monitoring,
Milestone F unification and private Windows deployment readiness remain separate work.
