# Policy retrieval eval (Urdu rewrite: all via groq:openai/gpt-oss-120b; dense: off)

35 questions. dev = seen while tuning; heldout = never tuned on. Hit rates count only questions whose gold clause the parser produced.

| Split/lang | Method | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|---|
| dev/en | bm25 | 16 | 44% | 81% | 0.60 |
| dev/en | char | 16 | 44% | 69% | 0.54 |
| dev/en | hybrid | 16 | 38% | 94% | 0.59 |
| dev/ur | bm25 | 6 | 50% | 83% | 0.60 |
| dev/ur | char | 6 | 50% | 67% | 0.54 |
| dev/ur | hybrid | 6 | 50% | 83% | 0.64 |
| heldout/en | bm25 | 11 | 64% | 91% | 0.73 |
| heldout/en | char | 11 | 45% | 82% | 0.62 |
| heldout/en | hybrid | 11 | 55% | 91% | 0.73 |
| heldout/ur | bm25 | 2 | 50% | 100% | 0.75 |
| heldout/ur | char | 2 | 0% | 100% | 0.42 |
| heldout/ur | hybrid | 2 | 50% | 100% | 0.75 |

| Question | In index | bm25 | char | hybrid | hybrid top-3 |
|---|---|---|---|---|---|
| p1 | yes | 1 | 1 | 1 | prosumer-2026:14(1), nm-2015:14(2), nm-2015:14(1) |
| p1-ur | yes | 1 | 1 | 1 | prosumer-2026:14(1), prosumer-2026:14(2), nm-2015:14(2) |
| p2 | yes | 2 | 2 | 2 | csm-2025:6.1.1.1, prosumer-2026:14(2), nm-2015:14(3) |
| p2-ur | yes | 1 | 1 | 1 | prosumer-2026:14(2), nm-2015:14(3), nm-2015:14(2) |
| p3 | yes | 1 | 1 | 1 | prosumer-2026:14(3), nm-2015:4(1), nm-2015:Schedule-I |
| p4 | yes | 1 | - | 2 | csm-2025:6.4.1, prosumer-2026:21(2), csm-2025:4.3.1 |
| p4-ur | yes | - | - | - | nm-2015:12(3), prosumer-2026:12(3), nm-2015:3(9) |
| p5 | yes | 2 | 1 | 2 | prosumer-2026:21(3), prosumer-2026:21(1), prosumer-2026:21(2) |
| p6 | yes | 1 | 1 | 1 | prosumer-2026:3(2), nm-2015:Schedule-I, prosumer-2026:Schedule-I |
| p6-ur | yes | 4 | 4 | 2 | prosumer-2026:7(1), prosumer-2026:3(2), nm-2015:7(1) |
| p7 | yes | - | 3 | 3 | prosumer-2026:14(1), prosumer-2026:14(2), prosumer-2026:2(1)(viii) |
| p8 | yes | 3 | - | 5 | prosumer-2026:3(2), nm-2015:6(1), nm-2015:9(4) |
| n1 | yes | - | 1 | 5 | nm-2015:1, nm-2015:Schedule-VII, nm-2015:Schedule-I |
| n2 | yes | 2 | 1 | 1 | nm-2015:14(3), csm-2025:6.1.1.1, csm-2025:6.4.1 |
| n3 | yes | - | - | - | prosumer-2026:Schedule-I, csm-2025:6.4.1, csm-2025:1.4 |
| c1 | yes | 1 | 1 | 1 | csm-2025:4.3.1, csm-2025:4.3.6, csm-2025:6.4.1 |
| c1-ur | yes | 1 | 1 | 1 | csm-2025:4.3.1, csm-2025:9.2.3, csm-2025:6.4.1 |
| c2 | yes | 3 | - | 4 | csm-2025:4.3.6, csm-2025:4.3.3, csm-2025:4.4 |
| c3 | yes | 2 | 2 | 2 | csm-2025:4.3.1, csm-2025:4.3.3, csm-2025:4.3.4 |
| c3-ur | yes | 3 | - | 3 | csm-2025:4.3.1, csm-2025:6.4.1, csm-2025:4.3.3 |
| c4 | yes | 1 | 4 | 2 | csm-2025:6.3, csm-2025:6.1.1, csm-2025:6.1.1.1 |
| c5 | yes | 1 | - | 1 | csm-2025:2.4.9, csm-2025:2.4.10, csm-2025:Annex-VI |
| h1 | yes | 2 | 2 | 2 | prosumer-2026:7(2), prosumer-2026:7(1), nm-2015:7(1) |
| h1-ur | yes | 2 | 3 | 2 | prosumer-2026:7(2), prosumer-2026:7(1), prosumer-2026:2(1)(ii) |
| h2 | yes | - | 3 | - | nm-2015:2(1), nm-2015:3(9), nm-2015:12(1) |
| h3 | yes | 1 | - | 2 | prosumer-2026:2(1)(ix), prosumer-2026:5(1), csm-2025:2.4.11 |
| h4 | yes | 1 | 1 | 1 | prosumer-2026:8(1), prosumer-2026:6(2), prosumer-2026:7(1) |
| h5 | yes | 1 | 2 | 1 | nm-2015:14(4), csm-2025:6.4.1, csm-2025:4.3.1 |
| h6 | yes | 1 | 1 | 1 | csm-2025:9.1.3, csm-2025:9.2.3, csm-2025:9.2.5 |
| h6-ur | yes | 1 | 2 | 1 | csm-2025:9.1.3, csm-2025:9.2.5, csm-2025:9.2.3 |
| h7 | yes | 3 | - | 2 | csm-2025:9.2.5, csm-2025:10.3.1, csm-2025:10.3 |
| h8 | yes | 1 | 1 | 1 | csm-2025:6.7.2, csm-2025:6.8.1, csm-2025:8.2.4 |
| h9 | yes | 1 | 2 | 1 | csm-2025:6.1.1.1, csm-2025:6.4.1, csm-2025:6.8.1 |
| h10 | yes | 1 | 1 | 1 | csm-2025:2.4.11, csm-2025:4.2.8, nm-2015:2(1) |
| h11 | yes | 4 | 1 | 2 | csm-2025:7.5.2, csm-2025:8.2.10, csm-2025:2.10.1 |
