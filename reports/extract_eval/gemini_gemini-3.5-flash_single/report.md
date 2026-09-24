# Extraction eval - gemini:gemini-3.5-flash (verify loop: off)

7 real bill photos vs hand-verified labels; 0 read, 7 failed at the API.

| Metric | Value |
|---|---|
| API errors (quota / overload - not reading errors) | 100.0% |
| Field accuracy (bills read) | 0.0% |
| Key-field accuracy (pay, due date, arrears, tariff...) | 0.0% |
| Extracted bill reconciles (bills read) | 0.0% |
| Mean attempts | 1.00 |
| Mean time per bill | 227.0 s |

| Layout | Field accuracy |
|---|---|

| Bill | Fields | Accuracy | Key fields | Reconciles | Attempts | Wrong (first 5) |
|---|---|---|---|---|---|---|
| iesco-2019-07 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| iesco-2021-01 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| iesco-2023-03 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| pesco-2026-03 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| pesco-2026-07 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| pesco-2026-08 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
| pesco-2026-09 | - | - | - | - | 1 | API ERROR: gemini:gemini-3.5-flash HTTP 429: [{ "error": { "code": 429, "message": "You exceeded your current quota, please check your plan and billing details. For more i |
