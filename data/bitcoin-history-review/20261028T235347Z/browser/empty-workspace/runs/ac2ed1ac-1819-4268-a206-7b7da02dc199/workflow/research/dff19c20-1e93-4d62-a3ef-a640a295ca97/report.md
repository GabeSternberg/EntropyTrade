# Agent research report

Mode: local_templates; run: dff19c20-1e93-4d62-a3ef-a640a295ca97
Question: Test scaled_moneyness > 0

Known data (protected dates excluded):
0 independent events across 0 dates; 0 contracts; 0 eligible feature events; 0 source-matched outcome-label events.
No backtest was run. No predictive or trading edge is established.

Candidate hypotheses (unverified agent proposals):

template-c0: REJECTED
The requested signal scaled_moneyness may improve contract probabilities.
Falsification: Reject without validation improvement and fee-aware depth evidence.
Reasons: hypothesis market family is absent from the permitted universe; No actual listed contracts are available in the captured evidence; no point-in-time observations for scaled_moneyness; required real fitted probability artifact is unavailable; model validation coverage is not permitted by the research cutoff; no certified decision-time coverage for source coinbase; historical rules and settlement semantics are not certified; insufficient independent eligible events/source-matched scalar labels; no executable historical depth; candles/prints cannot establish fills
Critic: Local rule checks only; independent evidence and experiment gates apply.
Previously searched: False

template-c1: REJECTED
An event-weighted training frequency may be more stable than a moneyness regression.
Falsification: Reject without validation improvement and fee-aware depth evidence.
Reasons: hypothesis market family is absent from the permitted universe; No actual listed contracts are available in the captured evidence; no point-in-time observations for hours_to_close; no point-in-time observations for scaled_moneyness; required real fitted probability artifact is unavailable; model validation coverage is not permitted by the research cutoff; no certified decision-time coverage for source coinbase; historical rules and settlement semantics are not certified; insufficient independent eligible events/source-matched scalar labels; no executable historical depth; candles/prints cannot establish fills
Critic: Local rule checks only; independent evidence and experiment gates apply.
Previously searched: False

Next experiments: collect certified decision-time source vintages and actual rule snapshots; obtain the contract's named settlement source; accumulate independent events; fit/calibrate through temporal gates before execution experiments.
Candidate readiness does not imply profitability, validation or permission to trade.
