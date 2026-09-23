# Auditor eval (synthetic bills)

Seed 42, 2000 bills: 1286 with a detectable planted error, 129 with an error no single bill can reveal, 585 clean.
Synthetic data tests the auditor's logic - it is not a real-world accuracy claim.

| Metric | Value |
|---|---|
| Detection rate (detectable errors) | 100.0% |
| Localisation rate (right check fired) | 100.0% |
| False-positive rate (clean bills) | 0.0% |

| Error type | Expected check | n | Detected | Localised |
|---|---|---|---|---|
| gst_inflated | gst_on_energy | 161 | 100.0% | 100.0% |
| wrong_ed_rate | electricity_duty | 149 | 100.0% | 100.0% |
| fpa_on_wrong_month | fpa_units_vs_history | 144 | 100.0% | 100.0% |
| fpa_line_inflated | fpa_line | 137 | 100.0% | 100.0% |
| current_bill_arithmetic | legacy_current_bill | 126 | 100.0% | 100.0% |
| arrears_not_in_history | arrears_vs_history | 153 | 100.0% | 100.0% |
| lp_surcharge_mismatch | payable_after_due | 140 | 100.0% | 100.0% |
| units_not_matching_meter | register_units | 134 | 100.0% | 100.0% |
| protected_billed_as_unprotected | tariff_rates | 48 | 100.0% | 100.0% |
| next_slab_rate | tariff_rates | 94 | 100.0% | 100.0% |
| inflated_meter_reading | _(undetectable on one bill)_ | 129 | 0.0% | 0.0% |
