# Summary eval - groq:allam-2-7b

7 summaries (real bills x languages).

| Metric | Value |
|---|---|
| First draft passed the critic | 14.3% |
| Fell back to template | 57.1% |
| Faithfulness (final) | 100.0% |
| Coverage of must-mention facts (final) | 100.0% |
| Correct language (final) | 100.0% |
| Mean attempts | 2.43 |
| LLM errors (fell back safely) | 0.0% |
| Mean time per summary | 48.6 s |

| Bill | Lang | Source | Attempts | Rejected drafts |
|---|---|---|---|---|
| iesco-2019-07 | ur | template_fallback | 3 | #1: invented 15, missed amount to pay / credit, units used; #2: missed amount to pay / credit, units used; #3: missed amount to pay / credit, units used |
| iesco-2021-01 | ur | llm | 2 | #1: missed amount to pay / credit |
| iesco-2023-03 | ur | llm | 2 | #1: missed amount to pay / credit, units used |
| pesco-2026-03 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited, audit problems; #2: missed amount to pay / credit, units sent back, what this bill added/credited, audit problems; #3: missed amount to pay / credit, units sent back, what this bill added/credited, audit problems |
| pesco-2026-07 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited; #2: invented 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, 1400, 1700, missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited; #3: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited |
| pesco-2026-08 | ur | llm | 1 | - |
| pesco-2026-09 | ur | template_fallback | 3 | #1: missed amount to pay / credit; #2: missed amount to pay / credit, units taken from grid, units sent back; #3: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited |
