"""Extraction eval on REAL bill photos against hand-verified labels.

  uv run rehnuma-eval-extract                          # Gemini, verify loop on (resumes)
  uv run rehnuma-eval-extract --fresh                  # ignore saved results, start over
  uv run rehnuma-eval-extract --no-verify              # single pass only
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

Free-tier quota (a full run does not fit in one day):
  * a DAILY quota error stops the run at once - the remaining bills are "not run", not
    failed, and retrying for minutes cannot bring the quota back;
  * each bill's result is saved as it finishes (reports/extract_eval/<model>_verify/rows/),
    so the next day's run skips it and continues. Saved rows are keyed by a hash of the
    prompt: changing the prompt starts a fresh set instead of mixing two prompts;
  * the "no re-read loop" column comes from the SAME run: the first schema-valid read gets
    no re-read feedback, so it is what a --no-verify run returns (up to the model's own
    run-to-run noise at temperature 0). One run instead of two.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from rehnuma.engine import Status, audit_bill
from rehnuma.extract.compare import compare
from rehnuma.extract.pipeline import ExtractionResult, extract_bill
from rehnuma.extract.prompt import SYSTEM, build_prompt
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


def prompt_version() -> str:
    """Saved results are only reused while the prompt is unchanged."""
    return hashlib.sha256((SYSTEM + build_prompt()).encode("utf-8")).hexdigest()[:10]


def score(label, bill) -> dict:
    """How one extracted bill compares with its hand-verified label."""
    cmp = compare(label, bill)
    fails = {f.check for f in audit_bill(bill) if f.status == Status.FAIL} if bill else set()
    return {"field_accuracy": cmp.accuracy, "key_accuracy": cmp.key_accuracy(),
            "fields": cmp.total, "wrong": [[k, str(e), str(g)] for k, e, g in cmp.wrong],
            "missing": cmp.missing, "extra": cmp.extra,
            "reconciles": bill is not None and fails == expected_fails(label.bill_id),
            "failed_checks": sorted(fails)}


def make_row(label, res: ExtractionResult) -> dict:
    first = res.first_pass
    return {
        "bill_id": label.bill_id, "layout": label.layout.value, "read": res.bill is not None,
        **score(label, res.bill),
        "first_pass": score(label, first.bill) if first and first.bill else None,
        "attempts": len(res.attempts), "errors": [a.error for a in res.attempts if a.error],
        "seconds": round(res.seconds, 1),
        "extracted": res.bill.model_dump(mode="json") if res.bill else None,
    }


def run(images: Path, labels: Path, client, verify: bool, pause: float = 0.0,
        only: str | None = None, cache: Path | None = None) -> dict:
    rows, not_run, stopped = [], [], None
    todo = pairs(images, labels, only)
    called = False
    for i, (img, lab) in enumerate(todo):
        label = load_bill(lab)
        tag = f"[{i + 1}/{len(todo)}] {img.name}"
        saved = cache / f"{label.bill_id}.json" if cache else None
        if saved and saved.exists():
            rows.append(json.loads(saved.read_text(encoding="utf-8")))
            print(f"{tag}: saved result from an earlier run", flush=True)
            continue
        if stopped:
            not_run.append(label.bill_id)
            continue
        if called and pause:
            time.sleep(pause)                    # stay under per-minute quotas
        called = True
        print(f"{tag}: reading ...", end=" ", flush=True)
        res = extract_bill(img, client, label.bill_id, verify=verify)
        if res.quota_exhausted:
            stopped = res.attempts[-1].error
            not_run.append(label.bill_id)
            print("QUOTA USED UP - stopping; run the same command again later to continue",
                  flush=True)
            continue
        last = res.attempts[-1] if res.attempts else None
        status = ("verified" if res.verified
                  else f"ERROR: {last.error[:150]}" if last and last.error and res.bill is None
                  else "NOT verified (read, but checks failed)")
        print(f"{len(res.attempts)} attempt(s), {res.seconds:.0f} s, {status}", flush=True)
        row = make_row(label, res)
        rows.append(row)
        if saved and row["read"]:                # API errors are retried next time
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    return summarize(rows, client.name, verify, not_run, stopped)


def _rates(rows: list[dict]) -> dict:
    fields = sum(r["fields"] for r in rows) or 1
    n = len(rows) or 1
    return {"field_accuracy": sum(r["field_accuracy"] * r["fields"] for r in rows) / fields,
            "key_accuracy": sum(r["key_accuracy"] for r in rows) / n,
            "reconciles_rate": sum(r["reconciles"] for r in rows) / n}


def summarize(rows: list[dict], provider: str, verify: bool, not_run: list[str] | None = None,
              stopped: str | None = None) -> dict:
    read = [r for r in rows if r["read"]]
    first = [r["first_pass"] for r in read if r.get("first_pass")]
    by_layout: dict[str, list] = {}
    for r in read:
        by_layout.setdefault(r["layout"], []).append(r)
    return {
        "provider": provider, "verify": verify, "prompt_version": prompt_version(),
        "n": len(rows), "n_read": len(read), "not_run": not_run or [], "stopped": stopped,
        "overall": {
            "api_error_rate": (len(rows) - len(read)) / (len(rows) or 1),
            **_rates(read),
            "mean_attempts": sum(r["attempts"] for r in rows) / (len(rows) or 1),
            "mean_seconds": sum(r["seconds"] for r in rows) / (len(rows) or 1),
        },
        "first_pass": _rates(first) if first else None,
        "by_layout": {k: sum(r["field_accuracy"] * r["fields"] for r in v)
                      / (sum(r["fields"] for r in v) or 1) for k, v in by_layout.items()},
        "rows": rows,
    }


def render_markdown(rep: dict) -> str:
    o, f = rep["overall"], rep.get("first_pass")
    total = rep["n"] + len(rep["not_run"])
    lines = [
        f"# Extraction eval - {rep['provider']} (verify loop: {'on' if rep['verify'] else 'off'})",
        "", f"{total} real bill photos vs hand-verified labels: {rep['n_read']} read, "
        f"{rep['n'] - rep['n_read']} failed at the API, {len(rep['not_run'])} not run yet "
        f"(quota). Prompt version `{rep['prompt_version']}`.", "",
    ]
    if rep["not_run"]:
        lines += [f"**Incomplete:** {', '.join(rep['not_run'])} not run - the quota ran out. "
                  "Run the same command again later; finished bills are kept.", ""]
    if rep["verify"] and f:
        lines += [
            "| Metric (bills read) | First read (no loop) | With re-read loop |", "|---|---|---|",
            f"| Field accuracy | {f['field_accuracy']:.1%} | {o['field_accuracy']:.1%} |",
            f"| Key-field accuracy (pay, due date, arrears, tariff...) | "
            f"{f['key_accuracy']:.1%} | {o['key_accuracy']:.1%} |",
            f"| Extracted bill reconciles | {f['reconciles_rate']:.1%} | "
            f"{o['reconciles_rate']:.1%} |", "",
            "The first read gets no re-read feedback, so it is what a single-pass run returns.",
            "",
        ]
    lines += [
        "| Metric | Value |", "|---|---|",
        f"| API errors (quota / overload - not reading errors) | {o['api_error_rate']:.1%} |",
        f"| Field accuracy (bills read) | {o['field_accuracy']:.1%} |",
        f"| Key-field accuracy (pay, due date, arrears, tariff...) | {o['key_accuracy']:.1%} |",
        f"| Extracted bill reconciles (bills read) | {o['reconciles_rate']:.1%} |",
        f"| Mean attempts | {o['mean_attempts']:.2f} |",
        f"| Mean time per bill | {o['mean_seconds']:.1f} s |", "",
        "| Layout | Field accuracy |", "|---|---|",
        *[f"| {k} | {v:.1%} |" for k, v in rep["by_layout"].items()], "",
        "| Bill | Fields | First read | Final | Key fields | Reconciles (first -> final) "
        "| Attempts | Wrong (first 5) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rep["rows"]:
        if not r["read"]:
            err = " ".join((r["errors"][-1] if r["errors"] else "no output").split())[:160]
            lines.append(f"| {r['bill_id']} | - | - | - | - | - | {r['attempts']} | "
                         f"API ERROR: {err} |")
            continue
        fp = r.get("first_pass")
        first_acc = f"{fp['field_accuracy']:.1%}" if fp else "-"
        first_rec = ("yes" if fp["reconciles"] else "no") if fp else "-"
        wrong = "; ".join(f"{k}: {e} -> {g}" for k, e, g in r["wrong"][:5]) or "-"
        lines.append(f"| {r['bill_id']} | {r['fields']} | {first_acc} | "
                     f"{r['field_accuracy']:.1%} | {r['key_accuracy']:.0%} | "
                     f"{first_rec} -> {'yes' if r['reconciles'] else 'no'} | "
                     f"{r['attempts']} | {wrong} |")
    for b in rep["not_run"]:
        lines.append(f"| {b} | - | - | - | - | - | - | not run yet (quota) |")
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
    ap.add_argument("--fresh", action="store_true", help="ignore saved results and start over")
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    client = OpenAICompatVision(args.provider, args.model)
    if args.list_models:
        print("\n".join(client.list_models()))
        return 0
    verify = not args.no_verify
    slug = client.name.replace(":", "_").replace("/", "_")
    out = Path("reports/extract_eval") / f"{slug}_{'verify' if verify else 'single'}"
    cache = None if args.only else out / "rows" / prompt_version()
    if cache and args.fresh and cache.exists():
        for f in cache.glob("*.json"):
            f.unlink()
    rep = run(Path(args.images), Path(args.labels), client, verify=verify,
              pause=args.pause, only=args.only, cache=cache)
    if args.only:
        print(render_markdown(rep))     # quick check: don't overwrite the full report
        return 0
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
