# Rehnuma (رہنما)

**An AI copilot that audits Pakistani electricity bills and guides solar decisions — in Urdu or English.**

Pakistani electricity bills stack slab rates, protected/unprotected status, FPA, QTA,
fixed charges, ED, GST and more into one page almost nobody can read. On top of that,
NEPRA's 2026 Prosumer Regulations moved new solar users from net metering to net billing,
so the "is solar worth it?" math changed overnight.

Rehnuma reads a photo of your bill, **re-computes it rupee by rupee with a deterministic
engine**, explains every line with citations to the NEPRA rules behind it, and tells you
what to do next.

## Two kinds of households, one product

| | Conventional household (no solar) | Solar prosumer (net metering / net billing) |
|---|---|---|
| **Main question** | "Is my bill correct? Why is it so high?" | "Is my export credit correct? What is it worth?" |
| **Key checks** | slab, protected status, FPA, taxes, arrears | import/export/net, banked units, quarterly settlement |
| **Forecast** | next 12 months of bills | credit balance and settlement trajectory |
| **Solar** | Should I install? Payback under 2026 net billing | Should I expand / add batteries? |

## Status

**Milestone 1: deterministic reconciliation engine** — done.
**Milestone 2 (in progress): from-scratch levy calculator** — ED, GST, NJ surcharge and the
FPA tax calculation are recomputed from first principles and match every legacy-layout bill
(3 IESCO + 1 PESCO, 2019–2026) with zero delta. All 7 real bills (solar and non-solar)
reconcile; the one failure is a real Rs 2 inconsistency printed on a PESCO bill.
A slab engine checks protected status from the bill's own 6-month history, and an auditor
eval over 2,000 synthetic bills with 11 planted error types reports detection, localisation
and false-positive rates ([`reports/auditor_eval/report.md`](reports/auditor_eval/report.md)). See
[`docs/FINDINGS.md`](docs/FINDINGS.md) for what the real bills taught us and
[`docs/PROGRESS.md`](docs/PROGRESS.md) for the roadmap.

## Quickstart

```bash
uv sync                                  # create .venv and install everything
uv run pytest                            # run the test suite
uv run rehnuma-audit data/labels/real    # audit all real bills
uv run rehnuma-audit data/labels/real --all   # include every passing check
uv run rehnuma-eval-auditor --n 2000 --seed 42  # auditor eval on synthetic bills
uv run rehnuma-summary data/labels/real          # plain summary, Urdu (default)
uv run rehnuma-summary data/labels/real --lang en --out summary.md
uv run rehnuma-eval-summary --provider groq      # LLM summary + critic (needs .env)
uv run rehnuma-eval-extract                      # bill photo -> verified bill (needs .env)
```

## How it's built

```
src/rehnuma/
  schema.py            # Pydantic model of a bill (both layouts, both connection types)
  loader.py            # JSON label loading (UTF-8, Windows-safe globbing)
  cli.py               # rehnuma-audit command
  engine/
    checks.py          # single-bill checks: meter, net-metering bank, charges, FPA, totals
    cross_bill.py      # multi-bill checks: meter continuity, arrears, history agreement
    findings.py        # PASS / FAIL / SKIP result type + half-up rounding
    rates.py           # constants, each with its source (INFERRED ones flagged)
data/
  labels/real/         # hand-verified ground truth, PII removed (committed)
  real/                # original photos (git-ignored)
```

**Design rule:** the LLM never does arithmetic. Every number Rehnuma shows comes from
this engine; the LLM's job (later milestones) is extraction and explanation.

## Privacy

Real bill photos contain the reference number, consumer ID and address. They live in
`data/real/`, which is git-ignored. Labels in `data/labels/real/` carry no identifiers, and a
test enforces this.
