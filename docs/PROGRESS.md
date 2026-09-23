# Rehnuma — progress log

## Milestone 1 — Deterministic reconciliation engine
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

## Milestone 2 — Tariff rates + synthetic generator
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
- [ ] Get S.R.O. 279(I)/2026 itself and upgrade the 2026 schedule to `official`
- [ ] ToU (A-1b) and net-metering slabs; fixed charges and their GST treatment
- [ ] Resolve open questions in FINDINGS.md (LP surcharge base, status codes, Q1 vs Q3 netting)
- [ ] Render synthetic bills as images (feeds milestone 3)

## Milestone 2.5 — Plain-language summary (from user research)
- [x] Neighbourhood conversations recorded in USER_RESEARCH.md
- [x] BillStory: verified facts people care about (solar sent/used/banked; flat vs ToU; 200-unit limit)
- [x] Template summary, Urdu by default, English with `--lang en` (`rehnuma-summary`)
- [x] Numeric-faithfulness check: every number in a summary must come from the engine
- [x] Fixed: summary said Mar-26 "credited Rs 872"; it actually added Rs 292 (FPA billed separately)
- [ ] Show Urdu summaries to 3–5 neighbours, record feedback
- [ ] LLM summary (Groq) + critic, scored against the template baseline

## Milestone 3 — Vision extraction + PII redaction
## Milestone 4 — NEPRA visual RAG + agent graph with critic
## Milestone 5 — Forecasting (both segments) + solar planner (PVGIS, 2026 net billing)
## Milestone 6 — LLMOps: Langfuse tracing, evals in CI, tariff-change watcher
## Milestone 7 — Live FastAPI backend + Next.js frontend, deploy
