# 12-month outlook (milestone 5a/5b)

`uv run rehnuma-forecast <bill.json> [--lang en] [--table]` · eval: `uv run rehnuma-eval-forecast`

For a flat-tariff (A-1a) household: the next 12 months of units, what they cost at today's
rates, and the months where a small cut is worth a lot because of the 200-unit protected
limit and the slab edges.

## Method

**Units: same month last year.** Every bill prints the last 12 months, so this is always
available. The range shown for each month is the lowest and highest of last year's month
and its two neighbours (a hot spell a few weeks early or late moves units between months).
No trend or level adjustment: nothing in our data can show whether one helps.

**Why the household's own months, not a national profile.** Monthly profiles of our three
IESCO households (units / yearly mean):

| Pair | Correlation |
|---|---|
| household a vs b | +0.89 |
| household a vs c | -0.49 |
| household b vs c | -0.48 |

a and b peak in August/September (air-conditioning); c peaks in January (likely electric
heating). A shared profile would forecast household c backwards.

**Rupees.** Each month is priced with the same slab engine the auditor uses, plus electricity
duty and GST with the functions that reproduce real bills. Protected status is re-decided
every month from the six months before it - including forecast months - so one month over
200 costs protected rates for the next six, as the rule works. The fixed charge per
sanctioned kW (secondary source) is added untaxed as its own line. Not included, and said so
to the user: fuel adjustment, quarterly adjustments, TV fee.

**Where a cut is worth it.** A month is "in reach" of a slab edge (100, 200, ... 700) if it is
at most 15% over it. For each such month the whole 12-month cost path is re-run with that
month held at the edge; the difference is the saving, and saving / units cut is the leverage.
The advice only says "keeps protected rates" when later months actually become protected.

Example (iesco-2021-01, 2026 rates): June forecast 211 units. Holding it at 200 saves about
Rs 13,130 - about **Rs 1,190 per unit not used** - because July and August stay protected.
A normal unit costs Rs 10-50.

## Eval (`reports/forecast_eval/report.md`)

| Part | Result |
|---|---|
| Backtest: forecast vs actual, same household | **n = 0 - not measured.** The three IESCO bills are three different households; no household has two bills a year apart. |
| Seasonality across households | +0.89 / -0.49 / -0.48 (table above) |
| Cost engine reproduces the printed energy charge of each real bill | 3 / 3 (gated in CI) |

What would give the backtest a number: bills from the same household 6-12 months apart. Each
pair scores up to 12 months (MAE, MAPE, share inside the range, and recall/precision of the
over-200 warnings). The eval picks pairs up automatically by `connection_id`.

## Bugs found while building it

- **The first draft claimed "keeps protected rates" for every month over 200.** For
  iesco-2019-07, August (207) came right after July (203): the household was already
  unprotected, and holding August at 200 only protects one later month. The claim now
  depends on the counted months (`protected_gained`), with a test on that exact case.
- **A heavy user was told to cut 558 units to 200.** The first counterfactual capped every
  month over 200 ("save Rs 175,017"). Advice is now limited to months within 15% of an edge,
  and a household over 200 all year is told protected rates are out of reach.

## Known limits

- Accuracy is unmeasured until same-household bill pairs exist (above).
- Protection effects past the 12-month window are not counted (iesco-2019-07: holding July
  2020 at 200 would protect months after the window; the outlook prices only the edge).
- Per-month savings are not additive; the "all together" figure is its own re-run.
- 2026 A-1a rates are from secondary sources; fixed-charge tax treatment is unconfirmed.
- Only flat A-1a households. Time-of-use (A-1b) and solar households come next (5c).
