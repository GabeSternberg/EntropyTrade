# Research-to-experiment report

Data: synthetic. Research run: 00000000-0000-0000-0000-000000000fa0
Final holdout: not evaluated. No trading authorization.

mentions: BACKTESTED
Completed deterministic validation experiment.
Forecast metrics: {"brier": 0.1875, "calibration_intercept": 0.4979504978398706, "calibration_slope": 0.5468420610057607, "contracts": 20, "independent_date_blocks": 20, "independent_events": 20, "log_loss": 0.5623351446188084, "predictions": 20, "reliability_bins": [{"lower": 0.7, "observed": 0.75, "predicted": 0.75, "predictions": 20}], "status": "evaluated"}
base: fills=20, net P&L=4.200000, fees=0.800000; modeled fills.
unsupported: UNSUPPORTED
hedging is not implemented

Each candidate/scenario counts as a trial. Intervals are descriptive after selection.
Snapshot fills model taker execution, not queues or observed fills.
Synthetic results verify software only; ranking is not deployment authorization.
