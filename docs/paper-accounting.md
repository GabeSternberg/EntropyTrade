# Simulated accounting in continuous shadow tracking

Start the existing local website with `uv run entropytrade-web`, complete a real research
run and select its typed candidate under Continuous shadow tracking. Monitoring does not
approve a strategy. Authentic candidates without usable frozen models or certified fees
continue collecting receipts and saving explicit blocked decisions, with zero paper fills.
No credentials or order-submission gateway are used by this workflow.

Select a saved monitor to inspect **Simulated paper account**, positions, cash, fees,
realized simulated P&L and equity at cost. Each cycle exposes paper decisions and their
source versions/probabilities, execution risk checks, simulated orders/fills, refusals and
settlement evidence. **Paper account JSON** downloads the current state; **Shadow evidence
JSON** includes all cycles, complete accounting inputs and the account chain for offline replay.
Observed `fills` stay empty and observed `performance` stays absent. Controlled synthetic
fixtures have a visible synthetic label; their balances never establish empirical returns.

Each monitor starts a separate simulated $1,000 account on its first committed accounting
cycle. Existing historical intentions are never converted into fills. Accounts are independent,
not a shared allocation. The shared shadow limits remain $25 per trade, $100 per event,
$500 deployed total, $1,000 loss/drawdown, $0.10 spread and 60-second maximum book age.
The browser and StrategySpec cannot raise them. Fee-inclusive exposure includes open costs
and paid position fees. Decisions use actual simulated holdings and pending reservations;
future execution/settlement cannot affect an earlier decision.

After an eligible decision, the worker waits at least one second and makes another bounded
public book/series capture, for at most ten contracts. It saves original receipt times.
Only later sized receipts within the cycle, before close, can execute. Missing, future,
crossed or mismatched books refuse. Sources, features and probabilities stay frozen at the
original decision. Price improvement is clamped to the decision touch. Each consumed side's
payload/sequence has durable remaining capacity; another receipt time, opposite-side change
or reappearance of an old payload cannot replenish it. A changed side/sequence supplies a
new snapshot assumption. Public snapshots cannot prove actual queue replenishment.

Execution selects fees again at the later receipt and checks captured series conflicts.
It applies the existing risk engine to actual account exposure with the strategy's minimum
net edge enforced again after costs. Worst-case full-intention costs must fit the original
cash/monetary caps. Smaller available depth may explicitly reduce IOC size; intended,
approved and unsubmitted quantities are saved. FOK refuses such a reduction. PaperBroker
records exact taker fills and per-fill rounded fees; any remainder cancels. No queue,
maker fill or subsequent market impact is invented. Open positions are valued at cost,
so displayed equity is not mark-to-market or an empirical performance measurement.

After risk sizing, an additional `execution_net_edge` check uses the executable quantity,
the broker's exact planned slices and the sum of the individually rounded taker fees.
It preserves the original uncertainty/slippage/latency reserves and compares total expected
net value with minimum edge times executable quantity, avoiding an upward-rounded edge
at the threshold. A fractional or integer reduction cannot spread its rounded fee across
the larger original intention. The audit retains `fill_plan` prices, quantities, cost and
fees even when this check refuses execution; refusal records no paper order or fill.
New cycles freeze `shadow-paper-inputs-v2`. Safe v1 accounting exports reproduce with their
original audit shape after passing the corrected gate. Unsafe legacy fills fail replay;
historical results, references and receipts are never rewritten to make them pass.

Official reconciliation still validates original contract terms, final non-provisional
binary result, payout, settlement time and raw receipt. Accounting settles only when that
outcome is available locally, retains the original official settlement time separately and
guards duplicate/conflicting outcomes. Exceptional/scalar/changed or unresolved results
cannot create a payout. Previously accepted finalized outcomes are not automatically
revised; later exchange corrections require review. Hold-to-settlement remains the supported
monitoring exit mode.

Cycle completion and the account snapshot share one SQLite transaction and previous-state
check. Repeated completion is idempotent. A paused/interrupted worker cannot commit late
fills. Restart retains balances, positions, consumed depth and settlement identities. A
missing/corrupt snapshot or mismatch with the latest committed cycle refuses to reset cash.
A worker result written before its transaction is retained as `uncommitted-result.json`
if the runner records the failure. Failed/partial source receipts are preserved; existing
backoff, pause and workspace/cycle budgets remain. This bounds polling, not historical
performance. Durable snapshots grow with the bounded account/cycle history.

The existing workspace snapshot/restore command includes the account table and verifies
each paper transition against frozen inputs. Legacy archives without accounts remain
supported, without backfilling paper activity. To reproduce a downloaded full export offline:

```bash
uv run python -m entropytrade.tracking.accounting /path/to/shadow-export.json
```

This checks cycle digests, account continuity and every deterministic transition. It does
not authenticate downloaded sources. Individual local cycles additionally verify artifact
hashes, capture reference/hash bindings, original decision replay and paper replay with
the existing command:

```bash
uv run python -m entropytrade.tracking.replay data/cache/workbench/shadow/MONITOR/CYCLE
```

Initial receipts resolve under `execution/`; later receipts resolve under `paper-execution/`.
Local replay checks each capture summary, all receipt bytes/hashes, nested fee references
and later books against the successful raw receipts and original receipt clocks. A reference
to the other capture refuses even if the referenced bytes happen to match. This is local
evidence consistency, not external source certification. Earlier evidence remains untouched;
the correction's current-source tests and exact limitations are recorded in the
[review correction](../data/paper-accounting-review/20261031-correction/README.md).

The new browser workflow remains unverified in this environment. Managed Chromium installed,
but launch failed at `crashpad/util/linux/socket.cc:45`, `setsockopt: Operation not permitted`
and SIGTRAP before any page interaction. The initial two-case Playwright invocation produced
two launch-failure traces; it was not relaunched after observing the denial. No screenshots
or browser downloads passed. Run the executable harness in a permitted environment with
fresh evidence and workspace paths under this repository:

```bash
cd frontend/browser
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" npm run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE=/absolute/repo/data/paper-review/NEW \
ENTROPYTRADE_BROWSER_WORKSPACE=/absolute/repo/data/cache/paper-review-NEW \
npm run test:paper
```

It opens the actual localhost website, inspects controlled synthetic and authentic blocked
accounts, saves screenshots, downloads account/evidence JSON, checks offline replay and
compares downloads after server restart. It stops at the first failure, with no retry or
personal browser fallback. A permitted run of both procedures and the complete pytest suite
remains a supervisor/human acceptance step. Full current results and exact environment
failures are in [the evidence bundle](../data/paper-accounting-review/20261031/README.md).
V1 still needs authentic fitted models/labels, certified fee evidence, empirical two-family
validation, authorized provider evidence and independent release review. Bitcoin boundaries
stay frozen; no additional family is selected.
