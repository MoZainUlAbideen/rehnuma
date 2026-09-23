"""Summary eval on REAL bills: LLM (with critic) vs the template baseline.

  uv run rehnuma-eval-summary                     # template baseline (offline)
  uv run rehnuma-eval-summary --provider groq     # needs GROQ_API_KEY in .env

For every real bill x language it records:
  * first-draft pass rate  - did the LLM's FIRST draft pass the critic?
  * final faithfulness     - share of stated numbers found in the verified facts
  * coverage               - share of must-mention numbers that were mentioned
  * language ok            - Urdu summary really in Urdu (and English in English)
  * fallback rate          - how often the user would have got the template instead
Honest reading: first-draft numbers show how good the LLM is on its own; final numbers
show what users actually get once the critic has done its job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rehnuma.explain.llm_summary import llm_summary
from rehnuma.explain.render import summarize
from rehnuma.explain.story import build_story
from rehnuma.loader import load_bills


class TemplateClient:
    """Pretends to be an LLM by returning the template summary - the baseline."""
    name = "template"

    def __init__(self):
        self.story = None
        self.lang = "ur"

    def complete(self, system: str, user: str) -> str:
        return "\n".join(f"- {line}" for line in summarize(self.story, self.lang))


def run(bill_paths: list[str], provider: str, langs: list[str]) -> dict:
    if provider == "groq":
        from rehnuma.llm.client import GroqClient
        client = GroqClient()
    else:
        client = TemplateClient()
    rows = []
    for bill in sorted(load_bills(bill_paths), key=lambda b: b.bill_month):
        story = build_story(bill)
        for lang in langs:
            if isinstance(client, TemplateClient):
                client.story, client.lang = story, lang
            res = llm_summary(story, client, lang)
            rows.append({
                "bill_id": bill.bill_id, "lang": lang, "source": res.source,
                "attempts": res.attempts, "first_draft_passed": res.attempts == 1
                and res.source == "llm",
                "faithfulness": res.quality.faithfulness, "coverage": res.quality.coverage,
                "language_ok": res.quality.language_ok,
                "unsupported": [str(x) for x in res.quality.unsupported],
                "rejected_drafts": res.drafts_rejected,
                "latency_s": round(res.latency_s, 2), "text": res.text,
            })
    n = len(rows)

    def share(key):
        return sum(1 for r in rows if r[key]) / n if n else 0.0

    return {
        "provider": client.name, "n": n,
        "overall": {
            "first_draft_pass_rate": share("first_draft_passed"),
            "fallback_rate": sum(r["source"] == "template_fallback" for r in rows) / n,
            "mean_faithfulness": sum(r["faithfulness"] for r in rows) / n,
            "mean_coverage": sum(r["coverage"] for r in rows) / n,
            "language_ok_rate": share("language_ok"),
            "mean_attempts": sum(r["attempts"] for r in rows) / n,
        },
        "rows": rows,
    }


def render_markdown(report: dict) -> str:
    o = report["overall"]
    lines = [
        f"# Summary eval - {report['provider']}", "",
        f"{report['n']} summaries (real bills x languages).", "",
        "| Metric | Value |", "|---|---|",
        f"| First draft passed the critic | {o['first_draft_pass_rate']:.1%} |",
        f"| Fell back to template | {o['fallback_rate']:.1%} |",
        f"| Faithfulness (final) | {o['mean_faithfulness']:.1%} |",
        f"| Coverage of must-mention facts (final) | {o['mean_coverage']:.1%} |",
        f"| Correct language (final) | {o['language_ok_rate']:.1%} |",
        f"| Mean attempts | {o['mean_attempts']:.2f} |", "",
        "| Bill | Lang | Source | Attempts | Rejected drafts |", "|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        why = "; ".join(
            f"#{d['attempt']}: " + ", ".join(
                ([f"invented {', '.join(d['unsupported'])}"] if d["unsupported"] else [])
                + ([f"missed {', '.join(d['missing'])}"] if d["missing"] else [])
                + ([] if d["language_ok"] else ["wrong language"]))
            for d in r["rejected_drafts"]) or "-"
        lines.append(f"| {r['bill_id']} | {r['lang']} | {r['source']} | {r['attempts']} | {why} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate bill summaries on real bills.")
    ap.add_argument("paths", nargs="*", default=["data/labels/real"])
    ap.add_argument("--provider", choices=["template", "groq"], default="template")
    ap.add_argument("--langs", default="ur,en")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    report = run(args.paths, args.provider, args.langs.split(","))
    out = Path(args.out or f"reports/summary_eval/{args.provider}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    md = render_markdown(report)
    (out / "report.md").write_text(md, encoding="utf-8")
    samples = "\n\n".join(f"### {r['bill_id']} ({r['lang']}, {r['source']})\n\n{r['text']}"
                          for r in report["rows"])
    (out / "samples.md").write_text(samples + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
