"""Retrieval eval for the NEPRA index: does the clause that answers the question come back?

  uv run rehnuma-eval-policy                # bm25 vs char vs hybrid (lexical, no API)
  uv run rehnuma-eval-policy --dense        # + multilingual HF embeddings (uv sync --extra dense)
  uv run rehnuma-eval-policy --rewrite      # + Groq rewrites Urdu questions to English
  uv run rehnuma-eval-policy --rewrite all  # + English questions rewritten into NEPRA wording
  uv run rehnuma-eval-policy --rewrite all --replay <earlier report.json>
                                            # reuse that run's rewrites: no API calls, repeatable

Two failure kinds are kept apart, because they have different fixes:
  * gold NOT IN INDEX - the parser never produced the clause (fix the parser)
  * gold in index but not retrieved - a ranking failure (fix retrieval)
Hit rates are computed over questions whose gold IS in the index, and the parser misses
are listed separately, so a parsing bug cannot masquerade as a retrieval score.

Questions are split: `dev` (seen while tuning) and `heldout` (written from the clause text
before any tuning, never tuned on). A method that only wins on dev is overfitting.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rehnuma.policy.parse import Chunk, load_chunks
from rehnuma.policy.query import MODES, needs_rewrite, rewrite, search_queries
from rehnuma.policy.retrieve import PolicyIndex

QUESTIONS = Path("data/policy/retrieval_questions.json")
K = 5


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def matches(chunk: Chunk, gold: dict) -> bool:
    path = gold.get("path", [])
    return (chunk.doc_id == gold["doc"] and chunk.path[:len(path)] == path
            and (not gold.get("contains")
                 or _squash(gold["contains"]) in _squash(chunk.search_text)))


def load_replay(path: Path) -> dict[str, str]:
    """question id -> rewrite, from an earlier report. Older reports stored the searched
    string (English: original + " " + rewrite), so the original prefix is stripped."""
    rep = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for r in rep["rows"]:
        if r.get("rewrite"):
            out[r["id"]] = r["rewrite"]
        elif r.get("query") and r.get("rewrite_error") is None:
            out[r["id"]] = r["query"]
    return out


def evaluate(index: PolicyIndex, questions: list[dict], client=None,
             rewrite_mode: str = "urdu", replay: dict[str, str] | None = None) -> dict:
    methods = index.methods
    rows = []
    for q in questions:
        in_index = any(matches(c, g) for c in index.chunks for g in q["gold"])
        wanted = replay is not None and (rewrite_mode == "all" or needs_rewrite(q["q"]))
        if wanted:
            rewritten, err = replay.get(q["id"]), None
            if rewritten and not needs_rewrite(q["q"]) and rewritten.startswith(q["q"]):
                rewritten = rewritten[len(q["q"]):].strip() or None     # old report format
        else:
            rewritten, err = rewrite(q["q"], client, rewrite_mode)
        primary, also = search_queries(q["q"], rewritten)
        row = {"id": q["id"], "lang": q["lang"], "split": q.get("split", "dev"),
               "in_index": in_index, "rewrite": rewritten, "rewrite_error": err,
               "by_method": {}}
        for m in methods:
            hits = index.search(primary, k=K, method=m, also=also)
            rank = next((h.rank for h in hits if any(matches(h.chunk, g) for g in q["gold"])),
                        None)
            row["by_method"][m] = {"rank": rank,
                                   "top": [f"{h.chunk.doc_id}:{h.chunk.clause}" for h in hits[:3]]}
        rows.append(row)

    def agg(rs, m):
        rs = [r for r in rs if r["in_index"]]
        n = len(rs) or 1
        ranks = [r["by_method"][m]["rank"] for r in rs]
        return {"n": len(rs),
                "hit@1": sum(r == 1 for r in ranks) / n,
                f"hit@{K}": sum(r is not None for r in ranks) / n,
                "mrr": sum(1 / r for r in ranks if r) / n}

    groups = sorted({(r["split"], r["lang"]) for r in rows})
    summary = {f"{s}/{lang}": {m: agg([r for r in rows if (r["split"], r["lang"]) == (s, lang)], m)
                               for m in methods} for s, lang in groups}
    source = "replay" if replay is not None else (client.name if client else None)
    return {"rewrite": f"{rewrite_mode} via {source}" if source else None,
            "dense": index.dense.encoder.name if index.dense else None,
            "methods": list(methods), "n": len(rows),
            "not_in_index": [r["id"] for r in rows if not r["in_index"]],
            "summary": summary, "rows": rows}


def render(rep: dict) -> str:
    methods = rep["methods"]
    lines = [f"# Policy retrieval eval (Urdu rewrite: {rep['rewrite'] or 'off'}; "
             f"dense: {rep['dense'] or 'off'})", "",
             f"{rep['n']} questions. dev = seen while tuning; heldout = never tuned on. Hit rates "
             f"count only questions whose gold clause the parser produced.", ""]
    if rep["not_in_index"]:
        lines += [f"**Gold clause NOT in index (parser misses):** {', '.join(rep['not_in_index'])}",
                  ""]
    lines += ["| Split/lang | Method | n | hit@1 | hit@5 | MRR |", "|---|---|---|---|---|---|"]
    for group, by_m in rep["summary"].items():
        for m, s in by_m.items():
            lines.append(f"| {group} | {m} | {s['n']} | {s['hit@1']:.0%} | {s[f'hit@{K}']:.0%} | "
                         f"{s['mrr']:.2f} |")
    best = methods[-1]
    lines += ["", "| Question | In index | " + " | ".join(methods) + f" | {best} top-3 |",
              "|---|---|" + "---|" * (len(methods) + 1)]
    for r in rep["rows"]:
        ranks = [str(r["by_method"][m]["rank"] or "-") for m in methods]
        top = ", ".join(r["by_method"][best]["top"])
        lines.append(f"| {r['id']} | {'yes' if r['in_index'] else '**no**'} | "
                     + " | ".join(ranks) + f" | {top} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Retrieval eval over the NEPRA clause index")
    ap.add_argument("--rewrite", nargs="?", const="urdu", choices=MODES, default=None,
                    help="Groq query rewrite: 'urdu' (default) or 'all' (English too)")
    ap.add_argument("--model", default=None, help="Groq model for --rewrite")
    ap.add_argument("--replay", default=None,
                    help="reuse rewrites from an earlier report.json instead of calling Groq")
    ap.add_argument("--dense", action="store_true", help="add the HF embedding ranker")
    ap.add_argument("--dense-model", default=None, help="HF model id (default e5-small)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    chunks = load_chunks()

    dense = None
    if args.dense:
        from rehnuma.policy.dense import DEFAULT_MODEL, DenseIndex, HFEncoder
        encoder = HFEncoder(args.dense_model or DEFAULT_MODEL)
        dense = DenseIndex(chunks, encoder)
        print(f"dense: {encoder.name}, {dense.encoded} chunk(s) encoded (rest from cache)")
    client, replay = None, None
    if args.replay:
        replay = load_replay(Path(args.replay))
        args.rewrite = args.rewrite or "urdu"
        print(f"replaying {len(replay)} rewrites from {args.replay}")
    elif args.rewrite:
        from rehnuma.llm.client import GroqClient
        client = GroqClient(args.model, temperature=0.0, max_tokens=400)
        n = (len(questions) if args.rewrite == "all"
             else sum(needs_rewrite(q["q"]) for q in questions))
        print(f"rewriting {n} questions ({args.rewrite})...")

    rep = evaluate(PolicyIndex(chunks, dense=dense), questions, client=client,
                   rewrite_mode=args.rewrite or "urdu", replay=replay)
    name = ("retrieval" + ("_dense" if dense else "")
            + (f"_rewrite-{args.rewrite}" if (client or replay) else "")
            + ("_replay" if replay else ""))
    out = Path("reports/policy_eval") / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    md = render(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
