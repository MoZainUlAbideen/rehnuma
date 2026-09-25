"""rehnuma-eval-forecast: how far to trust the 12-month outlook.

  uv run rehnuma-eval-forecast

Three parts, each reported with its sample size:

1. Backtest (the real accuracy number). For every pair of bills from the SAME connection
   where the later bill's history covers months the earlier bill forecast, compare the
   forecast with what was actually used: mean absolute error in units, MAPE, and how
   well the forecast called the months that went over 200 units. Today there are no
   such pairs - our three IESCO bills are three different households - so this part
   reports n = 0 instead of a number. It fills in as consecutive-year bills are added.

2. Seasonality across households: correlation of each household's monthly profile (units
   / its yearly mean). This is the evidence for forecasting from the household's OWN
   months rather than a shared national profile.

3. Cost-engine consistency: the forecast prices months with the same slab engine the
   auditor uses. Applied to each real bill's actual units with that bill's own schedule,
   it must reproduce the printed cost of electricity (Rs 1 display rounding allowed).
"""

from __future__ import annotations

import json
import statistics as st
import sys
from decimal import Decimal
from itertools import combinations
from pathlib import Path

from rehnuma.forecast.units import forecast_units, monthly_units
from rehnuma.loader import load_bills
from rehnuma.schema import Bill, ConnectionType
from rehnuma.tariffs import (
    PROTECTED_LIMIT_KWH,
    UnknownRate,
    protected_eligible,
    schedule_for,
    slab_rate_lines,
)

LABELS = "data/labels/real"


def conventional(bills: list[Bill]) -> list[Bill]:
    return [b for b in bills if b.connection_type == ConnectionType.CONVENTIONAL
            and b.tariff.startswith("A-1a")]


def backtest(bills: list[Bill]) -> dict:
    """Forecast from each bill; score against later bills of the same connection."""
    rows = []
    for early, late in combinations(sorted(bills, key=lambda b: b.bill_month), 2):
        if not early.connection_id or early.connection_id != late.connection_id:
            continue
        actual = monthly_units(late)
        try:
            fc = forecast_units(monthly_units(early), early.bill_month)
        except ValueError:
            continue
        for f in fc:
            if f.month in actual:
                rows.append({"connection": early.connection_id, "from": early.bill_month,
                             "month": f.month, "forecast": f.units, "low": f.low,
                             "high": f.high, "actual": actual[f.month]})
    seen, unique = set(), []
    for r in rows:                     # a month covered by two later bills counts once
        key = (r["connection"], r["from"], r["month"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    out: dict = {"n": len(unique), "rows": unique}
    if unique:
        errs = [abs(r["forecast"] - r["actual"]) for r in unique]
        pct = [e / r["actual"] for e, r in zip(errs, unique, strict=True) if r["actual"] > 0]
        over_a = {i for i, r in enumerate(unique) if r["actual"] > PROTECTED_LIMIT_KWH}
        over_f = {i for i, r in enumerate(unique) if r["forecast"] > PROTECTED_LIMIT_KWH}
        out.update({
            "mae_units": st.mean(errs), "mape": st.mean(pct) if pct else None,
            "in_range": sum(r["low"] <= r["actual"] <= r["high"] for r in unique) / len(unique),
            "over_200_recall": len(over_a & over_f) / len(over_a) if over_a else None,
            "over_200_precision": len(over_a & over_f) / len(over_f) if over_f else None,
        })
    return out


def profiles(bills: list[Bill]) -> dict:
    prof = {}
    for b in bills:
        by_cal: dict[int, list[int]] = {}
        for month, units in monthly_units(b).items():
            by_cal.setdefault(int(month[5:]), []).append(units)
        if len(by_cal) < 12:
            continue
        means = [st.mean(by_cal[c]) for c in range(1, 13)]
        avg = st.mean(means)
        prof[b.connection_id or b.bill_id] = [m / avg for m in means]
    pairs = {f"{a} vs {b}": st.correlation(prof[a], prof[b])
             for a, b in combinations(sorted(prof), 2)}
    peaks = {k: max(range(12), key=lambda i: v[i]) + 1 for k, v in prof.items()}
    return {"profiles": prof, "correlation": pairs, "peak_month": peaks}


def engine_consistency(bills: list[Bill]) -> list[dict]:
    rows = []
    for b in bills:
        sched = schedule_for(b.tariff, b.bill_month)
        units = monthly_units(b).get(b.bill_month)
        if sched is None or units is None or b.legacy_charges is None:
            continue
        prot = protected_eligible(b.history, b.bill_month, b.tariff) if sched.has_protected \
            else False
        try:
            lines = slab_rate_lines(units, sched, bool(prot))
        except UnknownRate as e:
            rows.append({"bill": b.bill_id, "error": str(e)})
            continue
        cost = sum((ln.rate * ln.units for ln in lines), Decimal(0))
        printed = b.legacy_charges.cost_of_electricity
        rows.append({"bill": b.bill_id, "units": units, "computed": str(cost),
                     "printed": str(printed), "ok": abs(cost - printed) <= 1})
    return rows


def run(paths: list[str] | None = None) -> dict:
    bills = conventional(load_bills(paths or [LABELS]))
    return {"n_bills": len(bills), "backtest": backtest(bills), "seasonality": profiles(bills),
            "engine": engine_consistency(bills)}


def render(rep: dict) -> str:
    bt, se = rep["backtest"], rep["seasonality"]
    lines = ["# Forecast eval", "", f"{rep['n_bills']} conventional A-1a bills.", "",
             "## 1. Backtest (same household, forecast vs actual)", ""]
    if bt["n"] == 0:
        lines += ["**n = 0 - not measured.** No two bills come from the same connection a year "
                  "apart, so there is nothing to score the forecast against yet. Needed: "
                  "bills from the same household 6-12 months apart (each pair adds up to 12 "
                  "scored months).", ""]
    else:
        mape = f"{bt['mape']:.0%}" if bt["mape"] is not None else "-"
        lines += ["| Metric | Value |", "|---|---|", f"| Months scored | {bt['n']} |",
                  f"| Mean absolute error | {bt['mae_units']:.0f} units |", f"| MAPE | {mape} |",
                  f"| Actual inside the forecast range | {bt['in_range']:.0%} |",
                  f"| Months over 200 caught (recall) | {bt['over_200_recall']} |",
                  f"| Over-200 warnings that were right (precision) | "
                  f"{bt['over_200_precision']} |", ""]
    lines += ["## 2. Seasonality across households", "",
              "| Pair | Correlation of monthly profiles |", "|---|---|"]
    lines += [f"| {k} | {v:+.2f} |" for k, v in se["correlation"].items()]
    lines += ["", "Peak month per household: " + ", ".join(
        f"{k}: {v}" for k, v in se["peak_month"].items()), "",
              "## 3. Cost engine reproduces printed energy charges", "",
              "| Bill | Units | Computed | Printed | OK |", "|---|---|---|---|---|"]
    for r in rep["engine"]:
        if "error" in r:
            lines.append(f"| {r['bill']} | - | - | - | {r['error']} |")
        else:
            lines.append(f"| {r['bill']} | {r['units']} | {r['computed']} | {r['printed']} | "
                         f"{'yes' if r['ok'] else '**no**'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rep = run()
    out = Path("reports/forecast_eval")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    md = render(rep)
    (out / "report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
