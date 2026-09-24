# Policy retrieval eval (Urdu rewrite: groq:openai/gpt-oss-120b)

22 questions over 2 language(s). Hit rates count only questions whose gold clause the parser produced.

| Lang | Method | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|---|
| en | bm25 | 16 | 31% | 81% | 0.51 |
| en | char | 16 | 25% | 50% | 0.38 |
| en | hybrid | 16 | 38% | 88% | 0.56 |
| ur | bm25 | 6 | 33% | 50% | 0.39 |
| ur | char | 6 | 17% | 50% | 0.33 |
| ur | hybrid | 6 | 33% | 50% | 0.42 |

| Question | In index | bm25 rank | char rank | hybrid rank | hybrid top-3 |
|---|---|---|---|---|---|
| p1 | yes | 4 | - | 4 | csm-2025:6.4.1, csm-2025:4.3.1, csm-2025:6.1.1.1 |
| p1-ur | yes | - | - | - | csm-2025:4.3.1, csm-2025:6.4.1, csm-2025:6.1.1.1 |
| p2 | yes | - | - | - | csm-2025:6.1.1.1, csm-2025:6.4.1, csm-2025:6.1.1.1 |
| p2-ur | yes | 1 | 2 | 1 | prosumer-2026:14(2), nm-2015:14(3), prosumer-2026:14(1) |
| p3 | yes | 1 | 1 | 1 | prosumer-2026:14(3), csm-2025:15.1, csm-2025:16.2.5 |
| p4 | yes | 5 | - | 4 | csm-2025:6.4.1, csm-2025:4.3.1, csm-2025:6.1.1.1 |
| p4-ur | yes | - | - | - | csm-2025:1.2, csm-2025:1.1, csm-2025:15.1.1 |
| p5 | yes | 1 | 1 | 1 | prosumer-2026:21(1), prosumer-2026:21(2), prosumer-2026:preamble |
| p6 | yes | 1 | 1 | 1 | prosumer-2026:3(2), nm-2015:18, csm-2025:7.5.1 |
| p6-ur | yes | 3 | 2 | 2 | nm-2015:18, prosumer-2026:3(2), nm-2015:14(2) |
| p7 | yes | 3 | 1 | 1 | prosumer-2026:2(1)(viii), prosumer-2026:14(1), prosumer-2026:14(2) |
| p8 | yes | 2 | - | 5 | prosumer-2026:3(2), nm-2015:6, nm-2015:9(4) |
| n1 | yes | - | - | 5 | nm-2015:preamble, nm-2015:13, prosumer-2026:21(1) |
| n2 | yes | 3 | 2 | 2 | csm-2025:6.1.1.1, nm-2015:14(3), csm-2025:6.4.1 |
| n3 | yes | - | - | - | csm-2025:3.4.4, prosumer-2026:21(3), nm-2015-amend-2017:p1 |
| c1 | yes | 1 | 2 | 1 | csm-2025:4.3.1, csm-2025:4.3.6, csm-2025:6.4.1 |
| c1-ur | yes | 1 | 1 | 1 | csm-2025:4.3.1, csm-2025:6.4.1, csm-2025:4.3.6 |
| c2 | yes | 1 | - | 2 | csm-2025:4.3.6, csm-2025:4.3.1, csm-2025:4.4 |
| c3 | yes | 2 | 2 | 2 | csm-2025:4.3.1, csm-2025:4.3.3, csm-2025:4.3.4 |
| c3-ur | yes | - | - | - | csm-2025:4.3.1, csm-2025:6.4.1, csm-2025:9.2.3 |
| c4 | yes | 2 | 2 | 2 | csm-2025:6.3, csm-2025:6.1.1.1, csm-2025:6.1.1 |
| c5 | yes | 2 | - | 1 | csm-2025:2.4.9, csm-2025:2.4.10, csm-2025:8.6 |
