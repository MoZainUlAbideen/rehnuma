"""Auditor eval: plant known errors in synthetic bills and measure what the auditor catches.

  uv run rehnuma-eval-auditor --n 1000 --seed 42

Metrics (per error type and overall):
  * detection rate     - bill has at least one FAIL
  * localisation rate  - the EXPECTED check is among the FAILs (the auditor caught it
                         for the right reason, not by accident)
  * false-positive rate on clean bills - any FAIL on a correct bill is a false alarm

Undetectable-by-design errors are reported separately and never mixed into recall.
These are SYNTHETIC-data numbers: they test the auditor's logic, not real-world accuracy.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from rehnuma.engine import Status, audit_bill
from rehnuma.synth.errors import ERROR_TYPES
from rehnuma.synth.generator import build_bill, sample_household


@dataclass
class TypeResult:
    name: str
    expected_check: str | None
    n: int = 0
    detected: int = 0
    localised: int = 0
    missed_examples: list[str] | None = None

    @property
    def detection_rate(self) -> float:
        return self.detected / self.n if self.n else 0.0

    @property
    def localisation_rate(self) -> float:
        return self.localised / self.n if self.n else 0.0


def run(n: int, seed: int, clean_share: float = 0.3) -> dict:
    rng = random.Random(seed)
    results = {e.name: TypeResult(e.name, e.expected_check, missed_examples=[])
               for e in ERROR_TYPES}
    clean = TypeResult("clean", None, missed_examples=[])
    fp_checks: dict[str, int] = defaultdict(int)

    for i in range(n):
        hh = sample_household(rng, seed=i)
        bid = f"synth-{seed}-{i}"
        if rng.random() < clean_share:
            fails = [f for f in audit_bill(build_bill(hh, bid)) if f.status == Status.FAIL]
            clean.n += 1
            if fails:
                clean.detected += 1
                for f in fails:
                    fp_checks[f.check] += 1
                if len(clean.missed_examples) < 5:
                    clean.missed_examples.append(f"{bid}: {fails[0].check}: {fails[0].message}")
            continue
        options = [e for e in ERROR_TYPES if e.applies(hh)]
        err = rng.choice(options)
        clean_bill = build_bill(copy.deepcopy(hh), bid)
        bill = err.apply(hh, rng, bid)
        if bill.model_dump() == clean_bill.model_dump():
            raise RuntimeError(f"{err.name} planted no change on {bid} - generator bug")
        fails = [f for f in audit_bill(bill) if f.status == Status.FAIL]
        r = results[err.name]
        r.n += 1
        r.detected += bool(fails)
        hit = err.expected_check is not None and any(
            f.check.startswith(err.expected_check) for f in fails)
        r.localised += hit
        if err.expected_check and not hit and len(r.missed_examples) < 5:
            got = ", ".join(sorted({f.check for f in fails})) or "no FAIL"
            r.missed_examples.append(f"{bid}: got {got}")

    detectable = [r for r in results.values() if r.expected_check]
    n_det = sum(r.n for r in detectable)
    return {
        "seed": seed, "n_bills": n,
        "overall": {
            "detection_rate": sum(r.detected for r in detectable) / n_det if n_det else 0.0,
            "localisation_rate": sum(r.localised for r in detectable) / n_det if n_det else 0.0,
            "false_positive_rate": clean.detection_rate,
            "n_error_bills": n_det, "n_clean_bills": clean.n,
            "n_undetectable_bills": sum(r.n for r in results.values() if not r.expected_check),
        },
        "per_type": {name: {**asdict(r), "detection_rate": r.detection_rate,
                            "localisation_rate": r.localisation_rate}
                     for name, r in results.items()},
        "false_positive_checks": dict(fp_checks),
        "clean_examples": clean.missed_examples,
    }


def render_markdown(report: dict) -> str:
    o = report["overall"]
    lines = [
        "# Auditor eval (synthetic bills)",
        "",
        f"Seed {report['seed']}, {report['n_bills']} bills: {o['n_error_bills']} with a "
        f"detectable planted error, {o['n_undetectable_bills']} with an error no single bill "
        f"can reveal, {o['n_clean_bills']} clean.",
        "Synthetic data tests the auditor's logic - it is not a real-world accuracy claim.",
        "",
        "| Metric | Value |", "|---|---|",
        f"| Detection rate (detectable errors) | {o['detection_rate']:.1%} |",
        f"| Localisation rate (right check fired) | {o['localisation_rate']:.1%} |",
        f"| False-positive rate (clean bills) | {o['false_positive_rate']:.1%} |",
        "",
        "| Error type | Expected check | n | Detected | Localised |", "|---|---|---|---|---|",
    ]
    for name, r in report["per_type"].items():
        exp = r["expected_check"] or "_(undetectable on one bill)_"
        lines.append(f"| {name} | {exp} | {r['n']} | {r['detection_rate']:.1%} | "
                     f"{r['localisation_rate']:.1%} |")
    misses = {k: v["missed_examples"] for k, v in report["per_type"].items()
              if v["missed_examples"]}
    if misses or report["clean_examples"]:
        lines += ["", "## Misses and false alarms (first 5 each)", ""]
        for k, ex in misses.items():
            lines += [f"- **{k}**: " + "; ".join(ex)]
        if report["clean_examples"]:
            lines += ["- **false alarms**: " + "; ".join(report["clean_examples"])]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the auditor on synthetic bills.")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="reports/auditor_eval")
    args = ap.parse_args(argv)

    report = run(args.n, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = render_markdown(report)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
