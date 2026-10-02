# Philadelphia daily high

This note records the stored Philadelphia scores. It does not fit a model.
Four rules were tried. None was promoted. Fidelity is `trade-print`. A print
is not a guaranteed fill. Base and conservative never take one.

The bracket is 80 to 81 inclusive. The price threshold is 0.40. The midpoint
is 80.5. The decision is 15:00 UTC. The window is the 40 stored CLI days.

## Full window

| Rule | Optimistic fills | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- |
| forecast_inside | 0 | 100.000000 | 100.000000 | 100.000000 |
| forecast_above | 0 | 100.000000 | 100.000000 | 100.000000 |
| forecast_below | 0 | 100.000000 | 100.000000 | 100.000000 |
| forecast_gap | 3 | 99.900000 | 100.000000 | 100.000000 |

## Walk-forward

The split is train 20, validation 10, holdout 10. The holdout is not scored.

| Split | Rule | Optimistic fills | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- | --- |
| train | forecast_inside | 0 | 100.000000 | 100.000000 | 100.000000 |
| train | forecast_above | 0 | 100.000000 | 100.000000 | 100.000000 |
| train | forecast_below | 0 | 100.000000 | 100.000000 | 100.000000 |
| train | forecast_gap | 2 | 99.910000 | 100.000000 | 100.000000 |
| validation | forecast_inside | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_above | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_below | 0 | 100.000000 | 100.000000 | 100.000000 |
| validation | forecast_gap | 1 | 99.990000 | 100.000000 | 100.000000 |

Nothing in the train split or the validation split was promoted.
