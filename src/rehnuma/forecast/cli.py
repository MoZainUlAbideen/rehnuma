"""`uv run rehnuma-forecast data/labels/real/iesco-2021-01.json` - the next 12 months.

Solar (net-metering) bills get their last 12 months and, when the other bills of the same
billing cycle are passed too (e.g. the whole folder), the renewal comparison.

  --lang en      English instead of Urdu
  --table        also print the month-by-month table
"""

from __future__ import annotations

import argparse
import sys

from rehnuma.explain.render import LANGS
from rehnuma.forecast.outlook import NotSupported, outlook
from rehnuma.forecast.render import summarize_outlook, table
from rehnuma.forecast.solar import solar_outlook
from rehnuma.forecast.solar_render import summarize_solar
from rehnuma.loader import load_bills
from rehnuma.schema import ConnectionType


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="12-month bill outlook with the 200-unit watch.")
    ap.add_argument("paths", nargs="+", help="bill JSON files or folders")
    ap.add_argument("--lang", choices=LANGS, default="ur")
    ap.add_argument("--table", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bills = sorted(load_bills(args.paths), key=lambda b: b.bill_month)
    for bill in bills:
        if bill.connection_type == ConnectionType.NET_METERING:
            lines = summarize_solar(solar_outlook(bill, bills), args.lang)
            print(f"## {lines[0]}  ({bill.bill_id})\n")
            print("\n".join(f"- {ln}" for ln in lines[1:]) + "\n")
            continue
        try:
            o = outlook(bill)
        except NotSupported as e:
            print(f"## {bill.bill_id}: no outlook - {e}\n")
            continue
        lines = summarize_outlook(o, args.lang)
        print(f"## {lines[0]}  ({bill.bill_id})\n")
        print("\n".join(f"- {ln}" for ln in lines[1:]))
        if args.table:
            print("\n" + table(o, args.lang))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
