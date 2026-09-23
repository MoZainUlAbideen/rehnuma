"""`uv run rehnuma-summary data/labels/real/pesco-2026-09.json` - plain summary, Urdu by default.

  --lang en        English instead of Urdu
  --out file.md    also write the summary to a UTF-8 file (easiest way to read Urdu:
                   open it in VS Code - many Windows terminals can't join Urdu letters)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rehnuma.explain.faithfulness import check_faithfulness
from rehnuma.explain.render import LANGS, summarize
from rehnuma.explain.story import build_story
from rehnuma.loader import load_bills


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Summarise electricity bills in Urdu or English.")
    ap.add_argument("paths", nargs="+", help="JSON files, folders or glob patterns")
    ap.add_argument("--lang", choices=LANGS, default="ur")
    ap.add_argument("--out", help="write the summaries to this UTF-8 markdown file")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252

    blocks = []
    for bill in sorted(load_bills(args.paths), key=lambda b: b.bill_month):
        story = build_story(bill)
        lines = summarize(story, args.lang)
        faith = check_faithfulness("\n".join(lines), story)
        if faith.unsupported:
            raise SystemExit(f"{bill.bill_id}: unsupported numbers {faith.unsupported}")
        body = "\n".join(f"- {line}" for line in lines[1:])
        blocks.append(f"## {lines[0]}  ({bill.bill_id})\n\n{body}\n")

    text = "\n".join(blocks)
    print(text)
    if args.out:
        rtl = '<div dir="rtl">\n\n' if args.lang == "ur" else ""
        end = "\n</div>\n" if args.lang == "ur" else ""
        Path(args.out).write_text(rtl + text + end, encoding="utf-8")
        print(f"(written to {args.out})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
