# Probability modeling evaluation

Data kind: **synthetic**.
Status: **evaluated**.
Independent events: 480.
Eligible forecast events: 480.
Metrics use independent-event weights; held-out dates are never used in fitting.

Forecast evaluation only; no fills, fees, trading P&L or strategy promotion.

Source-matched scalar-label events: 480.
Independent date blocks: 240.
Missing forecast rows: 0.
Unknown historic rule rows: 0.
Final holdout evaluated: False.

| Model | Split | Events | Brier | Log loss |
| --- | --- | ---: | ---: | ---: |
| climatology | validation | 96 | 0.1814 | 0.5094 |
| raw_forecast | validation | 96 | 0.0415 | 0.1263 |
| forecast_error | validation | 96 | 0.0416 | 0.1263 |
| ridge | validation | 96 | 0.0354 | 0.1111 |
| boosting | validation | 96 | 0.0412 | 0.1530 |

Full reliability, calibration, coverage and walk-forward diagnostics: results.json.
