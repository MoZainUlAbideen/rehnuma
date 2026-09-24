# Rehnuma — progress log

## Milestone 1 — Deterministic reconciliation engine ✅
- [x] Repo scaffold with uv (src layout, pytest, ruff)
- [x] Bill schema covering 2 PESCO layouts + conventional / net-metering connections
- [x] Ground-truth labels for 4 real PESCO bills (PII removed)
- [x] Single-bill checks: meter units, net-metering bank, legacy charges, FPA tax cascade, v2 charges, totals
- [x] Cross-bill checks: meter continuity, arrears carry-forward, bank carry-forward, history agreement
- [x] Error-injection tests (seed of the auditor eval)
- [x] Synthetic conventional bill test (non-solar path)
- [x] `rehnuma-audit` CLI
- [x] FINDINGS.md from real bills
- [x] Verified ED on FPA against the paper Mar-26 bill (16), diagnosed the resulting Rs 2 anomaly
- [x] Expected-anomalies registry: real bills must fail exactly their documented checks
- [x] Pushed to GitHub

## Milestone 2 — Tariff rates + synthetic generator ✅ (core complete)
- [x] Collect real conventional (non-solar) bills — 3 IESCO bills (2019, 2021, 2023)
- [x] DISCO-agnostic `pitc_legacy` layout; multi-month FPA; printed rate lines
- [x] Levy calculator: ED, GST (dated schedule), NJ, FPA tax cascade — zero-delta on 4 bills
- [x] Tests proving each rule beats its plausible alternative
- [x] Fixed: recompute tolerance now follows printed precision
- [x] Fixed: cross-bill checks group by connection_id
- [x] Tariff schedules with source + confidence (2026 domestic from secondary sources; 2019/2021/2023 observed)
- [x] Slab engine: one-previous-slab benefit, unprotected band-reached rule, protected status from 6-month history
- [x] `tariff_rates` check: catches a protected household billed at unprotected rates
- [x] Synthetic generator: conventional households on the legacy layout, 11 planted error types
- [x] Auditor eval (`rehnuma-eval-auditor`): detection / localisation / false-positive rate
- [x] Fixed: eval found a generator bug (no-op planted error), now guarded

## Milestone 2.5 — Plain-language summary (from user research) ✅
- [x] Neighbourhood conversations recorded in USER_RESEARCH.md
- [x] BillStory: verified facts people care about (solar sent/used/banked; flat vs ToU; 200-unit limit)
- [x] Template summary, Urdu by default, English with `--lang en` (`rehnuma-summary`)
- [x] Numeric-faithfulness check: every number in a summary must come from the engine
- [x] Fixed: summary said Mar-26 "credited Rs 872"; it actually added Rs 292 (FPA billed separately)
- [x] LLM summary (Groq) + deterministic critic (numbers, must-mention facts, language), 2 retries with feedback, template fallback
- [x] Summary eval on real bills (`rehnuma-eval-summary`): first-draft pass rate, fallback rate, faithfulness, coverage, language
- [x] Groq model comparison (allam-2-7b / gpt-oss-120b / qwen3.8-27b), findings in SUMMARY_EVAL.md
- [x] Critic v2: structure check (loops), no due date on credit bills, readable dates
- [x] Critic v2 rerun: gpt-oss-120b and qwen3.8-27b 100% first-draft on Urdu
- [x] Production model: gpt-oss-120b (tied on critic, 2x faster: 1.4 s/summary)
- [x] First reader check: bill owner (native Urdu speaker) says the summaries look good (n=1)
- [x] Broader user check: ~5 neighbours found the Urdu summaries OK

