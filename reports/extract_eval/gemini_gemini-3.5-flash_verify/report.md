# Extraction eval - gemini:gemini-3.5-flash (verify loop: on)

7 real bill photos vs hand-verified labels; 6 read, 1 failed at the API.

| Metric | Value |
|---|---|
| API errors (quota / overload - not reading errors) | 14.3% |
| Field accuracy (bills read) | 96.2% |
| Key-field accuracy (pay, due date, arrears, tariff...) | 100.0% |
| Extracted bill reconciles (bills read) | 83.3% |
| Mean attempts | 1.29 |
| Mean time per bill | 44.7 s |

| Layout | Field accuracy |
|---|---|
| pitc_legacy | 97.2% |
| pesco_v2_2026 | 94.1% |

| Bill | Fields | Accuracy | Key fields | Reconciles | Attempts | Wrong (first 5) |
|---|---|---|---|---|---|---|
| iesco-2019-07 | 87 | 96.6% | 100% | yes | 1 | legacy_charges.cost_of_electricity: 1652.60 -> 1652.6; legacy_charges.govt.nj_surcharge: 20.30 -> 20.3; legacy_charges.rate_lines.1.rate: 10.20 -> 10.2 |
| iesco-2021-01 | 93 | 98.9% | 100% | yes | 1 | legacy_charges.govt.nj_surcharge: 5.80 -> 5.8 |
| iesco-2023-03 | 87 | 97.7% | 100% | yes | 1 | legacy_charges.govt.ed_on_fpa: 4 -> 46 |
| pesco-2026-03 | 96 | 95.8% | 100% | no | 3 | sanctioned_load_kw: 7.00 -> 7.0; net_metering.dg_capacity_kw: 9.50 -> 9.5 |
| pesco-2026-07 | 85 | 90.6% | 100% | yes | 1 | sanctioned_load_kw: 7.00 -> 7.0; history.2025-07.bill: -105168 -> -100168; history.2025-08.bill: -103988 -> -103168; history.2025-12.units: -873 -> -872; history.2025-12.bill: -136921 -> -124121 |
| pesco-2026-08 | 85 | 97.6% | 100% | yes | 1 | sanctioned_load_kw: 7.00 -> 7; history.2025-08.bill: -103988 -> 103988 |
| pesco-2026-09 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
