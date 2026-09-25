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
- [x] `--only pesco-2026-09` on gemini-3.5-flash: 96.5% fields, 100% key fields, NOT verified - it CALCULATED the net-metering bank (Rem kWh present = previous - Net: 1325 + 507 = 1832, -319 - 194 = -513) instead of copying the printed 0 of a settlement month; the engine caught it, the re-read repeated it
- [x] Fixed: prompt + re-read feedback say Rem kWh is copied, never computed (effect to be measured in the full run)
- [x] Fixed: a DAILY quota 429 was retried 4 x 90 s per bill (3 minutes lost, then the next bill did the same) - now stops the run at once; the API answers 503 "free quota used up"
- [x] Eval resumes across days: each finished bill is saved (keyed by a hash of the prompt), the next run continues; quota stops are "not run", not API errors
- [x] Verify on/off from ONE run: the first schema-valid read gets no feedback, so it is the single-pass result - half the quota
- [ ] Full run on all 7 bills with the new prompt (spread over days) and record first-read vs re-read numbers
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
- [x] Full answer eval: held-out 100% answered (EN+UR), 91-100% cite gold; dev 88% EN / 67% UR; out-of-scope 6/6 refused
- [x] Fixed: 3 correct answers fell back on per-sentence tagging - neighbour rule (7 of 8 tag rejections now pass; replayed on the real drafts)
- [x] Dev re-run: 0 fallbacks (Urdu was 33%); 2 questions hit Groq's rate limit - reported as errors, not scored
- [x] Router (`rehnuma-ask`): bill -> engine facts (numbers checked, template fallback), policy -> cited clauses, both -> two labelled sections, needs-bill -> asks for a photo
- [x] Router eval (`rehnuma-eval-route`): held-out batch 1 EN 9/10 UR 4/6 (fixed, moved to dev); batch 2 EN 3/5 UR 5/5 (misses left as measurement)
- [x] Works without an LLM: bill questions get the template summary; rules questions get the clause list, or "unavailable" for Urdu
- [ ] Known limits: p4 omits the switch to net billing; router misses "legally" / "import"; c3-ur and c5 to re-run after the rate limit
- [x] First live "both" question (FPA legality, Urdu): bill part correct numbers; rules part honest NOT_FOUND (corpus gap, see Backlog)
- [x] Fixed: bill part said "yes" under a legality question and pointed to text "above" - prompt rules (facts only, no yes/no, answer stands alone)
- [ ] Real questions from neighbours (round 4) through `rehnuma-ask` - the real router test
- [ ] Route bill questions to the engine (RAG explains rules, the engine does the arithmetic)

## Milestone 5 — Forecasting (both segments) + solar planner
- [x] 5a Next-12-months units from the bill's own history (same month last year, neighbour-month range) - `rehnuma-forecast` (see FORECAST.md)
- [x] Evidence for own-history forecasting: household profiles correlate +0.89 (two summer peakers) and -0.49 / -0.48 (one winter peaker)
- [x] 5b Rupees at today's rates: audited slab engine + ED + GST + fixed charge; protected status re-decided every month, so one month over 200 costs the next six
- [x] 200-unit and slab-edge watch: months within 15% of an edge, priced through the full 12-month path (iesco-2021-01: holding June at 200 saves ~Rs 13,130, ~Rs 1,190 per unit not used)
- [x] Fixed: "keeps protected rates" was claimed for months after an earlier crossing - now only when later months actually change
- [x] Fixed: first counterfactual told a 558-unit household to cut to 200 - advice limited to months in reach
- [x] `rehnuma-eval-forecast`: backtest (n = 0 - no same-household pairs yet, reported as not measured), seasonality, engine reproduces 3/3 printed energy charges (gated in CI)
- [ ] Backtest number: bills from the same households 6-12 months apart
- [x] Outlook in the API (`outlook` on every sample/upload, no LLM so free) and on the website: 12-month chart (months over 200 in amber, hover for range, protected status and bill) + the advice lines, Urdu/English
- [x] 5c Solar: last 12 months rebuilt from the balance history (settlements, import months, in-cycle charge level) - 6/6 months match their own bills, gated in CI
- [x] Fixed: the bill's own month used "current bill" (Mar-26: -872) - the balance moved +292 because the fuel adjustment is billed on top
- [x] Measured: last year's rupees as a forecast missed by -68% over Apr-Sep 2026 (in-cycle months 2-3x dearer, smaller June settlement) - so no solar rupee forecast
- [x] Renewal comparison (reg. 21(2) -> reg. 14 net billing) on the real Jul-Sep 2026 cycle: Rs 55,420-61,590 more for that quarter (rates secondary, cited in solar_rates.json)
- [x] Settlement hypothesis (netting + power purchase price for the surplus) explains the Jul-Sep 2026 cycle within 6.5%
- [x] Solar card on the website: 12-month charges/credits chart + the renewal box
- [ ] Solar planner: PVGIS yield + 2026 net billing (buyback at national average energy purchase price) vs grandfathered net metering

