"""rehnuma-policy: build and query the NEPRA clause index.

  uv run rehnuma-policy fetch                 # download the PDFs listed in sources.json
  uv run rehnuma-policy fetch --force         # re-download; reports CHANGED files
  uv run rehnuma-policy ingest                # PDFs -> data/policy/chunks.jsonl (+ report)
  uv run rehnuma-policy search "can my solar be bigger than my sanctioned load"
  uv run rehnuma-policy search "کیا میرا سولر منظور شدہ لوڈ سے بڑا ہو سکتا ہے" --method hybrid+dense
  uv run rehnuma-policy ask "میرا نیٹ میٹرنگ 2026 سے پہلے لگا تھا، اب یونٹ کس ریٹ پر گنے جائیں گے؟"
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from rehnuma.policy.parse import CHUNKS, extract_pages, load_chunks, parse_document, save_chunks
from rehnuma.policy.retrieve import ALL_METHODS, PolicyIndex
from rehnuma.policy.sources import fetch, load_sources


def _top_level(chunks) -> str:
    tops = list(dict.fromkeys(c.path[0] for c in chunks))
    return ", ".join(tops if len(tops) <= 14 else tops[:6] + ["..."] + tops[-6:])


def ingest() -> int:
    all_chunks = []
    for doc in load_sources():
        if not doc.path.exists():
            print(f"MISSING  {doc.id}: run `rehnuma-policy fetch` first ({doc.path})")
            continue
        pages = extract_pages(doc.path)
        empty = sum(1 for p in pages if len(p) < 40)
        chunks = parse_document(doc, pages)
        all_chunks += chunks
        kinds = Counter("windows" if c.clause.startswith("p") and c.clause[1:].isdigit()
                        else "clauses" for c in chunks)
        print(f"{doc.id}: {len(pages)} pages, {sum(map(len, pages)):,} chars, "
              f"{len(chunks)} chunks ({dict(kinds)})")
        if empty:
            print(f"  WARNING: {empty} page(s) have no text layer (scanned) - they are missing")
        if kinds.get("windows") and doc.style != "amendment":
            print("  WARNING: clause structure not recognised - fell back to page windows")
        print(f"  top-level units: {_top_level(chunks)}")
    if not all_chunks:
        return 1
    save_chunks(all_chunks)
    print(f"\nwrote {len(all_chunks)} chunks to {CHUNKS}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NEPRA document index")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--force", action="store_true")
    sub.add_parser("ingest")
    a = sub.add_parser("ask", help="cited answer in the question's language (needs GROQ_API_KEY)")
    a.add_argument("question")
    a.add_argument("--show-drafts", action="store_true")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--k", type=int, default=5)
    s.add_argument("--method", default="hybrid", choices=ALL_METHODS)
    s.add_argument("--dense-model", default=None, help="HF model id for dense methods")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.cmd == "fetch":
        print("\n".join(fetch(load_sources(), force=args.force)))
        return 0
    if args.cmd == "ingest":
        return ingest()
    if args.cmd == "ask":
        from rehnuma.llm.client import GroqClient
        from rehnuma.policy.answer import answer
        ans = answer(args.question, PolicyIndex(load_chunks()),
                     GroqClient(temperature=0.0, max_tokens=700))
        print(ans.render())
        print(f"\n[{ans.status}, {len(ans.drafts)} draft(s), {ans.seconds:.1f} s]")
        if args.show_drafts:
            for d, problems in ans.drafts:
                print(f"\n--- draft ({'; '.join(problems) or 'passed'}) ---\n{d}")
        return 0
    chunks, dense = load_chunks(), None
    if "dense" in args.method:
        from rehnuma.policy.dense import DEFAULT_MODEL, DenseIndex, HFEncoder
        dense = DenseIndex(chunks, HFEncoder(args.dense_model or DEFAULT_MODEL))
    index = PolicyIndex(chunks, dense=dense)
    for h in index.search(args.query, k=args.k, method=args.method):
        c = h.chunk
        print(f"{h.rank}. [{c.doc_id} {c.clause}, p.{c.page}] {c.heading}  (score {h.score:.3f})")
        print(f"   {c.text[:300]}{'...' if len(c.text) > 300 else ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
