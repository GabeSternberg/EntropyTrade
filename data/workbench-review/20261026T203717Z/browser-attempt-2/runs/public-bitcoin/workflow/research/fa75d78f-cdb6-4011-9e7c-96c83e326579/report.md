# Agent research report

Mode: local_templates; run: fa75d78f-cdb6-4011-9e7c-96c83e326579
Question: Does Bitcoin spot relative to the actual strike help estimate KXBTC probabilities?

Known data (protected dates excluded):
3 independent events across 3 dates; 210 contracts; 3 eligible feature events; 0 source-matched outcome-label events.
No backtest was run. No predictive or trading edge is established.

Candidate hypotheses (unverified agent proposals):

template-c0: INSUFFICIENT_DATA
The requested signal spot_minus_floor_usd may improve contract probabilities.
Falsification: Reject without validation improvement and fee-aware depth evidence.
Reasons: required real fitted probability artifact is unavailable; model validation coverage is not permitted by the research cutoff; historical rules and settlement semantics are not certified; settlement authority is not established by contract text; insufficient independent eligible events/source-matched scalar labels; no executable historical depth; candles/prints cannot establish fills
Critic: Local rule checks only; independent evidence and experiment gates apply.
Previously searched: False

template-c1: INSUFFICIENT_DATA
A forecast-error baseline may be more stable than regression for this signal.
Falsification: Reject without validation improvement and fee-aware depth evidence.
Reasons: required real fitted probability artifact is unavailable; model validation coverage is not permitted by the research cutoff; historical rules and settlement semantics are not certified; settlement authority is not established by contract text; insufficient independent eligible events/source-matched scalar labels; no executable historical depth; candles/prints cannot establish fills
Critic: Local rule checks only; independent evidence and experiment gates apply.
Previously searched: False

Next experiments: collect certified decision-time source vintages and actual rule snapshots; obtain the contract's named settlement source; accumulate independent events; fit/calibrate through temporal gates before execution experiments.
Candidate readiness does not imply profitability, validation or permission to trade.
