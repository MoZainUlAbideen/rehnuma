"""Router eval: does each question go to the right part of Rehnuma? No API needed.

  uv run rehnuma-eval-route

Reports accuracy per split and language and a confusion matrix. The costly mistakes are
not symmetric: a rules question sent to the bill engine gets no citation; a bill question
sent to the policy guide gets a correct rule but no answer about the user's own numbers.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from rehnuma.assistant.route import BILL, BOTH, POLICY, classify

QUESTIONS = Path("data/assistant/route_questions.json")
KINDS = (BILL, POLICY, BOTH)


def evaluate(questions: list[dict]) -> dict:
    rows = [{**q, "got": classify(q["q"])} for q in questions]
    for r in rows:
        r["ok"] = r["got"] == r["route"]
    groups = {}
    for key in sorted({(r["split"], r["lang"]) for r in rows}):
        rs = [r for r in rows if (r["split"], r["lang"]) == key]
        groups[f"{key[0]}/{key[1]}"] = {"n": len(rs),
                                        "accuracy": sum(r["ok"] for r in rs) / len(rs)}
    confusion = Counter((r["route"], r["got"]) for r in rows)
    return {"n": len(rows), "groups": groups,
            "confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
            "rows": rows}


def render(rep: dict) -> str:
    lines = ["# Router eval", "", "| Split/lang | n | accuracy |", "|---|---|---|"]
    lines += [f"| {g} | {m['n']} | {m['accuracy']:.0%} |" for g, m in rep["groups"].items()]
    lines += ["", "Confusion (expected -> got), all splits:", "",
              "| expected \\ got | " + " | ".join(KINDS) + " |", "|---|" + "---|" * len(KINDS)]
    for a in KINDS:
        lines.append(f"| {a} | " + " | ".join(str(rep["confusion"].get(f"{a}->{b}", 0))
                                             for b in KINDS) + " |")
    wrong = [r for r in rep["rows"] if not r["ok"]]
    if wrong:
        lines += ["", "Misrouted:", ""]
        lines += [f"- {r['id']} ({r['split']}, {r['lang']}): expected {r['route']}, got "
                  f"{r['got']} - {r['q']}" for r in wrong]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rep = evaluate(json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"])
    out = Path("reports/route_eval")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    md = render(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
