# Findings from real bills

Observations from 4 real PESCO bills (Mar, Jul, Aug, Sep 2026) of one net-metering
household (9.5 kW solar, tariff A-1b(03)T, 7 kW sanctioned load).
Each one is either verified by a test or listed as an open question.

## Verified

1. **PESCO changed its bill layout between Mar-2026 and Jul-2026.**
   The legacy PITC-style bill was replaced by a redesigned one (QR code, "Bill Charges
   Breakdown"). A template-based parser would have silently broken. → the schema carries a
   `layout` field and evals will be reported per layout.

2. **Every bill reconciles to within Rs 1.** Arrears + current bill (+ Total FPA on the legacy
   layout) equals the printed payable amount exactly on all four bills.

3. **Bills show Rs 1 rounding gaps between lines.** Jul-26: charges 2,687 + taxes 484 = 3,171,
   printed current bill 3,170. → tolerance is Rs 1, and near-misses are always *reported*,
   never hidden. (`test_known_rs1_rounding_gap_is_reported_not_hidden`)

4. **Real anomaly: the Mar-26 FPA lines don't add up to the Total FPA.** Printed:
   FPA 972 + GST on FPA 178 + ED on FPA **16** (verified on paper) = 1,166, but Total FPA is
   printed as **1,164**, a Rs 2 gap that exceeds rounding tolerance.
   The total is reproduced exactly by computing unrounded and rounding once:
   (597 × 1.6274) × 1.015 × 1.18 = 1,163.63 → **1,164**, which implies ED ≈ 14.57, not 16.
   A brute-force search (ED 1.00–2.50%, GST on FPA or FPA+ED, rounded/unrounded FPA) found
   **no rule** that prints ED 16, GST 178 and total 1,164 together, so the bill contradicts
   itself. The engine flags it, and it is recorded in `data/eval/expected_anomalies.json`.
   Tests require every real bill to fail *exactly* its documented anomalies.
   (`test_fpa_total_follows_unrounded_cascade_not_printed_lines`)
   *How it was found:* the first transcription read ED as 15 and everything passed; the owner
   checked the paper bill, corrected it to 16, and the check failed. The label was
   corrected, not the tolerance.

5. **Net metering banks units across a 3-month cycle.** `Mnt Cnt` runs 1/3 → 2/3 → 3/3.
   Inside the cycle, remaining = previous remaining − net (off-peak 0 → 834 → 1,326); at 3/3 the
   bank settles and resets to 0 (Sep-26: Rs 19,285 credit).

6. **Bills are consistent with each other.** Meter readings carry forward exactly, arrears
   equal last month's payable, and the 12-month history tables agree across bills.

## Design consequences

- **The bill-history "units" column cannot be used as consumption for net-metering users.**
  It shows *net* units, and months inside a cycle show 0 (Jul-26, Aug-26). Forecasting for
  prosumers must use the import/export registers, one bill at a time.
- **Conventional households need their own path.** No real conventional bill yet; a synthetic
  one guards that path in tests until we collect real ones.

## Open questions (milestone 2)

- **Q1-2026 vs Q3-2026 behave differently.** Jan-26 (597) and Feb-26 (383) show billed units
  inside the cycle and Mar-26 starts with an empty bank, but Jul/Aug-26 carry units forward.
  Seasonal rule (import > export gets billed monthly)? Or a rule change under the Feb-2026
  NEPRA Prosumer Regulations? Needs the regulation text.
- **Implied netting value.** Mar-26: −3,012 for −204 net units ≈ Rs 14.76/kWh. What rate is
  that? Verify against NEPRA tariffs before claiming anything.
- **The `SS` status on Nov-25** — meaning unknown.
- **ED 1.5% is read from the bill header, not yet sourced.** GST is now a dated schedule in
  `engine/taxes.py` (18% from 14-Feb-2023).
- **Prediction to test when the Oct-26 bill arrives:** history row for Sep-26 should show net
  units of about −1,320 (off-peak −1,833, peak +513).


---

# Findings from IESCO bills (conventional, 2019 / 2021 / 2023)

Three web-generated IESCO bills of three different non-solar households (A-1a(01)).
Every tax line is now **recomputed from first principles** by `engine/calculator.py`
and matches the printed value with **zero delta** on all of them.

## Verified rules (each tested against a rejected alternative in `tests/test_calculator.py`)

7. **The PITC legacy layout is shared across DISCOs.** IESCO and PESCO print the same
   bill; the layout is now `pitc_legacy`, not PESCO-specific.
8. **Electricity duty = 1.5% x (cost of electricity + QTA).** FC surcharge is *not* in the
   base (IESCO Mar-23: printed 169; including FC would give 192).
9. **GST = rate x (cost + FC surcharge + QTA + ED)**, at the rate for the bill month:
   17% in 2019/2021, 18% in 2023 (18% took effect 14-Feb-2023).
10. **NJ surcharge = Rs 0.10/kWh** on the 2019 and 2021 bills; absent in 2023.
11. **FPA is charged on the units of an earlier reference month**, and those units match
    the bill's own history table (Jul-19 bill -> May-19's 102 units).