## Milestone 3 — Vision extraction + PII redaction (in progress)
- [x] Vision client for any OpenAI-compatible API (Gemini default), stdlib only
- [x] Extraction prompt + schema derived from `Bill`; PII-free by design (no field for identifiers, extras dropped)
- [x] Verify loop: the reconciliation engine checks each extraction; failed checks trigger a re-read
- [x] Fixed: re-read feedback leaked the expected value ("expected 3273") - now names fields only
- [x] Extraction eval (`rehnuma-eval-extract`): field / key-field accuracy, reconciles rate, per layout, verify on/off
- [x] Fixed: photos with double extensions (.jpg.jpeg) were silently skipped - renamed + warning in the eval
- [x] Fixed: API quota errors were scored as 0% accuracy - now reported separately as api_error_rate
- [x] Default vision model: gemini-3.5-flash (3.8-flash overloaded / 429, 2.5-flash retired for new keys)
- [x] First real run (verify on): 6/7 bills read, 96.2% field accuracy, 100% key fields, 83.3% reconcile
- [x] Fixed: eval scored decimal formatting ("1652.60" vs "1652.6") as misreads - values now compared, not strings
- [x] New `ed_on_fpa` check: Gemini copied GST on FPA (46) into ED on FPA (4) and no check looked at that line
- [ ] Re-run verify on vs off after the Gemini quota resets (+ `--only pesco-2026-09`) and record the numbers
- [ ] EXTRACT_EVAL.md: results, each real misread, and the history-row limit (see Backlog)
- [ ] Render synthetic bills as images (clean + phone-photo augmentation) - stress test with perfect labels
- [ ] Image-level PII: blur identifiers before the photo leaves the device
- [ ] Meter-photo check: printed reading vs the meter photo on IESCO bills