## Milestone 6 — LLMOps
- [x] Langfuse tracing (optional `obs` extra): api -> assistant -> bill/policy answer -> retrieve -> each LLM/vision call, with the critic's problems per draft on the span (docs/OPERATIONS.md)
- [x] Tracing can't hurt the product: off without keys, failures swallowed, 10+ digit numbers masked, photo bytes never sent, tests never trace - 6 tests with the real SDK and an in-memory exporter
- [x] Found while testing: the SDK keeps one client per public key - a second test's exporter silently got no spans; fixed with a fresh key per test
- [x] `rehnuma-ci-evals`: every no-API eval in one gate (auditor, template summaries, retrieval lexical + production rewrites replayed from a frozen file, router) - 18 metrics, fails if any drops below `data/eval/ci_thresholds.json`
- [x] Fixed (found by the gate's first run): a floor rounded UP (15/16 -> 0.938) failed on its own value - floors are rounded down, a test guards it
- [x] Renamed or missing metrics fail the gate (a metric can't silently stop being checked)
- [x] GitHub Actions (`.github/workflows/ci.yml`): ruff + pytest + eval gate + web lint/build on every push - first run green (backend 18 s, web 28 s)
- [x] Policy watcher: `rehnuma-policy watch` re-downloads the NEPRA PDFs and compares with the lock (read only); weekly GitHub workflow opens a `policy-watch` issue on a change (exit 3) and goes red when NEPRA is unreachable for every file (exit 4) - a blind run must not look like "no change"
- [ ] First scheduled watch run on GitHub (does nepra.org.pk answer GitHub's runners?)

## Milestone 7 — Live product (in progress)
Decisions: backend on Render (Docker, free tier; Hugging Face Docker Spaces now need PRO); frontend on Vercel; sample bills free, live uploads/questions rate-limited per visitor (5 uploads, 20 questions a day) so the free Groq/Gemini quota survives strangers.
- [x] 7a FastAPI backend (`rehnuma-api`): health, samples (bill + audit + Urdu/English summary, free), photo upload (verify loop; photo never stored), ask (router; cached per sample question)
- [x] Citations carry the official PDF link + page (`...pdf#page=12`)
- [x] Per-visitor daily limits behind the proxy (X-Forwarded-For), `Retry-After` until midnight UTC
- [x] Degrades without keys: summaries from the template, rules from the clause list; degraded answers never cached
- [x] API tests (fake LLM + vision, real samples + real clause index): incl. "the photo is never written to disk"
- [x] Dockerfile (non-root, PORT from env, ships labels + clause index only; photos, PDFs, .env excluded)
- [x] 7b Deployed on Render: https://rehnuma-api-3e5t.onrender.com - health, samples and a live Urdu `/api/ask` verified (route bill, LLM answer, repeat served from cache)
- [x] Removed the Hugging Face deploy files
- [x] 7c Next.js site in `web/`: home (what it does, the 5 NEPRA documents), accuracy page (evals, real bugs, known limits), GitHub link, bottom-left chat (sample bills, photo upload, Urdu/English, clickable citations to the PDF page)
- [x] Chat handles the free server's cold start ("waking up" notice; the page pings `/api/health` on load), 429 limits and expired uploads
- [ ] 7c Deploy `web/` to Vercel (root directory `web`)
- [ ] 7d Set `REHNUMA_CORS_ORIGINS` on Render to the Vercel URL; end-to-end check on the live site
- [x] Fixed: CORS setting pasted with a trailing slash ("https://x.vercel.app/") never matches a browser origin - slashes, spaces and newlines are now stripped (seen while deploying)
- [x] Chat polish: bill cards follow the language toggle; bill chips scroll without a scrollbar
- [ ] Found live: bill answer said "you ALREADY have Rs 134,041 credit" - that total includes this month's Rs 19,285 (numbers right, relation wrong; the critic checks numbers, not meaning) - send the carried-over balance as its own fact
- [ ] Image-level PII blurring before upload (milestone 3 item; matters once real users upload)

## Backlog — waiting on sources or data
- [ ] Add the legal basis for FPA to the policy corpus (NEPRA Act 1997 s. 31(7) + monthly fuel-charge-adjustment decisions) — *"is the FPA on my bill legal?" correctly got NOT_FOUND: none of the 5 documents cover it, and FPA is among the most common complaints*
- [ ] Get S.R.O. 279(I)/2026 itself and upgrade the 2026 schedule to `official` — *needs the official PDF*
- [ ] ToU (A-1b) and net-metering slabs; fixed charges and their GST treatment — *needs the same SRO*
- [ ] Open questions in FINDINGS.md: LP surcharge base, status codes (`LK`, `SS`), Q1 vs Q3 netting — *needs regulation text / more bills*
- [ ] History rows older than last month are not verifiable from one bill (Gemini misread digits and one sign there, still "verified") — *needs consecutive bills to cross-check, or a documented limit*
- [ ] Stronger multilingual embeddings (`BAAI/bge-m3`) for Urdu without an LLM call — *e5-small reached 17% hit@5 on raw Urdu*
- [ ] Net Metering Regs 2015 reg. 8 heading is OCR'd as "S. Termination of Agrei" — its text stays under reg. 7 (known limit)
