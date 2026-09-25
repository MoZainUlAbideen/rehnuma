# Operations (milestone 6): evals in CI, tracing, policy watcher

## 1. Evals in CI - `.github/workflows/ci.yml`

Every push runs ruff, the test suite and `rehnuma-ci-evals`: every eval that needs no API
key, checked against the limits in `data/eval/ci_thresholds.json` (auditor, template
summaries, retrieval lexical and with frozen production rewrites, router, forecast engine,
solar reconstruction). A metric below its limit - or a metric that disappears - fails the
build. The table shows on the run's summary page. The web job lints and builds the site.

## 2. Tracing - Langfuse, optional (`src/rehnuma/obs.py`)

Off unless the `obs` extra is installed AND `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are
set. One question = one trace:

```
api.ask            question, sample / upload, cached?, route
└ assistant.ask    route decision, final reply
  ├ bill.answer    source (llm / template_fallback), critic problems per draft
  │ └ llm          prompt, draft, tokens, latency
  └ policy.answer  status, rewrite, cited clauses, critic problems per draft
    ├ llm          query rewrite
    ├ retrieve     query + the clauses returned
    └ llm          answer draft(s)
api.extract        photo type and size (never the photo)
└ extract_bill     attempts, verified, failed checks, quota
  └ vision         prompt, output, tokens
```

What it answers that logs couldn't: why an answer fell back (the critic's problems per draft
are on the span), which clauses retrieval returned for a wrong answer, where latency goes
(rewrite vs answer vs retry), and token use per route against the free-tier limits.

Guarantees, each with a test (`tests/test_obs.py`):
- no keys -> no-ops; a broken or unreachable Langfuse never breaks or slows a request
  (checked live: 0.3 s answer with Langfuse pointed at a dead port);
- errors inside traced code still propagate;
- runs of 10+ digits (phone, CNIC, reference numbers) are masked before leaving the process;
- photo bytes never reach a trace;
- the test suite never sends traces, even with keys in your `.env`.

## 3. Policy watcher - `.github/workflows/policy-watch.yml`

Every Monday 04:00 UTC (and on demand), `rehnuma-policy watch` re-downloads the five NEPRA
PDFs and compares their SHA-256 with the committed `data/policy/sources.lock.json`. It writes
nothing: a change is a question for a human, not an automatic update.

| Exit | Meaning | What the workflow does |
|---|---|---|
| 0 | no change | green run, report on the summary page |
| 3 | a document changed | opens (or comments on) a `policy-watch` issue with the review steps |
| 4 | NEPRA unreachable for every file | red run - a blind watcher must not look like "no change" |

Known limit: it watches the five files Rehnuma already uses. A NEW regulation (e.g. the
fuel-adjustment legal basis in the backlog) is not discovered automatically.
