# Summary eval - groq:allam-2-7b

14 summaries (real bills x languages).

| Metric | Value |
|---|---|
| First draft passed the critic | 21.4% |
| Fell back to template | 50.0% |
| Faithfulness (final) | 100.0% |
| Coverage of must-mention facts (final) | 100.0% |
| Correct language (final) | 100.0% |
| Mean attempts | 2.36 |

| Bill | Lang | Source | Attempts | Rejected drafts |
|---|---|---|---|---|
| iesco-2019-07 | ur | llm | 3 | #1: invented 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 8, 9, missed amount to pay / credit; #2: missed amount to pay / credit, units used |
| iesco-2019-07 | en | llm | 2 | #1: invented 1, 2, 3, 4 |
| iesco-2021-01 | ur | llm | 2 | #1: missed amount to pay / credit, units used |
| iesco-2021-01 | en | llm | 1 | - |
| iesco-2023-03 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units used; #2: missed amount to pay / credit; #3: missed units used |
| iesco-2023-03 | en | llm | 1 | - |
| pesco-2026-03 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units sent back, what this bill added/credited; #2: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited, audit problems; #3: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited, audit problems |
| pesco-2026-03 | en | llm | 2 | #1: missed what this bill added/credited |
| pesco-2026-07 | ur | template_fallback | 3 | #1: invented 2, 4, 5; #2: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited; #3: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited |
| pesco-2026-07 | en | template_fallback | 3 | #1: invented 2, 1340; #2: invented 2, missed what this bill added/credited; #3: invented 1340 |
| pesco-2026-08 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited; #2: missed what this bill added/credited; #3: missed amount to pay / credit, units taken from grid, units sent back, what this bill added/credited |
| pesco-2026-08 | en | template_fallback | 3 | #1: invented 1, missed what this bill added/credited; #2: invented 1; #3: invented 1 |
| pesco-2026-09 | ur | template_fallback | 3 | #1: missed amount to pay / credit, units taken from grid, units sent back; #2: invented 1, 2, 4, 5, missed amount to pay / credit; #3: invented 1, 2, missed amount to pay / credit, units taken from grid, units sent back |
| pesco-2026-09 | en | llm | 1 | - |
