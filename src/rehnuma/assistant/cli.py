"""rehnuma-ask: one question to Rehnuma - about your bill, the rules, or both.

  uv run rehnuma-ask "کیا میرے بل پر لگا ہوا ایف پی اے قانون کے مطابق ہے؟" \
      --bill data/labels/real/pesco-2026-03.json
  uv run rehnuma-ask "Can my solar be bigger than my sanctioned load?"
  uv run rehnuma-ask "Why is my bill negative?" --bill data/labels/real/pesco-2026-09.json --why
"""

from __future__ import annotations

import argparse
import sys

from rehnuma.assistant.assistant import ask
from rehnuma.loader import load_bill
from rehnuma.policy.parse import load_chunks
from rehnuma.policy.retrieve import PolicyIndex


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ask Rehnuma about your bill or the rules")
    ap.add_argument("question")
    ap.add_argument("--bill", default=None, help="a bill JSON (a verified extraction or label)")
    ap.add_argument("--lang", choices=["ur", "en"], default=None)
    ap.add_argument("--no-llm", action="store_true", help="template bill answer; no Groq")
    ap.add_argument("--why", action="store_true", help="show the route and the drafts")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = None
    if not args.no_llm:
        from rehnuma.llm.client import GroqClient
        client = GroqClient(temperature=0.0, max_tokens=700)
    bill = load_bill(args.bill) if args.bill else None
    reply = ask(args.question, PolicyIndex(load_chunks()), client, bill=bill, lang=args.lang)
    print(reply.render())
    if args.why:
        print(f"\n[route: {reply.route.kind} - {reply.route.reason}]")
        for name, part in (("bill", reply.bill), ("policy", reply.policy)):
            if part:
                for d, probs in part.drafts:
                    print(f"\n--- {name} draft ({'; '.join(probs) or 'passed'}) ---\n{d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
