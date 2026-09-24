"""Extraction eval on REAL bill photos against hand-verified labels.

  uv run rehnuma-eval-extract                          # Gemini, verify loop on
  uv run rehnuma-eval-extract --no-verify              # ablation: single pass
  uv run rehnuma-eval-extract --only iesco-2023-03     # one bill, quick check
  uv run rehnuma-eval-extract --list-models            # which vision models your key has

Pairs every image in data/real/ with the label of the same name in data/labels/real/
(pesco-2026-09.jpg <-> pesco-2026-09.json). Reports, per bill and per layout:
  * field accuracy     - share of labelled fields read exactly right
  * key-field accuracy - amount to pay, due date, arrears, current bill, tariff, ...
  * reconciles         - the extracted bill passed every reconciliation check
    (bills with a documented real anomaly are expected to fail exactly that check)
Accuracy is computed ONLY over bills the model actually read. API failures (quota,
overload) are counted separately: scoring them as 0% once made a Gemini outage look
like the model could not read a single digit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rehnuma.engine import Status, audit_bill
from rehnuma.extract.compare import compare
from rehnuma.extract.pipeline import extract_bill
from rehnuma.extract.vision_client import OpenAICompatVision
from rehnuma.loader import load_bill

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ANOMALIES = Path("data/eval/expected_anomalies.json")


def expected_fails(bill_id: str) -> set[str]:
    if not ANOMALIES.exists():
        return set()
    data = json.loads(ANOMALIES.read_text(encoding="utf-8"))
    return {a["check"] for a in data.get(bill_id, [])}


def pairs(images: Path, labels: Path, only: str | None = None) -> list[tuple[Path, Path]]:
    out = []
    for img in sorted(images.iterdir()):
        if img.suffix.lower() not in IMAGE_EXT or (only and img.stem != only):
            continue
        label = labels / f"{img.stem}.json"
        if label.exists():
            out.append((img, label))
        else:
            # Never skip silently: a double extension (bill.jpg.jpeg) once hid 5 of 7 bills
            print(f"WARNING: no label for {img.name} (expected {label.name}) - skipped")
    return out


def run(images: Path, labels: Path, client, verify: bool, pause: float = 0.0,
        only: str | None = None) -> dict:
    rows = []
    todo = pairs(images, labels, only)
    for i, (img, lab) in enumerate(todo):
        if i and pause:
            time.sleep(pause)                    # stay under per-minute quotas
        label = load_bill(lab)
        print(f"[{i + 1}/{len(todo)}] reading {img.name} ...", end=" ", flush=True)
        res = extract_bill(img, client, label.bill_id, verify=verify)
        last = res.attempts[-1] if res.attempts else None
        status = ("verified" if res.verified
                  else f"ERROR: {last.error[:150]}" if last and last.error and res.bill is None
                  else "NOT verified (read, but checks failed)")
        print(f"{len(res.attempts)} attempt(s), {res.seconds:.0f} s, {status}", flush=True)
        cmp = compare(label, res.bill)
        fails = ({f.check for f in audit_bill(res.bill) if f.status == Status.FAIL}
                 if res.bill else set())
        rows.append({
            "bill_id": label.bill_id, "layout": label.layout.value,
            "read": res.bill is not None,
            "field_accuracy": cmp.accuracy, "key_accuracy": cmp.key_accuracy(),
            "fields": cmp.total, "wrong": [[k, str(e), str(g)] for k, e, g in cmp.wrong],
            "missing": cmp.missing, "extra": cmp.extra,
            "reconciles": res.bill is not None and fails == expected_fails(label.bill_id),
            "failed_checks": sorted(fails), "attempts": len(res.attempts),
            "errors": [a.error for a in res.attempts if a.error],
            "seconds": round(res.seconds, 1),
            "extracted": res.bill.model_dump(mode="json") if res.bill else None,
        })
    read = [r for r in rows if r["read"]]
    n_read = len(read) or 1
    fields = sum(r["fields"] for r in read) or 1
    by_layout: dict[str, list] = {}
    for r in read:
        by_layout.setdefault(r["layout"], []).append(r)
    return {
        "provider": client.name, "verify": verify, "n": len(rows), "n_read": len(read),
        "overall": {
            "api_error_rate": (len(rows) - len(read)) / (len(rows) or 1),
            "field_accuracy": sum(r["field_accuracy"] * r["fields"] for r in read) / fields,
            "key_accuracy": sum(r["key_accuracy"] for r in read) / n_read,
            "reconciles_rate": sum(r["reconciles"] for r in read) / n_read,
            "mean_attempts": sum(r["attempts"] for r in rows) / (len(rows) or 1),
            "mean_seconds": sum(r["seconds"] for r in rows) / (len(rows) or 1),
        },
        "by_layout": {k: sum(r["field_accuracy"] * r["fields"] for r in v)
                      / (sum(r["fields"] for r in v) or 1) for k, v in by_layout.items()},
        "rows": rows,
    }


def render_markdown(rep: dict) -> str:
    o = rep["overall"]
    lines = [
        f"# Extraction eval - {rep['provider']} (verify loop: {'on' if rep['verify'] else 'off'})",
        "", f"{rep['n']} real bill photos vs hand-verified labels; "
        f"{rep['n_read']} read, {rep['n'] - rep['n_read']} failed at the API.", "",
        "| Metric | Value |", "|---|---|",
        f"| API errors (quota / overload - not reading errors) | {o['api_error_rate']:.1%} |",
        f"| Field accuracy (bills read) | {o['field_accuracy']:.1%} |",
        f"| Key-field accuracy (pay, due date, arrears, tariff...) | {o['key_accuracy']:.1%} |",
        f"| Extracted bill reconciles (bills read) | {o['reconciles_rate']:.1%} |",
        f"| Mean attempts | {o['mean_attempts']:.2f} |",
        f"| Mean time per bill | {o['mean_seconds']:.1f} s |", "",
        "| Layout | Field accuracy |", "|---|---|",
        *[f"| {k} | {v:.1%} |" for k, v in rep["by_layout"].items()], "",
        "| Bill | Fields | Accuracy | Key fields | Reconciles | Attempts | Wrong (first 5) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rep["rows"]:
        if not r["read"]:
            err = " ".join((r["errors"][-1] if r["errors"] else "no output").split())[:160]
            lines.append(f"| {r['bill_id']} | - | - | - | - | {r['attempts']} | "
                         f"API ERROR: {err} |")
            continue
        wrong = "; ".join(f"{k}: {e} -> {g}" for k, e, g in r["wrong"][:5]) or "-"
        lines.append(f"| {r['bill_id']} | {r['fields']} | {r['field_accuracy']:.1%} | "
                     f"{r['key_accuracy']:.0%} | {'yes' if r['reconciles'] else 'no'} | "
                     f"{r['attempts']} | {wrong} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate bill-photo extraction on real bills.")
    ap.add_argument("--images", default="data/real")
    ap.add_argument("--labels", default="data/labels/real")
    ap.add_argument("--provider", default="gemini", choices=["gemini", "groq"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--no-verify", action="store_true", help="single pass, no re-read loop")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between bills")
    ap.add_argument("--only", default=None, help="run a single bill id, e.g. iesco-2023-03")
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = OpenAICompatVision(args.provider, args.model)
    if args.list_models:
        print("\n".join(client.list_models()))
        return 0
    rep = run(Path(args.images), Path(args.labels), client, verify=not args.no_verify,
              pause=args.pause, only=args.only)
    if args.only:
        print(render_markdown(rep))     # quick check: don't overwrite the full report
        return 0
    slug = rep["provider"].replace(":", "_").replace("/", "_")
    out = Path("reports/extract_eval") / f"{slug}_{'verify' if rep['verify'] else 'single'}"
    out.mkdir(parents=True, exist_ok=True)
    # Extracted bills hold no identifiers (the schema has no field for them), so the
    # report is safe to commit.
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    md = render_markdown(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())