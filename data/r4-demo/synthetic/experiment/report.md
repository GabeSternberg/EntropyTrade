# Research-to-experiment report

Data: synthetic. Research run: c115f9e2-7584-46d4-afe5-eae45f5f4809
Final holdout: not evaluated. No trading authorization.

c0: REJECTED
too few modeled fills for trading evidence
Forecast metrics: {"brier": 0.02307350422979906, "calibration_intercept": 1.1435494474439708e-05, "calibration_slope": 1.8493738410534841, "contracts": 192, "independent_date_blocks": 48, "independent_events": 48, "log_loss": 0.08046581697510276, "predictions": 192, "reliability_bins": [{"lower": 0.0, "observed": 0.0, "predicted": 0.004758361909288973, "predictions": 127}, {"lower": 0.1, "observed": 0.0, "predicted": 0.12836299139910595, "predictions": 5}, {"lower": 0.2, "observed": 0.25, "predicted": 0.269661249924119, "predictions": 8}, {"lower": 0.3, "observed": 0.0, "predicted": 0.3097223933855613, "predictions": 2}, {"lower": 0.4, "observed": 0.0, "predicted": 0.4496862211999622, "predictions": 2}, {"lower": 0.5, "observed": 1.0, "predicted": 0.5503137788000355, "predictions": 2}, {"lower": 0.6, "observed": 1.0, "predicted": 0.6902776066144102, "predictions": 2}, {"lower": 0.7, "observed": 0.75, "predicted": 0.7303387500757903, "predictions": 8}, {"lower": 0.8, "observed": 1.0, "predicted": 0.8716370085965235, "predictions": 5}, {"lower": 0.9, "observed": 1.0, "predicted": 0.9805060657271917, "predictions": 31}], "status": "evaluated"}
optimistic: fills=6, net P&L=1.730000, fees=0.100000; modeled fills.
base: fills=6, net P&L=1.730000, fees=0.100000; modeled fills.
conservative: fills=0, net P&L=0.000000, fees=0.000000; modeled fills.
c1: BACKTESTED
Completed deterministic validation experiment.
Forecast metrics: {"brier": 0.02307350422979906, "calibration_intercept": 1.1435494474439708e-05, "calibration_slope": 1.8493738410534841, "contracts": 192, "independent_date_blocks": 48, "independent_events": 48, "log_loss": 0.08046581697510276, "predictions": 192, "reliability_bins": [{"lower": 0.0, "observed": 0.0, "predicted": 0.004758361909288973, "predictions": 127}, {"lower": 0.1, "observed": 0.0, "predicted": 0.12836299139910595, "predictions": 5}, {"lower": 0.2, "observed": 0.25, "predicted": 0.269661249924119, "predictions": 8}, {"lower": 0.3, "observed": 0.0, "predicted": 0.3097223933855613, "predictions": 2}, {"lower": 0.4, "observed": 0.0, "predicted": 0.4496862211999622, "predictions": 2}, {"lower": 0.5, "observed": 1.0, "predicted": 0.5503137788000355, "predictions": 2}, {"lower": 0.6, "observed": 1.0, "predicted": 0.6902776066144102, "predictions": 2}, {"lower": 0.7, "observed": 0.75, "predicted": 0.7303387500757903, "predictions": 8}, {"lower": 0.8, "observed": 1.0, "predicted": 0.8716370085965235, "predictions": 5}, {"lower": 0.9, "observed": 1.0, "predicted": 0.9805060657271917, "predictions": 31}], "status": "evaluated"}
optimistic: fills=11, net P&L=3.340000, fees=0.190000; modeled fills.
base: fills=11, net P&L=3.340000, fees=0.190000; modeled fills.
conservative: fills=0, net P&L=0.000000, fees=0.000000; modeled fills.
c2: UNSUPPORTED
no executable StrategySpec was supplied
negative-control: REJECTED
too few modeled fills for trading evidence
Forecast metrics: {"brier": 0.02307350422979906, "calibration_intercept": 1.1435494474439708e-05, "calibration_slope": 1.8493738410534841, "contracts": 192, "independent_date_blocks": 48, "independent_events": 48, "log_loss": 0.08046581697510276, "predictions": 192, "reliability_bins": [{"lower": 0.0, "observed": 0.0, "predicted": 0.004758361909288973, "predictions": 127}, {"lower": 0.1, "observed": 0.0, "predicted": 0.12836299139910595, "predictions": 5}, {"lower": 0.2, "observed": 0.25, "predicted": 0.269661249924119, "predictions": 8}, {"lower": 0.3, "observed": 0.0, "predicted": 0.3097223933855613, "predictions": 2}, {"lower": 0.4, "observed": 0.0, "predicted": 0.4496862211999622, "predictions": 2}, {"lower": 0.5, "observed": 1.0, "predicted": 0.5503137788000355, "predictions": 2}, {"lower": 0.6, "observed": 1.0, "predicted": 0.6902776066144102, "predictions": 2}, {"lower": 0.7, "observed": 0.75, "predicted": 0.7303387500757903, "predictions": 8}, {"lower": 0.8, "observed": 1.0, "predicted": 0.8716370085965235, "predictions": 5}, {"lower": 0.9, "observed": 1.0, "predicted": 0.9805060657271917, "predictions": 31}], "status": "evaluated"}
optimistic: fills=0, net P&L=0.000000, fees=0.000000; modeled fills.
base: fills=0, net P&L=0.000000, fees=0.000000; modeled fills.
conservative: fills=0, net P&L=0.000000, fees=0.000000; modeled fills.

Each candidate/scenario counts as a trial. Intervals are descriptive after selection.
Snapshot fills model taker execution, not queues or observed fills.
Synthetic results verify software only; ranking is not deployment authorization.
