# Policy answer eval (groq:openai/gpt-oss-120b)

22 questions; 27 LLM calls; mean 10.2 s per question. Rewrites: replayed.

| Split/lang | n | answered | first draft | fallback | false refusal | error | gold retrieved | cites gold | fact correct |
|---|---|---|---|---|---|---|---|---|---|
| dev/en | 16 | 88% | 75% | 6% | 6% | 0% | 94% | 93% (n=14) | 78% (n=9) |
| dev/ur | 6 | 67% | 67% | 33% | 0% | 0% | 100% | 100% (n=4) | 100% (n=3) |

| Question | Status | Attempts | Cites gold | Fact | Critic problems |
|---|---|---|---|---|---|
| p1 | answered | 1 | yes | yes | - |
| p1-ur | answered | 1 | yes | yes | - |
| p2 | answered | 1 | yes | yes | - |
| p2-ur | answered | 1 | yes | yes | - |
| p3 | answered | 1 | yes | - | - |
| p4 | answered | 1 | yes | **no** | - |
| p4-ur | fallback | 2 | **no** | - | write these rate names exactly, in English: national average power purchase price; national average energy purchase price; 1 sentence(s) hav |
| p5 | answered | 1 | yes | - | - |
| p6 | answered | 1 | yes | yes | - |
| p6-ur | answered | 1 | yes | - | - |
| p7 | answered | 1 | yes | yes | - |
| p8 | answered | 2 | **no** | **no** | 1 sentence(s) have no [S#] tag |
| n1 | answered | 2 | yes | - | S5 is REPEALED; say it is the old rule and when it still applies |
| n2 | answered | 1 | yes | - | - |
| n3 | refused | 1 | **no** | - | - |
| c1 | answered | 1 | yes | yes | - |
| c1-ur | answered | 1 | yes | yes | - |
| c2 | answered | 1 | yes | yes | - |
| c3 | answered | 1 | yes | yes | - |
| c3-ur | fallback | 2 | **no** | - | 1 sentence(s) have no [S#] tag; 1 sentence(s) have no [S#] tag |
| c4 | answered | 1 | yes | - | - |
| c5 | fallback | 2 | **no** | - | 1 sentence(s) have no [S#] tag; 1 sentence(s) have no [S#] tag |
