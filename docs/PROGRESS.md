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
- [x] Clause-level parser: regulations (inline "14. Billing.— (1)...(2)"), definitions, schedules; manual (dotted clauses, chapter check, TOC skipped, annexures); page-window fallback
- [x] Fixed: numbering filter dropped every regulation after a gap - now longest increasing run
- [x] Hybrid retrieval: BM25 + character n-grams (survives OCR typos), fused with RRF
- [x] Urdu question -> English search query (Groq)
- [x] Retrieval eval (`rehnuma-eval-policy`): hit@1 / hit@5 / MRR per method and language; parser misses reported separately
- [ ] Run fetch + ingest + retrieval eval on the real PDFs; fix what the real text breaks
- [ ] Answer layer: cite every claim [doc, clause, page], answer in Urdu/English, refuse when unsupported
- [ ] Critic: citations exist and were retrieved, numbers appear in cited clauses, repealed clauses flagged
- [ ] Answer eval: faithfulness, citation accuracy, refusal on out-of-scope questions
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