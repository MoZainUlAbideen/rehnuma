# Policy retrieval eval (Urdu rewrite: off; dense: off)

35 questions. dev = seen while tuning; heldout = never tuned on. Hit rates count only questions whose gold clause the parser produced.

| Split/lang | Method | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|---|
| dev/en | bm25 | 16 | 31% | 81% | 0.51 |
| dev/en | char | 16 | 25% | 56% | 0.39 |
| dev/en | hybrid | 16 | 38% | 88% | 0.56 |
| dev/ur | bm25 | 6 | 0% | 0% | 0.00 |
| dev/ur | char | 6 | 0% | 0% | 0.00 |
| dev/ur | hybrid | 6 | 0% | 0% | 0.00 |
| heldout/en | bm25 | 11 | 45% | 82% | 0.61 |
| heldout/en | char | 11 | 55% | 91% | 0.67 |
| heldout/en | hybrid | 11 | 64% | 91% | 0.76 |
| heldout/ur | bm25 | 2 | 0% | 0% | 0.00 |
| heldout/ur | char | 2 | 0% | 0% | 0.00 |
| heldout/ur | hybrid | 2 | 0% | 0% | 0.00 |

| Question | In index | bm25 | char | hybrid | hybrid top-3 |
|---|---|---|---|---|---|
| p1 | yes | 4 | - | 4 | csm-2025:6.4.1, csm-2025:4.3.1, csm-2025:6.1.1.1 |
| p1-ur | yes | - | - | - |  |
| p2 | yes | - | - | - | csm-2025:6.1.1.1, csm-2025:6.4.1, csm-2025:4.3.1 |
| p2-ur | yes | - | - | - |  |
| p3 | yes | 1 | 1 | 1 | prosumer-2026:14(3), csm-2025:15.1, csm-2025:16.2.5 |
| p4 | yes | 5 | - | 4 | csm-2025:6.4.1, csm-2025:4.3.1, csm-2025:6.1.1.1 |
| p4-ur | yes | - | - | - | prosumer-2026:1(1), prosumer-2026:preamble, prosumer-2026:21(3) |
| p5 | yes | 1 | 1 | 1 | prosumer-2026:21(1), prosumer-2026:21(2), prosumer-2026:21(3) |
| p6 | yes | 1 | 1 | 1 | prosumer-2026:3(2), nm-2015:18, csm-2025:7.5.1 |
| p6-ur | yes | - | - | - |  |
| p7 | yes | 3 | 1 | 1 | prosumer-2026:2(1)(viii), prosumer-2026:14(1), prosumer-2026:14(2) |
| p8 | yes | 2 | - | 5 | prosumer-2026:3(2), nm-2015:6(1), nm-2015:12(2) |
| n1 | yes | - | 5 | 5 | nm-2015:1, nm-2015:13(1), prosumer-2026:21(1) |
| n2 | yes | 3 | 2 | 2 | csm-2025:6.1.1.1, nm-2015:14(3), csm-2025:6.4.1 |
| n3 | yes | - | - | - | csm-2025:3.4.4, prosumer-2026:21(3), nm-2015-amend-2017:p1 |
| c1 | yes | 1 | 2 | 1 | csm-2025:4.3.1, csm-2025:4.3.6, csm-2025:6.4.1 |
| c1-ur | yes | - | - | - |  |
| c2 | yes | 1 | - | 2 | csm-2025:4.3.6, csm-2025:4.3.1, csm-2025:4.4 |
| c3 | yes | 2 | 2 | 2 | csm-2025:4.3.1, csm-2025:4.3.3, csm-2025:4.3.4 |
| c3-ur | yes | - | - | - |  |
| c4 | yes | 2 | 2 | 2 | csm-2025:6.3, csm-2025:6.1.1, csm-2025:6.2 |
| c5 | yes | 2 | - | 1 | csm-2025:2.4.9, csm-2025:2.4.10, csm-2025:8.6 |
| h1 | yes | 2 | 1 | 1 | prosumer-2026:7(1), prosumer-2026:7(2), prosumer-2026:2(1)(ii) |
| h1-ur | yes | - | - | - |  |
| h2 | yes | - | - | - | prosumer-2026:2(1)(x), nm-2015:2(1), nm-2015:3(9) |
| h3 | yes | 1 | 1 | 1 | prosumer-2026:13(1), nm-2015:13(1), prosumer-2026:2(1)(ix) |
| h4 | yes | - | 1 | 1 | prosumer-2026:8(1), nm-2015:2(1), nm-2015:18 |
| h5 | yes | 1 | 4 | 2 | csm-2025:6.4.1, nm-2015:14(4), csm-2025:4.3.1 |
| h6 | yes | 1 | 2 | 1 | csm-2025:9.1.3, csm-2025:9.2.3, csm-2025:9.2.5 |
| h6-ur | yes | - | - | - |  |
| h7 | yes | 2 | 3 | 1 | csm-2025:10.3.1, csm-2025:9.2.5, csm-2025:10.3.1 |
| h8 | yes | 1 | 1 | 1 | csm-2025:6.7.2, csm-2025:6.8.1, csm-2025:8.2.4 |
| h9 | yes | 2 | 3 | 2 | csm-2025:6.4.1, csm-2025:6.1.1.1, csm-2025:6.1.1.1 |
| h10 | yes | 1 | 1 | 1 | csm-2025:2.4.11, csm-2025:4.2.8, csm-2025:4.3.4 |
| h11 | yes | 5 | 1 | 3 | csm-2025:7.5.2, csm-2025:8.1, csm-2025:8.2.10 |
