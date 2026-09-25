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
