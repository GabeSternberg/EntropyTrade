# Agent research report

Mode: offline_mock; run: c115f9e2-7584-46d4-afe5-eae45f5f4809
Question: Investigate Philadelphia forecast revisions and model disagreement; compare hypotheses and retain negative controls.

Known data (protected dates excluded):
384 independent events across 192 dates; 1536 contracts; 384 eligible feature events; 384 source-matched outcome-label events.
No backtest was run. No predictive or trading edge is established.

Candidate hypotheses (unverified agent proposals):

c0: READY_FOR_EXPERIMENT
Revisions may identify probability changes before market repricing.
Falsification: Reject if there is no reliable out-of-sample improvement across independent dates.
Reasons: 
Critic: Plausible research proposal only; deterministic data and semantics checks must gate any experiment.
Previously searched: True

c1: READY_FOR_EXPERIMENT
Disagreement may flag unreliable probabilities for filtering.
Falsification: Reject if there is no reliable out-of-sample improvement across independent dates.
Reasons: 
Critic: Plausible research proposal only; deterministic data and semantics checks must gate any experiment.
Previously searched: True

c2: UNSUPPORTED
Previously resolved station errors may improve forecast calibration.
Falsification: Reject if there is no reliable out-of-sample improvement across independent dates.
Reasons: experiment-only proposal; comparison orchestration requires R4
Critic: Plausible research proposal only; deterministic data and semantics checks must gate any experiment.
Previously searched: True

negative-control: READY_FOR_EXPERIMENT
An unattainable net edge is a control for execution rejection.
Falsification: Reject any fill that cannot meet the declared net-edge hurdle.
Reasons: 
Critic: This is an explicit software negative control, not a profitability claim.
Previously searched: False

Next experiments: collect certified decision-time source vintages and actual rule snapshots; obtain the contract's named settlement source; accumulate independent events; fit/calibrate through temporal gates before execution experiments.
Candidate readiness does not imply profitability, validation or permission to trade.
