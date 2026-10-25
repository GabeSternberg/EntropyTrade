# Probability modeling evaluation

Data kind: **synthetic**.
Status: **evaluated**.
Independent events: 600.
Eligible forecast events: 600.
Metrics use independent-event weights; held-out dates are never used in fitting.

Forecast evaluation only; no fills, fees, trading P&L or strategy promotion.

Source-matched scalar-label events: 600.
Independent date blocks: 300.
Missing forecast rows: 0.
Unknown historic rule rows: 0.
Final holdout evaluated: True.

| Model | Split | Events | Brier | Log loss |
| --- | --- | ---: | ---: | ---: |
| climatology | validation | 120 | 0.3456 | 1.6831 |
| climatology | holdout | 120 | 0.4020 | 4.0173 |
| raw_forecast | validation | 120 | 0.0359 | 0.1128 |
| raw_forecast | holdout | 120 | 0.0398 | 0.1250 |
| forecast_error | validation | 120 | 0.0365 | 0.1169 |
| forecast_error | holdout | 120 | 0.0388 | 0.1255 |
| ridge | validation | 120 | 0.0297 | 0.0973 |
| ridge | holdout | 120 | 0.0359 | 0.1198 |
| boosting | validation | 120 | 0.0927 | 0.7302 |
| boosting | holdout | 120 | 0.3215 | 2.7226 |

Full reliability, calibration, coverage and walk-forward diagnostics: results.json.
