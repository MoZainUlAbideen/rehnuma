"""`uv run rehnuma-audit data/labels/real` — audit bills and print a report.

Output is plain ASCII on purpose (Windows consoles + file redirects).
"""

from __future__ import annotations

import argparse
import sys

from rehnuma.engine import Status, audit_bill, audit_series, summarize
from rehnuma.engine.findings import Finding
from rehnuma.loader import load_bills

MARK = {Status.PASS: "[PASS]", Status.FAIL: "[FAIL]", Status.SKIP: "[skip]"}


def _print(findings: list[Finding], show_pass: bool) -> None:
    for f in findings:
        if f.status == Status.PASS and not show_pass and (f.delta in (None, 0)):
            continue  # hide clean passes unless --all; always show near-misses
        who = f"  ({f.bill_id})" if f.bill_id and "->" in f.bill_id else ""
        print(f"  {MARK[f.status]} {f.check}: {f.message}{who}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit electricity bill labels.")
    parser.add_argument("paths", nargs="+", help="JSON files, folders or glob patterns")
    parser.add_argument("--all", action="store_true", help="also list exact passes")
    args = parser.parse_args(argv)

    bills = load_bills(args.paths)
    if not bills:
        print("No bills found.")
        return 2

    everything: list[Finding] = []
    for bill in sorted(bills, key=lambda b: b.bill_month):
        findings = audit_bill(bill)
        everything += findings
        s = summarize(findings)
        print(f"\n== {bill.bill_id}  [{bill.disco} | {bill.layout.value} | "
              f"{bill.connection_type.value} | {bill.bill_month}]  "
              f"PASS {s['PASS']}  FAIL {s['FAIL']}  skip {s['SKIP']}")
        _print(findings, args.all)

    if len(bills) > 1:
        cross = audit_series(bills)
        everything += cross
        s = summarize(cross)
        print(f"\n== cross-bill checks ({len(bills)} bills)  "
              f"PASS {s['PASS']}  FAIL {s['FAIL']}  skip {s['SKIP']}")
        _print(cross, args.all)

    s = summarize(everything)
    checked = s["PASS"] + s["FAIL"]
    rate = 100 * s["PASS"] / checked if checked else 0.0
    print(f"\nTOTAL: {s['PASS']}/{checked} checks pass ({rate:.1f}%), {s['SKIP']} skipped")
    return 1 if s["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
