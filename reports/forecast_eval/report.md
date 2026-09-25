# Forecast eval

3 conventional A-1a bills.

## 1. Backtest (same household, forecast vs actual)

**n = 0 - not measured.** No two bills come from the same connection a year apart, so there is nothing to score the forecast against yet. Needed: bills from the same household 6-12 months apart (each pair adds up to 12 scored months).

## 2. Seasonality across households

| Pair | Correlation of monthly profiles |
|---|---|
| iesco-web-a vs iesco-web-b | +0.89 |
| iesco-web-a vs iesco-web-c | -0.49 |
| iesco-web-b vs iesco-web-c | -0.48 |

Peak month per household: iesco-web-a: 8, iesco-web-b: 9, iesco-web-c: 1

## 3. Cost engine reproduces printed energy charges

| Bill | Units | Computed | Printed | OK |
|---|---|---|---|---|
| iesco-2019-07 | 203 | 1652.60 | 1652.60 | yes |
| iesco-2021-01 | 58 | 335.82 | 335.82 | yes |
| iesco-2023-03 | 393 | 10033.29 | 10033 | yes |

## 4. Solar: monthly amounts rebuilt from the balance history

6 / 6 months match the bill of that month.

## 5. Solar: last year's rupees as this year's forecast

| Month | Last year | Actual |
|---|---|---|
| 2026-04 | 1,078 | 3,441 |
| 2026-05 | 1,215 | 2,787 |
| 2026-06 | -76,801 | -47,682 |
| 2026-07 | 1,180 | 3,170 |
| 2026-08 | 1,180 | 3,273 |
| 2026-09 | -19,289 | -19,285 |

Total over 6 months: forecast -91,437, actual -54,296 (-68%). The pattern changed in 2026: months without a settlement cost 2-3x more, and June's settlement was smaller (fewer net units, less per unit). The timing matches the Feb-2026 rules, but one household can't separate rules from usage - so the outlook reports the last 12 months instead of forecasting solar rupees from them.

## 6. Solar: settlement hypothesis (secondary rates)

| Cycle | Predicted energy | Actual energy | Error |
|---|---|---|---|
| 2026-07 to 2026-09 | -23441 | -22016 | 6.5% |
