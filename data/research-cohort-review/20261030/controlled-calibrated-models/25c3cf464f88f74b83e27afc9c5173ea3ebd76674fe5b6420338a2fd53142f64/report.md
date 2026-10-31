# Probability modeling evaluation

Data kind: **real**.
Status: **evaluated**.
Independent events: 200.
Eligible forecast events: 200.
Metrics use independent-event weights; held-out dates are never used in fitting.

Forecast evaluation only; no fills, fees, trading P&L or strategy promotion.

Source-matched scalar-label events: 180.
Independent date blocks: 100.
Missing forecast rows: 0.
Unknown historic rule rows: 0.
Final holdout evaluated: False.

| Model | Split | Events | Brier | Log loss |
| --- | --- | ---: | ---: | ---: |
| climatology | validation | 60 | 0.2500 | 0.6931 |
| raw_forecast | validation | 60 | 0.0600 | 0.2315 |
| forecast_error | validation | 60 | 0.1017 | 0.3437 |
| ridge | validation | 60 | 0.0223 | 0.0707 |

boosting refused: boosting: 96 independent events < 200.

Full reliability, calibration, coverage and walk-forward diagnostics: results.json.
