# KXHIGH scan

Each ticker is another attempt at the same four rules. The bracket,
the 0.40 print, the 80.5 midpoint, and the 15:00 UTC decision are
unchanged. Train, then validation. The holdout is not scored.
Optimistic trade-print equity is not a fill. Nothing is promoted.

| Ticker | Markets found | Optimistic equity | Validation optimistic equity | Base and conservative |
| --- | --- | --- | --- | --- |
| KXHIGHTVABB | 0 | not scored | not walked | not scored |
| KXHIGHTLTFM | 0 | not scored | not walked | not scored |
| KXHIGHTNOLA | 0 | not scored | not walked | not scored |
| KXHIGHDEN | 7 | 100.000000, 100.000000, 100.000000, 99.620000 | 100.000000, 100.000000, 100.000000, 99.930000 | 100.000000 |
| KXHIGHTEDDB | 0 | not scored | not walked | not scored |
| KXHIGHTSDF | 4 | 99.990000, 100.000000, 99.610000, 99.980000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTBOS | 9 | 99.980000, 100.000000, 99.660000, 100.410000 | 99.980000, 100.000000, 99.660000, 99.980000 | 100.000000 |
| KXHIGHTZBAA | 0 | not scored | not walked | not scored |
| KXHIGHTEBBR | 0 | not scored | not walked | not scored |
| KXHIGHOU | 0 | not scored | not walked | not scored |
| KXHIGHTMIN | 6 | 100.000000, 100.000000, 99.600000, 100.080000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTSFO | 4 | 99.890000, 100.000000, 100.000000, 99.670000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTSAN | 16 | 100.000000, 99.940000, 100.990000, 101.100000 | 100.000000, 100.000000, 100.990000, 100.000000 | 100.000000 |
| KXHIGHTCYYZ | 0 | not scored | not walked | not scored |
| KXHIGHTEDDF | 0 | not scored | not walked | not scored |
| KXHIGHMIA | 0 | not scored | not walked | not scored |
| KXHIGHTPHX | 0 | not scored | not walked | not scored |
| KXHIGHTEGLL | 0 | not scored | not walked | not scored |
| KXHIGHTEMPDEN | 0 | not scored | not walked | not scored |
| KXHIGHNYD | 0 | not scored | not walked | not scored |
| KXHIGHTRKSI | 0 | not scored | not walked | not scored |
| KXHIGHTLFPG | 0 | not scored | not walked | not scored |
| KXHIGHUS | 0 | not scored | not walked | not scored |
| KXHIGHTEWR | 8 | 100.000000, 100.600000, 100.000000, 99.960000 | 100.000000, 100.000000, 100.000000, 99.980000 | 100.000000 |
| KXHIGHTTTN | 9 | 99.820000, 100.970000, 100.000000, 101.000000 | 99.820000, 100.000000, 100.000000, 100.570000 | 100.000000 |
| KXHIGHTZSPD | 0 | not scored | not walked | not scored |
| KXHIGHLAX | 15 | 99.990000, 100.620000, 100.000000, 99.480000 | 100.000000, 100.620000, 100.000000, 99.780000 | 100.000000 |
| KXHIGHTYSSY | 0 | not scored | not walked | not scored |
| KXHIGHTOMDB | 0 | not scored | not walked | not scored |
| KXHIGHTWSSS | 0 | not scored | not walked | not scored |
| KXHIGHTDC | 5 | 100.000000, 100.000000, 100.000000, 101.740000 | 100.000000, 100.000000, 100.000000, 101.810000 | 100.000000 |
| KXHIGHTSEA | 1 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTLV | 2 | 100.000000, 100.000000, 100.000000, 99.980000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTSBGR | 0 | not scored | not walked | not scored |
| KXHIGHTSATX | 0 | not scored | not walked | not scored |
| KXHIGHTRJTT | 0 | not scored | not walked | not scored |
| KXHIGHTATL | 5 | 99.950000, 100.000000, 100.000000, 101.830000 | 100.000000, 100.000000, 100.000000, 100.000000 | 100.000000 |
| KXHIGHTLSGG | 0 | not scored | not walked | not scored |
| KXHIGHTVHHH | 0 | not scored | not walked | not scored |
| KXHIGHTKSAN | 0 | not scored | not walked | not scored |
| KXHIGHTHOU | 0 | not scored | not walked | not scored |

## Revision

The 03:00 and 15:00 vintages are not available, because `run` is
rejected. The later field is `temperature_2m_previous_day1` and the
earlier field is `temperature_2m_previous_day2`. `available_at` is a
rule: 00:00 UTC on the valid day for the later field, and 00:00 UTC
the day before for the earlier field. A print is not a fill. Nothing
was promoted.

Philadelphia `forecast_revision_up`. Train fires: 0. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Chicago `forecast_revision_up`. Train fires: 0. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Philadelphia `forecast_revision_bracket`. Train fires: 1. Train fills: 1. Train optimistic equity: 99.770000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Chicago `forecast_revision_bracket`. Train fires: 7. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 3. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

New York `forecast_revision_bracket`. Train fires: 1. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Austin `forecast_revision_bracket`. Train fires: 1. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Oklahoma City `forecast_revision_bracket`. Train fires: 0. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 1. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Dallas `forecast_revision_bracket`. Train fires: 2. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Denver `forecast_revision_bracket`. Train fires: 2. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 1. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Louisville `forecast_revision_bracket`. Train fires: 1. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 3. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Boston `forecast_revision_bracket`. Train fires: 12. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 5. Validation fills: 1. Validation optimistic equity: 99.980000. Base and conservative equity: 100.000000. Nothing was promoted.

Minneapolis `forecast_revision_bracket`. Train fires: 0. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 1. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

San Francisco `forecast_revision_bracket`. Train fires: 6. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 1. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

San Diego `forecast_revision_bracket`. Train fires: 11. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 1. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Newark `forecast_revision_bracket`. Train fires: 1. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Trenton `forecast_revision_bracket`. Train fires: 2. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.

Los Angeles `forecast_revision_bracket`. Train fires: 6. Train fills: 0. Train optimistic equity: 100.000000. Validation fires: 0. Validation fills: 0. Validation optimistic equity: 100.000000. Base and conservative equity: 100.000000. Nothing was promoted.
