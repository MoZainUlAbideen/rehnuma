"""Answer eval for the NEPRA policy guide: cited, checked, in the user's language - or refused.

  uv run rehnuma-eval-answer --split heldout \
      --replay reports/policy_eval/retrieval_rewrite-all/report.json
  uv run rehnuma-eval-answer --only p4,p4-ur,o3          # a few questions, quick look

For every answerable question (the retrieval eval's questions, same gold clauses):
  * answered        - a draft passed the critic (first try or after one retry)
  * first-draft pass - passed without feedback
  * fallback        - two drafts failed; the user got the list of clauses instead
  * false refusal   - said NOT_FOUND although the documents answer it
  * cites gold      - the answer cites the clause that actually answers the question
  * fact correct    - for questions with a checkable fact (mostly numbers), the answer has it
Out-of-scope questions (inverter brands, next month's prices, passports) must be REFUSED.

Groq free tier: every question is 1 rewrite + 1-2 answer calls of ~2k tokens. --replay
reuses the retrieval eval's rewrites (no rewrite calls); run one split per day if the daily
token limit bites.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from rehnuma.evals.policy_retrieval_eval import QUESTIONS, load_replay, matches
from rehnuma.policy.answer import Answer, answer, numbers_in
from rehnuma.policy.parse import load_chunks
from rehnuma.policy.retrieve import PolicyIndex
from rehnuma.policy.sources import load_sources

ANSWER_EVAL = Path("data/policy/answer_eval.json")


def fact_present(text: str, alternatives: list[str]) -> bool:
    """A digit-only alternative must match a whole number ("2" is not in "2026")."""
    low, nums = text.lower(), numbers_in(text)
    for alt in alternatives:
        if re.fullmatch(r"[\d۰-۹]+", alt):
            if numbers_in(alt) <= nums:
                return True
        elif alt.lower() in low:
            return True
    return False


def score(a: Answer, q: dict, facts: dict) -> dict:
    row = {"id": q["id"], "lang": q["lang"], "split": q.get("split", "oos"),
           "status": a.status, "attempts": len(a.drafts), "seconds": round(a.seconds, 1),
           "calls": a.calls, "rewrite": a.rewrite, "answer": a.render(),
           "drafts": [{"text": d, "problems": p} for d, p in a.drafts],
           "sources": [f"{s.tag} {s.chunk.doc_id}:{s.chunk.clause}" for s in a.sources]}
    row["first_draft_pass"] = a.status == "answered" and len(a.drafts) == 1
    if "gold" in q:
        row["gold_retrieved"] = any(matches(s.chunk, g) for s in a.sources for g in q["gold"])
        row["cites_gold"] = any(matches(s.chunk, g) for s in a.cited for g in q["gold"])
        if q["id"] in facts and a.status == "answered":
            row["fact_ok"] = all(fact_present(a.text, alts) for alts in facts[q["id"]])
    return row


def summarize(rows: list[dict]) -> dict:
    def rate(rs, key, cond=lambda r: True):
        rs = [r for r in rs if cond(r)]
        return (sum(bool(r.get(key)) for r in rs) / len(rs), len(rs)) if rs else (None, 0)

    out = {}
    answerable = [r for r in rows if r["split"] != "oos"]
    for group in sorted({f"{r['split']}/{r['lang']}" for r in answerable}):
        rs = [r for r in answerable if f"{r['split']}/{r['lang']}" == group]
        answered = lambda r: r["status"] == "answered"                      # noqa: E731
        out[group] = {
            "n": len(rs),
            "answered": sum(answered(r) for r in rs) / len(rs),
            "first_draft_pass": sum(r["first_draft_pass"] for r in rs) / len(rs),
            "fallback": sum(r["status"] == "fallback" for r in rs) / len(rs),
            "false_refusal": sum(r["status"] == "refused" for r in rs) / len(rs),
            "error": sum(r["status"] == "error" for r in rs) / len(rs),
            "gold_retrieved": rate(rs, "gold_retrieved")[0],
            "cites_gold": rate(rs, "cites_gold", answered),
            "fact_ok": rate(rs, "fact_ok", lambda r: "fact_ok" in r),
        }
    oos = [r for r in rows if r["split"] == "oos"]
    if oos:
        out["out_of_scope"] = {
            "n": len(oos),
            "refused": sum(r["status"] == "refused" for r in oos) / len(oos),
            "answered_anyway": sum(r["status"] == "answered" for r in oos) / len(oos),
            "fallback": sum(r["status"] == "fallback" for r in oos) / len(oos),
        }
    return out


def _pct(x) -> str:
    if x is None:
        return "-"
    if isinstance(x, tuple):
        v, n = x
        return "-" if v is None else f"{v:.0%} (n={n})"
    return f"{x:.0%}"


def render(rep: dict) -> str:
    s = rep["summary"]
    lines = [f"# Policy answer eval ({rep['model']})", "",
             f"{rep['n']} questions; {rep['calls']} LLM calls; mean "
             f"{rep['mean_seconds']:.1f} s per question. Rewrites: {rep['rewrites']}.", "",
             "| Split/lang | n | answered | first draft | fallback | false refusal | error | "
             "gold retrieved | cites gold | fact correct |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for g, m in s.items():
        if g == "out_of_scope":
            continue
        lines.append(f"| {g} | {m['n']} | {_pct(m['answered'])} | {_pct(m['first_draft_pass'])} | "
                     f"{_pct(m['fallback'])} | {_pct(m['false_refusal'])} | {_pct(m['error'])} | "
                     f"{_pct(m['gold_retrieved'])} | {_pct(m['cites_gold'])} | "
                     f"{_pct(m['fact_ok'])} |")
    if "out_of_scope" in s:
        o = s["out_of_scope"]
        lines += ["", "| Out of scope | n | refused | answered anyway | fallback |",
                  "|---|---|---|---|---|",
                  f"| all | {o['n']} | {_pct(o['refused'])} | {_pct(o['answered_anyway'])} | "
                  f"{_pct(o['fallback'])} |"]
    lines += ["", "| Question | Status | Attempts | Cites gold | Fact | Critic problems |",
              "|---|---|---|---|---|---|"]
    for r in rep["rows"]:
        probs = "; ".join(p for d in r["drafts"] for p in d["problems"])[:140] or "-"
        yn = {True: "yes", False: "**no**", None: "-"}
        lines.append(f"| {r['id']} | {r['status']} | {r['attempts']} | "
                     f"{yn[r.get('cites_gold')]} | {yn[r.get('fact_ok')]} | {probs} |")
    return "\n".join(lines) + "\n"


def samples(rep: dict) -> str:
    out = [f"# Answer samples ({rep['model']})", ""]
    for r in rep["rows"]:
        out += [f"## {r['id']} ({r['lang']}, {r['status']})", "",
                f"Search rewrite: {r['rewrite'] or '-'}", "",
                f"Retrieved: {', '.join(r['sources'])}", "", r["answer"], ""]
        for i, d in enumerate(r["drafts"], 1):
            if d["problems"]:
                out += [f"<details><summary>Rejected draft {i}: {'; '.join(d['problems'])}"
                        "</summary>", "", d["text"], "", "</details>", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Answer eval for the NEPRA policy guide")
    ap.add_argument("--split", default="all", choices=["all", "dev", "heldout", "oos"])
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    ap.add_argument("--replay", default=None, help="retrieval report.json whose rewrites to reuse")
    ap.add_argument("--model", default=None)
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between questions")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from rehnuma.llm.client import GroqClient
    client = GroqClient(args.model, temperature=0.0, max_tokens=700)
    cfg = json.loads(ANSWER_EVAL.read_text(encoding="utf-8"))
    answerable = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    oos = [{**q, "split": "oos"} for q in cfg["out_of_scope"]]
    qs = [q for q in answerable + oos
          if args.split == "all" or q.get("split") == args.split]
    if args.only:
        wanted = set(args.only.split(","))
        qs = [q for q in answerable + oos if q["id"] in wanted]
    replay = load_replay(Path(args.replay)) if args.replay else {}

    index = PolicyIndex(load_chunks())
    docs = {d.id: d for d in load_sources()}
    rows, start = [], time.perf_counter()
    for i, q in enumerate(qs):
        if i and args.pause:
            time.sleep(args.pause)
        rw = replay.get(q["id"])
        if rw and q["lang"] == "en" and rw.startswith(q["q"]):      # old report format
            rw = rw[len(q["q"]):].strip()
        print(f"[{i + 1}/{len(qs)}] {q['id']} ...", end=" ", flush=True)
        a = answer(q["q"], index, client, lang=q["lang"], rewritten=rw, docs=docs)
        print(f"{a.status} ({len(a.drafts)} draft(s), {a.seconds:.1f} s)", flush=True)
        rows.append(score(a, q, cfg["facts"]))

    rep = {"model": client.name, "n": len(rows), "rewrites": "replayed" if replay else "live",
           "calls": sum(r["calls"] for r in rows),
           "mean_seconds": sum(r["seconds"] for r in rows) / (len(rows) or 1),
           "wall_seconds": round(time.perf_counter() - start),
           "summary": summarize(rows), "rows": rows}
    name = "answers" + ("" if args.split == "all" else f"_{args.split}") + \
        ("_only" if args.only else "")
    out = Path("reports/policy_eval") / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    (out / "samples.md").write_text(samples(rep), encoding="utf-8")
    md = render(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
