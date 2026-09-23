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
- **GST 18% and ED 1.5% are inferred** (they reproduce the bill exactly), not yet sourced.
- **Prediction to test when the Oct-26 bill arrives:** history row for Sep-26 should show net
  units of about −1,320 (off-peak −1,833, peak +513).
