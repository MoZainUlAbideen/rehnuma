# Policy answer eval (groq:openai/gpt-oss-120b)

22 questions; 21 LLM calls; mean 18.7 s per question. Rewrites: replayed.

| Split/lang | n | answered | first draft | fallback | false refusal | error | gold retrieved | cites gold | fact correct |
|---|---|---|---|---|---|---|---|---|---|
| dev/en | 16 | 88% | 88% | 0% | 6% | 6% | 94% | 93% (n=14) | 78% (n=9) |
| dev/ur | 6 | 83% | 67% | 0% | 0% | 17% | 100% | 100% (n=5) | 75% (n=4) |

| Question | Status | Attempts | Cites gold | Fact | Critic problems |
|---|---|---|---|---|---|
| p1 | answered | 1 | yes | yes | - |
| p1-ur | answered | 1 | yes | yes | - |
| p2 | answered | 1 | yes | yes | - |
| p2-ur | answered | 1 | yes | yes | - |
| p3 | answered | 1 | yes | - | - |
| p4 | answered | 1 | yes | **no** | - |
| p4-ur | answered | 2 | yes | **no** | write these rate names exactly, in English: national average power purchase price; national average energy purchase price |
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
| c3 | answered | 1 | yes | yes | - |
| c3-ur | error | 1 | **no** | - | LLM error: Groq HTTP 429: {"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01kwhmxddjfp |
| c4 | answered | 1 | yes | - | - |
| c5 | error | 1 | **no** | - | LLM error: Groq HTTP 429: {"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01kwhmxddjfp |