12. **One bill can carry FPA for two months** (Jan-21: Oct-20 and Nov-20).
13. **GST on FPA is rounded to whole rupees per FPA month.** Jan-21: 6 + 8 = 14 as printed;
    rounding once would give 13.
14. **GST on FPA uses the rate of the FPA's reference month.** Mar-23 bill (18% era) taxes
    Jan-23 FPA at 17%: printed 46 (18% would give 49). Consistent with all 4 legacy bills.
15. **Unrounded computation again.** Mar-23 prints cost 10,033 but only the unrounded
    25.53 x 393 = 10,033.29 reproduces ED, GST and the current bill. Same pattern as
    PESCO FPA, so it looks PITC-wide.

## Bugs found while building this

- **Recomputed lines were compared with a flat Rs 1 tolerance.** An injected wrong ED of
  5.41 passed against the printed 5.04 (a 7% error). Tolerance for recomputed lines is now
  one step of the printed precision (Rs 0.01 for paisa, Rs 1 for rupees). Caught by
  `test_ed_on_wrong_base_is_caught`; regression test in `test_rounding.py`.
- **Cross-bill checks grouped bills by (DISCO, tariff, type).** Three different IESCO
  households share all three, so they would have been checked as one meter. Bills now
  carry a pseudonymous `connection_id`. (`test_different_households_are_never_cross_checked`)

## Product idea

Every IESCO bill prints a photo of the meter, and all three match the printed reading
(9509.5 / 4142.9 / 8572). Comparing the meter photo with the printed reading is a
candidate vision feature: wrong or estimated readings are a common source of overbilling.

## Open questions (added)

- **Late-payment surcharge base.** 10% x (cost + FC + ED) fits 2019 and 2021, not 2023
  (1,280 fits 10% x (cost + FC + QTA)). Rule changed, or different base? Needs a source.
- **Status codes.** `LK` (Feb-Mar 2020, likely COVID-era locked/estimated readings) and
  "LK 337.5" (Apr-22), plus `SS` from PESCO. Need an official code list.
- **GST 17% start date** is recorded as Jul-2013 and still needs a primary source.


---

# Tariff schedules, protected status and the auditor eval

## Tariff data quality (a finding in itself)

- Secondary sources disagree. An explainer site lists 2026 slab rates "per S.R.O. 279(I)/2026"
  (effective 12-Feb-2026), but those per-unit rates are identical to NEPRA's **July-2025**
  decision, while Express Tribune (11-Feb-2026) reports Feb-2026 per-unit **cuts** of
  Rs 0.49–1.53. Both agree on the new per-kW fixed charges.
- So every schedule in `src/rehnuma/data/tariff_schedules.json` carries a `confidence`
  (`official` / `secondary` / `observed`) and a `source`. The 2026 schedule is `secondary`
  until the SRO itself is read. Nothing is `official` yet.

## Slab rules confirmed on real bills

16. **2019: every consumer got one-previous-slab benefit** (IESCO Jul-19: 8.11 x 200 + 10.20 x 3).
17. **2023: unprotected consumers pay the rate of the slab reached on every unit** (IESCO Mar-23:
    25.53 x 393). Only protected consumers keep the one-previous-slab benefit.
18. The 2023 household's last 6 months were all above 200 units, so the engine independently
    classifies it as unprotected, matching what was charged.

The rates in the `observed` schedules came from these same bills, so these tests check the
slab *structure* (which units get which rate), not the rates themselves.

## Auditor eval (synthetic) — `uv run rehnuma-eval-auditor`

Seed 42, 2,000 bills: 100% detection, 100% localisation, 0% false positives. Also 100% on
seeds 7 and 2026.

**How to read that 100%:** the generator and the auditor share `calculator.py`, so on synthetic
data the auditor is checking bills built from its own rules. The number mainly shows that every
error type is wired to a check that fires for the right reason, and that clean bills produce no
false alarms. It is **not** a real-world accuracy figure. That needs the vision extractor
(milestone 3) running on real bills.

What the eval did find:

- **A bug in the generator, not the auditor.** The first run missed 2/81 `fpa_on_wrong_month`
  bills. On both, the "wrong" month had the same units as the right one (98 vs 98, 50 vs 50),
  so no error had actually been planted. Fixed, and the eval now refuses to count any planted
  error that leaves the bill unchanged.
- **A class of error no single bill can reveal.** An inflated meter reading makes the whole bill
  consistent (0% detected, by design). Catching it needs the next month's reading
  (cross-bill continuity, already built) or the meter photo (milestone 3).