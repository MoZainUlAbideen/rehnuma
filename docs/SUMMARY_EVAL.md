# LLM summary eval: what we measured and what we learned

The summary a household sees is written by an LLM, checked by a deterministic critic, and
replaced by the template summary if it fails 3 times. Eval: 7 real bills x Urdu/English.
Reports: `reports/summary_eval/<model>/` (`report.md` = scores, `samples.md` = every final
summary plus every rejected draft).

## Round 1: three Groq models (Sep 2026, critic v1: numbers + must-mention facts + language)

| Model | First draft passed critic | Fell back to template | Time / summary |
|---|---|---|---|
| allam-2-7b (ur + en) | 21.4% | 50.0% | - |
| allam-2-7b (ur only, rerun) | 14.3% | 57.1% | 48.6 s |
| openai/gpt-oss-120b | 100% | 0% | 8.5 s |
| qwen/qwen3.8-27b | 100% | 0% | 5.3 s |

Final faithfulness was 100% for every model: **no invented number reached a user**.

## What reading the rejected drafts showed

Two guesses made from the score table alone were both wrong (Arabic-script digits;
line numbering). The drafts themselves showed:

1. **allam-2-7b writes broken Urdu.** Repetition loops (one line 20+ times), wrong words
   ("بلی" = cat for بل = bill, "پیٹھے" = stomach, "پانی" = water for a credit), and it
   reported this month's Rs 19,285 settlement as the account balance (actually Rs 134,041).
   The critic's "missing amount" rejections were correct.
2. **The critic can pass nonsense.** One allam draft passed with every number correct but
   described the credit as "114,756 پانی" and swapped peak/off-peak. The critic checks numbers,
   not meaning.
3. **Both large models made the same false claim** on the Sep-26 credit bill: "your credit is
   kept until 24 September 2026". The 24th is the payment due date; it means nothing on a credit.
   Root cause was ours: the prompt passed the due date on credit bills, in ISO format.

## Fixes (critic v2)

- Credit bills: the due date is no longer sent to the LLM, and is no longer an allowed number,
  so a "kept until 24 September" claim is rejected.
- Dates are sent as people read them ("24 ستمبر 2026"), not "2026-09-24".
- New structure check: 3–14 lines, no repeated line (catches loops). The limit is set by the
  longest real template summary (12 lines). A first limit of 10 rejected our own fallback,
  and a test now guards that.
- Groq requests cap `max_tokens` (an uncapped request reserved ~6k tokens and hit the 6,000 TPM
  free-tier limit with HTTP 413); gpt-oss runs with low reasoning effort; any LLM error falls back
  to the template instead of crashing.

## Still open

- **Meaning is not machine-checked.** Human review by a native Urdu reader is the current
  safeguard (below). A future option: an LLM judge scored against human ratings.
- Re-run gpt-oss-120b and qwen3.8-27b under critic v2 (Round 2).

## Round 2: critic v2 (Urdu, 7 real bills)

| Model | First draft passed critic | Fell back to template | Time / summary |
|---|---|---|---|
| openai/gpt-oss-120b | 100% | 0% | 1.4 s (was 8.5 s before the reasoning/token fixes) |
| qwen/qwen3.8-27b | 100% | 0% | 2.9 s |

**Human check:** the bill owner (native Urdu reader) said the summaries of his own bills
look good. One reader so far, see `USER_RESEARCH.md`.

**Production model: `openai/gpt-oss-120b`.** Both models tied on the critic; gpt-oss is 2x
faster. A line-by-line meaning review of both models is still worth doing before launch,
since the critic cannot check meaning.