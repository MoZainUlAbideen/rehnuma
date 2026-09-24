# Policy answer eval (groq:openai/gpt-oss-120b)

13 questions; 16 LLM calls; mean 5.6 s per question. Rewrites: replayed.

| Split/lang | n | answered | first draft | fallback | false refusal | error | gold retrieved | cites gold | fact correct |
|---|---|---|---|---|---|---|---|---|---|
| heldout/en | 11 | 100% | 73% | 0% | 0% | 0% | 91% | 91% (n=11) | 100% (n=3) |
| heldout/ur | 2 | 100% | 100% | 0% | 0% | 0% | 100% | 100% (n=2) | 100% (n=2) |

| Question | Status | Attempts | Cites gold | Fact | Critic problems |
|---|---|---|---|---|---|
| h1 | answered | 1 | yes | yes | - |
| h1-ur | answered | 1 | yes | yes | - |
| h2 | answered | 2 | **no** | - | 1 sentence(s) have no [S#] tag |
| h3 | answered | 2 | yes | - | 2 sentence(s) have no [S#] tag |
| h4 | answered | 1 | yes | - | - |
| h5 | answered | 1 | yes | - | - |
| h6 | answered | 1 | yes | yes | - |
| h6-ur | answered | 1 | yes | yes | - |
| h7 | answered | 1 | yes | yes | - |
| h8 | answered | 1 | yes | - | - |
| h9 | answered | 2 | yes | - | 1 sentence(s) have no [S#] tag |
| h10 | answered | 1 | yes | - | - |
| h11 | answered | 1 | yes | - | - |
