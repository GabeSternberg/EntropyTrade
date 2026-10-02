# Chicago daily high

This note records the stored Chicago scores. It does not fit a model.
Four rules were tried. None was promoted. Fidelity is `trade-print`.
Optimistic trade-print equity is not a fill. Base and conservative never
take one.

The bracket is 80 to 81 inclusive. The price threshold is 0.40. The midpoint
is 80.5. The decision is 15:00 UTC. The window is the 40 stored CLI days.
11 of the 40 B80.5 markets exist. The other 29 are not_found. Those strikes
were not replaced.

## Full window

| Rule | Optimistic fills | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- |
| forecast_inside | 1 | 100.750000 | 100.000000 | 100.000000 |
| forecast_above | 2 | 99.400000 | 100.000000 | 100.000000 |
| forecast_below | 1 | 99.660000 | 100.000000 | 100.000000 |
| forecast_gap | 7 | 102.430000 | 100.000000 | 100.000000 |

## Walk-forward

The split is train 20, validation 10, holdout 10. The holdout is not scored.
The full-window gap equity is not a threshold.

| Split | Rule | Fires | Agreements | Optimistic fills | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | forecast_inside | 2 | 1 | 1 | 100.750000 | 100.000000 | 100.000000 |
| train | forecast_above | 14 | 10 | 2 | 99.400000 | 100.000000 | 100.000000 |
| train | forecast_below | 4 | 3 | 1 | 99.660000 | 100.000000 | 100.000000 |
| train | forecast_gap | 16 | 5 | 6 | 102.510000 | 100.000000 | 100.000000 |
| validation | forecast_inside | 0 | 0 | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_above | 3 | 2 | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_below | 7 | 6 | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_gap | 3 | 0 | 1 | 99.920000 | 100.000000 | 100.000000 |

Nothing in the train split or the validation split was promoted.
