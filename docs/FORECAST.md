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
- Only flat A-1a households get the 12-month forecast. Solar households get the section below.

# Solar households (milestone 5c)

`uv run rehnuma-forecast data/labels/real --lang en` (the folder, so a bill can find the
other bills of its billing cycle).

## What happened - no rates needed

The history table prints the account balance each month. A month's amount is this month's
balance minus last month's (payments added back); settlement months are where banked units
were cashed out. Your family's last 12 months (to Sep 2026): **Rs 10,760 credited overall** -
settlements of Rs 16,000 (Dec), Rs 47,680 (Jun) and Rs 19,290 (Sep), against Rs 56,880 for
January and February 2026, when more was used than sent back and the units were billed.

Checked: every month rebuilt from one bill's history equals what that month's own bill says
(6 / 6, gated in CI).

**Bug found while building it:** the bill's own month first used "current bill" - for Mar-26
that is -872, but the balance moved +292 because the Rs 1,164 fuel adjustment is billed on
top. The next bills' history shows +292, so the own month now uses the change in payable.

## Why there is no rupee forecast for solar

"Same month last year" in rupees, scored on the six months the history covers twice
(Apr-Sep 2026): forecast -91,437, actual -54,296 (**-68%**). Months without a settlement cost
2-3x more in 2026 (about Rs 1,180 -> 3,220), and June's settlement was smaller (2,151 net units
vs 3,005, and less per unit). The timing matches the Feb-2026 rules, but one household can't
separate rules from usage, so the outlook reports the last 12 months instead of forecasting.

## At renewal (reg. 21(2))

Agreements signed before the Prosumer Regulations 2026 keep the old terms until they end;
renewals move to net billing (reg. 14): every imported unit at the tariff, every exported unit
at the energy purchase price. Priced on the family's REAL Jul-Sep 2026 meter readings (1,768
units taken, 3,088 sent back) with the bills' REAL charges on the other side: about
Rs 41,590-47,770 for that quarter instead of a Rs 13,820 credit - **Rs 55,420-61,590 more for one
summer quarter.** Fixed charges are taken from the in-cycle months and assumed unchanged.

Rates (`src/rehnuma/data/solar_rates.json`), all secondary: energy purchase price Rs 9-11
(Express Tribune 9 Feb 2026; Dawn), national average power purchase price Rs 25.9 (Tribune),
A-1b off-peak Rs 34.53 / peak Rs 46.85 (S.R.O. 279(I)/2026 via ebillpakistan.pk).

**Settlement hypothesis** (eval part 6): "off-peak imports netted 1:1 against exports inside
the cycle, surplus paid at the power purchase price, peak imports at the peak rate" explains
the Jul-Sep 2026 cycle's energy credit within **6.5%** (predicted -23,441, actual -22,016).
Close, not exact - the rates are secondary and the fixed charge is inferred - so it is
reported, not used to bill anyone.
