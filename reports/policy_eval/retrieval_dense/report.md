# Policy retrieval eval (Urdu rewrite: off; dense: intfloat/multilingual-e5-small)

35 questions. dev = seen while tuning; heldout = never tuned on. Hit rates count only questions whose gold clause the parser produced.

| Split/lang | Method | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|---|
| dev/en | bm25 | 16 | 31% | 81% | 0.51 |
| dev/en | char | 16 | 25% | 56% | 0.39 |
| dev/en | hybrid | 16 | 38% | 88% | 0.56 |
| dev/en | dense | 16 | 31% | 81% | 0.46 |
| dev/en | hybrid+dense | 16 | 31% | 81% | 0.50 |
| dev/ur | bm25 | 6 | 0% | 0% | 0.00 |
| dev/ur | char | 6 | 0% | 0% | 0.00 |
| dev/ur | hybrid | 6 | 0% | 0% | 0.00 |
| dev/ur | dense | 6 | 17% | 17% | 0.17 |
| dev/ur | hybrid+dense | 6 | 17% | 17% | 0.17 |
| heldout/en | bm25 | 11 | 45% | 82% | 0.61 |
| heldout/en | char | 11 | 55% | 91% | 0.67 |
| heldout/en | hybrid | 11 | 64% | 91% | 0.76 |
| heldout/en | dense | 11 | 64% | 73% | 0.66 |
| heldout/en | hybrid+dense | 11 | 64% | 82% | 0.68 |
| heldout/ur | bm25 | 2 | 0% | 0% | 0.00 |
| heldout/ur | char | 2 | 0% | 0% | 0.00 |
| heldout/ur | hybrid | 2 | 0% | 0% | 0.00 |
| heldout/ur | dense | 2 | 50% | 100% | 0.67 |
| heldout/ur | hybrid+dense | 2 | 50% | 100% | 0.67 |

| Question | In index | bm25 | char | hybrid | dense | hybrid+dense | hybrid+dense top-3 |
|---|---|---|---|---|---|---|---|
| p1 | yes | 4 | - | 4 | 4 | 3 | csm-2025:6.4.1, csm-2025:6.1.1.1, prosumer-2026:14(1) |
| p1-ur | yes | - | - | - | - | - | csm-2025:7.5, csm-2025:5.2, csm-2025:6.7 |
| p2 | yes | - | - | - | 1 | 3 | csm-2025:6.4.1, csm-2025:6.1.1.1, prosumer-2026:14(2) |
| p2-ur | yes | - | - | - | 1 | 1 | prosumer-2026:14(2), csm-2025:6.7, csm-2025:6.8 |
| p3 | yes | 1 | 1 | 1 | 4 | 1 | prosumer-2026:14(3), csm-2025:5.1.1, nm-2015:4(1) |
| p4 | yes | 5 | - | 4 | - | - | csm-2025:6.4.1, csm-2025:4.3.1, csm-2025:6.1.1.1 |
| p4-ur | yes | - | - | - | - | - | prosumer-2026:1(1), prosumer-2026:preamble, prosumer-2026:21(3) |
| p5 | yes | 1 | 1 | 1 | 3 | 1 | prosumer-2026:21(1), prosumer-2026:21(2), prosumer-2026:1(1) |
| p6 | yes | 1 | 1 | 1 | 1 | 1 | prosumer-2026:3(2), csm-2025:2.10.1, csm-2025:8.2.10 |
| p6-ur | yes | - | - | - | - | - | csm-2025:5.2, csm-2025:6.4, csm-2025:7.5 |
| p7 | yes | 3 | 1 | 1 | 3 | 3 | prosumer-2026:14(2), prosumer-2026:14(1), prosumer-2026:2(1)(viii) |
| p8 | yes | 2 | - | 5 | 2 | 3 | nm-2015:6(1), prosumer-2026:3(2), nm-2015:2(1) |
| n1 | yes | - | 5 | 5 | 1 | 3 | nm-2015:1, prosumer-2026:21(1), nm-2015-amend-2017:p1 |
| n2 | yes | 3 | 2 | 2 | - | 3 | csm-2025:6.1.1.1, csm-2025:6.4.1, nm-2015:14(3) |
| n3 | yes | - | - | - | - | - | nm-2015-amend-2017:p1, nm-2015-amend-2018:p1, csm-2025:1.4 |
| c1 | yes | 1 | 2 | 1 | 4 | 2 | csm-2025:4.3.6, csm-2025:4.3.1, csm-2025:4.3.2 |
| c1-ur | yes | - | - | - | - | - | csm-2025:6.4, csm-2025:6.7, csm-2025:4.3 |
| c2 | yes | 1 | - | 2 | 1 | 1 | csm-2025:4.3.1, csm-2025:4.3.3, csm-2025:4.3.6 |
| c3 | yes | 2 | 2 | 2 | 5 | 2 | csm-2025:4.3.1, csm-2025:4.3.3, csm-2025:6.1.1.1 |
| c3-ur | yes | - | - | - | - | - | csm-2025:6.1.1.1, csm-2025:4.3, csm-2025:6.1.1.1 |
| c4 | yes | 2 | 2 | 2 | 1 | 1 | csm-2025:6.1.1, csm-2025:6.1.1.1, csm-2025:6.3 |
| c5 | yes | 2 | - | 1 | 5 | - | csm-2025:8.6, csm-2025:8.6.2, csm-2025:5.2.2 |
| h1 | yes | 2 | 1 | 1 | - | 3 | nm-2015:18, nm-2015:18, prosumer-2026:7(1) |
| h1-ur | yes | - | - | - | 3 | 3 | nm-2015:7(1), csm-2025:6.4, prosumer-2026:7(1) |
| h2 | yes | - | - | - | 4 | - | nm-2015:2(1), nm-2015:14(1), nm-2015:3(9) |
| h3 | yes | 1 | 1 | 1 | 1 | 1 | prosumer-2026:13(1), nm-2015:13(1), csm-2025:16.5.2 |
| h4 | yes | - | 1 | 1 | - | 5 | nm-2015:18, nm-2015:18, nm-2015:18 |
| h5 | yes | 1 | 4 | 2 | - | - | csm-2025:4.3.1, csm-2025:6.1.1.1, csm-2025:6.4.1 |
| h6 | yes | 1 | 2 | 1 | 1 | 1 | csm-2025:9.1.3, csm-2025:9.2.3, csm-2025:9.2.3 |
| h6-ur | yes | - | - | - | 1 | 1 | csm-2025:9.2.3, csm-2025:9.2.3, csm-2025:9.1.3 |
| h7 | yes | 2 | 3 | 1 | 1 | 1 | csm-2025:10.3.1, csm-2025:10.3.1, csm-2025:9.2.5 |
| h8 | yes | 1 | 1 | 1 | 1 | 1 | csm-2025:6.7.2, csm-2025:6.8.1, csm-2025:8.2.4 |
| h9 | yes | 2 | 3 | 2 | 1 | 1 | csm-2025:6.1.1.1, csm-2025:6.1.1.1, csm-2025:6.1.1.1 |
| h10 | yes | 1 | 1 | 1 | 1 | 1 | csm-2025:2.4.11, csm-2025:4.3.4, csm-2025:4.2.8 |
| h11 | yes | 5 | 1 | 3 | 1 | 1 | csm-2025:8.2.10, csm-2025:7.5.2, csm-2025:8.4 |
