# Policy answer eval (groq:openai/gpt-oss-120b)

4 questions; 6 LLM calls; mean 3.9 s per question. Rewrites: replayed.

| Split/lang | n | answered | first draft | fallback | false refusal | error | gold retrieved | cites gold | fact correct |
|---|---|---|---|---|---|---|---|---|---|
| dev/en | 2 | 50% | 50% | 50% | 0% | 0% | 100% | 100% (n=1) | 100% (n=1) |
| dev/ur | 2 | 100% | 50% | 0% | 0% | 0% | 100% | 100% (n=2) | 100% (n=2) |

| Question | Status | Attempts | Cites gold | Fact | Critic problems |
|---|---|---|---|---|---|
| p1-ur | answered | 1 | yes | yes | - |
| p4 | answered | 1 | yes | yes | - |
| p4-ur | answered | 2 | yes | yes | write these rate names exactly, in English: national average power purchase price; national average energy purchase price |
| c5 | fallback | 2 | **no** | - | 6 sentence(s) have no [S#] tag; 3 sentence(s) have no [S#] tag |
