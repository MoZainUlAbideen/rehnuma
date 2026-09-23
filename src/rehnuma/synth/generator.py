"""Synthetic PITC-legacy bills for conventional (non-solar) households.

Every bill is built by the SAME calculator the auditor uses, so a clean synthetic
bill is correct by construction. Errors are then planted on purpose (see errors.py)
with a label saying which check should catch them.

What synthetic bills are for: stress-testing the auditor and, later, the vision
extractor. What they are NOT for: headline metrics. Those come from real bills only.

Simplifications (stated, not hidden):
  * 2026 tariff from the 'secondary'-confidence schedule; 18% GST; ED 1.5%.
  * No FC surcharge, QTA, TV fee or fixed charges: their 2026 treatment (and whether
    GST applies to fixed charges) isn't sourced yet. PESCO Mar-26 shows none of them.
  * One FPA month (bill month - 2), rate drawn from a plausible range.
  * LP surcharge = 10% x cost of electricity (the real base is an open question).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from rehnuma.engine import calculator as calc
from rehnuma.schema import (
    Bill,
    FpaPart,
    HistoryEntry,
    LegacyCharges,
    RateLine,
    Register,
    Totals,
    shift_month,
)
from rehnuma.tariffs import protected_eligible, schedule_for, slab_rate_lines

D = Decimal
ED_RATE_PCT = D("1.5")
BILL_MONTHS = ["2026-03", "2026-04", "2026-05", "2026-06"]
SEASON = {1: 0.75, 2: 0.7, 3: 0.8, 4: 1.0, 5: 1.35, 6: 1.6, 7: 1.7, 8: 1.65,
          9: 1.4, 10: 1.05, 11: 0.8, 12: 0.8}


def paisa(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), ROUND_HALF_UP)


def rupees(x: Decimal) -> int:
    return int(x.quantize(D(1), ROUND_HALF_UP))


@dataclass
class Household:
    """The 'truth' a bill is generated from. Errors may alter these before building."""
    seed: int
    bill_month: str
    protected_profile: bool
    usage: dict[str, int]                 # month -> units, 12 history months + bill month
    previous_reading: Decimal
    fpa_rate: Decimal
    load_kw: int
    charge_as_protected: bool | None = None   # None = charge correctly
    rate_override: list[RateLine] | None = None
    extra: dict = field(default_factory=dict)


def sample_household(rng: random.Random, seed: int) -> Household:
    bill_month = rng.choice(BILL_MONTHS)
    protected_profile = rng.random() < 0.35
    months = [shift_month(bill_month, -k) for k in range(12, -1, -1)]
    usage: dict[str, int] = {}
    if protected_profile:
        base = rng.uniform(60, 150)
        for m in months:
            usage[m] = max(20, min(200, round(base * SEASON[int(m[5:])] * rng.uniform(0.85, 1.1))))
    else:
        base = rng.uniform(140, 420)
        for m in months:
            usage[m] = max(30, round(base * SEASON[int(m[5:])] * rng.uniform(0.85, 1.15)))
        # make sure an unprotected profile really is unprotected in the lookback window
        lookback = [shift_month(bill_month, -k) for k in range(1, 7)]
        if all(usage[m] <= 200 for m in lookback):
            usage[rng.choice(lookback)] = rng.randint(201, 320)
    return Household(
        seed=seed, bill_month=bill_month, protected_profile=protected_profile, usage=usage,
        previous_reading=D(rng.randint(1000, 60000)),
        fpa_rate=D(str(round(rng.uniform(-2.0, 1.2), 4))),
        load_kw=rng.choice([1, 2, 3, 4]),
    )


def _history(hh: Household) -> list[HistoryEntry]:
    rows = []
    for k in range(12, 0, -1):
        m = shift_month(hh.bill_month, -k)
        approx_bill = rupees(D(hh.usage[m]) * D("30"))  # plausible magnitude only
        rows.append(HistoryEntry(month=m, units=D(hh.usage[m]), bill=approx_bill,
                                 payment=approx_bill))
    return rows


@dataclass
class Components:
    units: int
    rate_lines: list[RateLine]
    parts: list[FpaPart]
    printed: dict
    history: list[HistoryEntry]


def components(hh: Household) -> Components:
    """Everything a correct bill for this household would print."""
    units = hh.usage[hh.bill_month]
    history = _history(hh)
    schedule = schedule_for("A-1a(01)", hh.bill_month)
    eligible = protected_eligible(history, hh.bill_month, "A-1a(01)")
    as_protected = eligible if hh.charge_as_protected is None else hh.charge_as_protected
    rate_lines = hh.rate_override or slab_rate_lines(units, schedule, bool(as_protected))

    cost = calc.cost_of_electricity(rate_lines)
    ed = calc.electricity_duty(cost, D(0), ED_RATE_PCT)
    gst = calc.gst_on_energy(cost, D(0), D(0), ed, hh.bill_month)

    fpa_month = shift_month(hh.bill_month, -2)
    parts = [FpaPart(ref_month=fpa_month, units=hh.usage[fpa_month], rate=hh.fpa_rate)]
    fb = calc.fpa_breakdown(parts, ED_RATE_PCT)

    printed = {
        "cost": paisa(cost), "fpa": paisa(fb.fpa),
        "electricity_duty": paisa(ed), "gst": D(rupees(gst)),
        "ed_on_fpa": paisa(fb.ed_on_fpa), "gst_on_fpa": fb.gst_on_fpa,
    }
    return Components(units, rate_lines, parts, printed, history)


def build_bill(hh: Household, bill_id: str) -> Bill:
    """A fully consistent, correct bill for this household."""
    c = components(hh)
    return assemble(hh, bill_id, c.units, c.rate_lines, c.parts, c.printed, c.history,
                    extra=hh.extra)


def assemble(hh: Household, bill_id: str, units: int, rate_lines: list[RateLine],
             parts: list[FpaPart], printed: dict, history: list[HistoryEntry],
             extra: dict | None = None) -> Bill:
    """Turn printed lines into a Bill, deriving totals FROM the printed lines - the way
    a biller who got a line wrong would still produce totals that add up."""
    extra = extra or {}
    govt = {"electricity_duty": printed["electricity_duty"], "gst": printed["gst"],
            "gst_on_fpa": printed["gst_on_fpa"], "ed_on_fpa": printed["ed_on_fpa"]}
    total_fpa = printed["fpa"] + printed["ed_on_fpa"] + printed["gst_on_fpa"]
    current = rupees(printed["cost"] + printed["electricity_duty"] + printed["gst"])
    current += extra.get("current_bill_delta", 0)
    arrears = extra.get("arrears", 0)
    payable = rupees(D(arrears + current) + total_fpa)
    lp = rupees(printed["cost"] * D("0.10"))
    after = payable + lp + extra.get("after_due_delta", 0)
    reading_units = extra.get("reading_units", units)

    return Bill(
        bill_id=bill_id, connection_id=f"synthetic-{hh.seed}", source="synthetic",
        disco="SYNTH", layout="pitc_legacy", connection_type="conventional",
        tariff="A-1a(01)", sanctioned_load_kw=D(hh.load_kw), bill_month=hh.bill_month,
        ed_rate_pct=ED_RATE_PCT,
        registers=[Register(name="import", previous=hh.previous_reading,
                            present=hh.previous_reading + reading_units, units=units)],
        legacy_charges=LegacyCharges(
            units_consumed=units, cost_of_electricity=printed["cost"], fpa=printed["fpa"],
            disco_total=printed["cost"] + printed["fpa"], govt=govt,
            govt_total=sum(govt.values(), D(0)), total_fpa=total_fpa,
            fpa_parts=parts, rate_lines=rate_lines),
        totals=Totals(arrears=arrears, current_bill=current, payable_within_due=payable,
                      lp_surcharge=lp, payable_after_due=after),
        history=history,
        notes=["SYNTHETIC - generated by rehnuma.synth; not a real bill."],
    )