## Milestone 4 — NEPRA policy guide (RAG with citations) + agent with critic (in progress)
- [x] Official corpus: Prosumer Regs 2026, Net Metering Regs 2015 + 2017/2018 amendments, Consumer Service Manual 2025 (`data/policy/sources.json`, with in-force / repealed / amends)
- [x] `rehnuma-policy fetch`: downloads the PDFs; SHA-256 lock file flags a CHANGED document (policy-watcher seed)
- [x] Clause-level parser: regulations, definitions, schedules; manual (dotted clauses, chapter check, TOC skipped, annexures); page-window fallback
- [x] Hybrid retrieval: BM25 + character n-grams (survives OCR typos), fused with RRF; one hit per clause
- [x] Retrieval eval (`rehnuma-eval-policy`): hit@1 / hit@5 / MRR per method, language and split; parser misses reported separately
- [x] Ran on the real PDFs (5 docs, 566 clause chunks) - see POLICY_EVAL.md
- [x] Fixed (real PDFs): OCR heading variants - "I." for 1, ". ---", no dash, no full stop, "(I)" for (1) - regs 1/4/6/10/11 were missing
- [x] Fixed: overlapping heading candidates ("up to 1 MW" swallowed the real "3.")
- [x] Fixed: wrapped sentence taken as a clause title; logo junk ("y*", "£3") in place of chapter titles
- [x] Fixed: schedules/annexures matched uppercase only - every schedule was glued onto the last regulation (nm-2015 reg. 18: 16,000 chars)
- [x] Held-out question split (13 questions, written before tuning, never tuned on)
- [x] Multilingual HF embeddings (`--dense`, e5-small): no gain in English, 17% hit@5 on raw Urdu - kept optional, not the default
- [x] Query rewrite (Groq): Urdu -> NEPRA wording; `--rewrite all` also rewrites English
- [x] Fixed: RRF ties were broken by file order (4/27 questions tied at #1) - now BM25 rank, then id; earlier hit@1 figures corrected
- [x] Fixed: question + rewrite concatenated diluted the user's words (dev hit@5 88% -> 75%) - now two queries fused by rank
- [x] Fixed: rewriter appended "NEPRA Consumer Service Manual" - source names stripped before search
- [x] `--replay`: re-score retrieval on cached LLM rewrites (no API calls, repeatable)
- [x] Production setting: hybrid + fused rewrite - dev/en 38% hit@1 88% hit@5, held-out/en 64% / 91%, Urdu 50% hit@1
- [x] Fresh run with the new rewrite prompt: p4 (grandfathered export price) found at rank 2; dev/en hit@5 94%, Urdu 83%
- [x] Answer layer (`rehnuma-policy ask`): [S1]..[S5] sources with doc/clause/page and in-force/repealed status, Urdu or English, NOT_FOUND -> refusal
- [x] Critic (no LLM): tags exist, every sentence cited, numbers in cited sources (number words + Urdu digits), language, repealed flagged; one retry, then honest fallback
- [x] Fixed: sentence splitter cut "…years. [S1]" before the tag - every cited sentence looked uncited
- [x] Answer eval (`rehnuma-eval-answer`): answered / first draft / fallback / false refusal, cites gold, fact check, 6 out-of-scope questions
- [x] Answer eval, held-out: 91% answered (EN), 100% (UR), 90-100% cite the gold clause, 0 false refusals; out-of-scope 6/6 refused
- [x] Found: the family's own Urdu question got a cited but WRONG answer - retrieval missed 21(2) and the model repeated a paraphrase from our metadata
- [x] Fixed: metadata notes state no rules; repealed docs name their savings clause, which is always added to the sources and must be cited
- [x] Fixed: critic checks numbers against exactly what the model saw (h5 fell back over "2026" in a source header)
- [x] Re-run: held-out 100% answered (EN+UR), 91-100% cite gold; dev 88% (EN) / 100% (UR); p4 English exactly right
- [x] Found: Urdu translated the rate NAME - "energy" instead of "power" purchase price for the family's question; eval's Urdu fact alternative matched both rates
- [x] Fixed: rate names verbatim in English whenever a cited clause names them (critic); rate facts English-only in the eval
- [x] Fixed: referenced annexures/schedules added to sources (c5 had "as per Annexure - IV" without the rates); partial answers allowed
- [x] Found: a correct first draft (power until term end, energy for renewals) was rejected for tags and the from-scratch retry got it wrong - retry now fixes its own draft
- [x] Found: that run used stale files (parallel copy + write shipped old versions) - delivery now sequential, verified by read-back
- [x] Verified-code run: the family's question answered correctly (power price until the agreement ends, energy on renewal, citing 21(2)); retry kept the correct draft; rate rule caught p4-ur
- [x] Fixed: critic split sentences at "Rs." / "etc.", demanded tags on "the sources do not cover X", and broke on a trailing NOT_FOUND - c5's good partial answer fell back
- [x] p4/p4-ur now also must say billing moves to net billing (reg. 14) - completeness the critic can't enforce, measured by the eval
- [ ] Full answer eval (dev + held-out + out-of-scope) on the next Groq allowance
- [ ] Route bill questions to the engine (RAG explains rules, the engine does the arithmetic)

## Milestone 5 — Forecasting (both segments) + solar planner
- [ ] Next-12-months bill forecast from the bill's own history (conventional households)
- [ ] Export credit / settlement trajectory for prosumers
- [ ] Solar planner: PVGIS yield + 2026 net billing (buyback at national average energy purchase price) vs grandfathered net metering

## Milestone 6 — LLMOps
- [ ] Langfuse tracing across extraction, summary and policy answers
- [ ] Evals in CI (auditor, summary template baseline, policy retrieval)
- [ ] Policy watcher: scheduled `fetch`, CHANGED documents open a review task (a human approves every rule change)

## Milestone 7 — Live product
- [ ] FastAPI backend: upload photo -> verified bill -> audit + Urdu/English summary; policy Q&A endpoint
- [ ] Next.js frontend (Urdu-first, RTL), polished design
- [ ] Deploy

## Backlog — waiting on sources or data
- [ ] Get S.R.O. 279(I)/2026 itself and upgrade the 2026 schedule to `official` — *needs the official PDF*
- [ ] ToU (A-1b) and net-metering slabs; fixed charges and their GST treatment — *needs the same SRO*
- [ ] Open questions in FINDINGS.md: LP surcharge base, status codes (`LK`, `SS`), Q1 vs Q3 netting — *needs regulation text / more bills*
- [ ] History rows older than last month are not verifiable from one bill (Gemini misread digits and one sign there, still "verified") — *needs consecutive bills to cross-check, or a documented limit*
- [ ] Stronger multilingual embeddings (`BAAI/bge-m3`) for Urdu without an LLM call — *e5-small reached 17% hit@5 on raw Urdu*
- [ ] Net Metering Regs 2015 reg. 8 heading is OCR'd as "S. Termination of Agrei" — its text stays under reg. 7 (known limit)
