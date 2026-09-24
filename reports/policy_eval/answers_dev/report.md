# Policy answer eval (groq:openai/gpt-oss-120b)

22 questions; 23 LLM calls; mean 7.3 s per question. Rewrites: replayed.

| Split/lang | n | answered | first draft | fallback | false refusal | error | gold retrieved | cites gold | fact correct |
|---|---|---|---|---|---|---|---|---|---|
| dev/en | 16 | 88% | 81% | 0% | 12% | 0% | 94% | 93% (n=14) | 89% (n=9) |
| dev/ur | 6 | 100% | 100% | 0% | 0% | 0% | 100% | 100% (n=6) | 75% (n=4) |

| Question | Status | Attempts | Cites gold | Fact | Critic problems |
|---|---|---|---|---|---|
| p1 | answered | 1 | yes | yes | - |
| p1-ur | answered | 1 | yes | **no** | - |
| p2 | answered | 1 | yes | yes | - |
| p2-ur | answered | 1 | yes | yes | - |
| p3 | answered | 1 | yes | - | - |
| p4 | answered | 1 | yes | yes | - |
| p4-ur | answered | 1 | yes | yes | - |
| p5 | answered | 1 | yes | - | - |
| p6 | answered | 1 | yes | yes | - |
| p6-ur | answered | 1 | yes | - | - |
| p7 | answered | 1 | yes | yes | - |
| p8 | answered | 1 | **no** | **no** | - |
| n1 | answered | 1 | yes | - | - |
| n2 | answered | 1 | yes | - | - |
| n3 | refused | 1 | **no** | - | - |
| c1 | answered | 1 | yes | yes | - |
| c1-ur | answered | 1 | yes | yes | - |
| c2 | answered | 1 | yes | yes | - |
| c3 | answered | 2 | yes | yes | 2 sentence(s) have no [S#] tag |
| c3-ur | answered | 1 | yes | - | - |
| c4 | answered | 1 | yes | - | - |
| c5 | refused | 1 | **no** | - | - |
