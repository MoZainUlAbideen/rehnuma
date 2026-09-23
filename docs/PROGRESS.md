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
- [ ] You: verify the flagged `uncertain_fields` against the paper Mar-26 bill
- [ ] You: push to GitHub

## Milestone 2 — Tariff rates + synthetic generator
- [ ] Source NEPRA tariff tables (conventional slabs, protected rules, ToU rates, FPA/QTA history)
- [ ] Tariff engine: compute a bill *from scratch* (not just reconcile it)
- [ ] Resolve open questions in FINDINGS.md
- [ ] Synthetic bill generator: both layouts, both connection types, error injection
- [ ] Collect 2–3 real conventional (non-solar) bills

## Milestone 3 — Vision extraction + PII redaction
## Milestone 4 — NEPRA visual RAG + agent graph with critic
## Milestone 5 — Forecasting (both segments) + solar planner (PVGIS, 2026 net billing)
## Milestone 6 — LLMOps: Langfuse tracing, evals in CI, tariff-change watcher
## Milestone 7 — Live FastAPI backend + Next.js frontend, deploy
