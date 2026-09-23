"""Billing errors planted on purpose, each labelled with the check that should catch it.

Errors are realistic in one important way: after a line goes wrong, the TOTALS are
still derived from the printed lines, so the bill "adds up". The auditor has to catch
the wrong line itself, not a broken sum.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from rehnuma.engine import calculator as calc
from rehnuma.schema import Bill, FpaPart, RateLine, shift_month
from rehnuma.synth.generator import (
    ED_RATE_PCT,
    Household,
    assemble,
    build_bill,
    components,
    paisa,
    rupees,
)
from rehnuma.tariffs import protected_eligible, schedule_for, slab_rate_lines

D = Decimal


@dataclass(frozen=True)
class ErrorType:
    name: str
    description: str
    expected_check: str | None     # check-name prefix that should FAIL; None = undetectable
    applies: Callable[[Household], bool]
    apply: Callable[[Household, random.Random, str], Bill]


def _always(_: Household) -> bool:
    return True


def _reprice(c, cost: Decimal, month: str) -> None:
    """Recompute ED and GST consistently after the cost changed (biller used a wrong
    rate, but applied taxes correctly on top of it)."""
    ed = calc.electricity_duty(cost, D(0), ED_RATE_PCT)
    c.printed["cost"] = paisa(cost)
    c.printed["electricity_duty"] = paisa(ed)
    c.printed["gst"] = D(rupees(calc.gst_on_energy(cost, D(0), D(0), ed, month)))


# --- line-level errors ---------------------------------------------------------------
def gst_inflated(hh, rng, bid):
    c = components(hh)
    c.printed["gst"] += rng.randint(50, 500)
    return assemble(hh, bid, c.units, c.rate_lines, c.parts, c.printed, c.history)


def wrong_ed_rate(hh, rng, bid):
    c = components(hh)
    c.printed["electricity_duty"] = paisa(c.printed["cost"] * D("0.02"))   # 2% instead of 1.5%
    return assemble(hh, bid, c.units, c.rate_lines, c.parts, c.printed, c.history)


def fpa_on_wrong_month(hh, rng, bid):
    """FPA charged on the wrong month's units, with FPA taxes recomputed consistently."""
    c = components(hh)
    right_units = c.parts[0].units
    candidates = [shift_month(hh.bill_month, -k) for k in (1, 3, 4, 5, 6)]
    wrong_month = next(m for m in candidates if hh.usage[m] != right_units)
    wrong_units = hh.usage[wrong_month]
    parts = [FpaPart(ref_month=c.parts[0].ref_month, units=wrong_units, rate=hh.fpa_rate)]
    fb = calc.fpa_breakdown(parts, ED_RATE_PCT)
    c.printed.update(fpa=paisa(fb.fpa), ed_on_fpa=paisa(fb.ed_on_fpa), gst_on_fpa=fb.gst_on_fpa)
    return assemble(hh, bid, c.units, c.rate_lines, parts, c.printed, c.history)


def fpa_line_inflated(hh, rng, bid):
    c = components(hh)
    c.printed["fpa"] += D(rng.randint(30, 300))
    return assemble(hh, bid, c.units, c.rate_lines, c.parts, c.printed, c.history)


def current_bill_arithmetic(hh, rng, bid):
    hh.extra = {"current_bill_delta": rng.randint(20, 300)}
    return build_bill(hh, bid)


def arrears_not_in_history(hh, rng, bid):
    hh.extra = {"arrears": rng.randint(500, 5000)}   # history says last bill was paid
    return build_bill(hh, bid)


def lp_surcharge_mismatch(hh, rng, bid):
    hh.extra = {"after_due_delta": rng.randint(10, 200)}
    return build_bill(hh, bid)


def units_not_matching_meter(hh, rng, bid):
    """Bill charges more units than the meter readings show."""
    c = components(hh)
    extra_units = rng.randint(15, 120)
    units = c.units + extra_units
    schedule = schedule_for("A-1a(01)", hh.bill_month)
    prot = bool(protected_eligible(c.history, hh.bill_month, "A-1a(01)"))
    lines = slab_rate_lines(units, schedule, prot)
    _reprice(c, calc.cost_of_electricity(lines), hh.bill_month)
    hh.extra = {"reading_units": c.units}
    return assemble(hh, bid, units, lines, c.parts, c.printed, c.history, extra=hh.extra)


# --- tariff-level errors (cost is consistent with the printed rate lines) --------------
def protected_billed_as_unprotected(hh, rng, bid):
    hh.charge_as_protected = False
    return build_bill(hh, bid)


def next_slab_rate(hh, rng, bid):
    """Unprotected household charged the next slab's rate on every unit."""
    c = components(hh)
    schedule = schedule_for("A-1a(01)", hh.bill_month)
    rates = [b.rate for b in schedule.unprotected]
    current_rate = c.rate_lines[-1].rate
    idx = rates.index(current_rate)
    higher = rates[min(idx + 1, len(rates) - 1)]
    if higher == current_rate:
        higher = current_rate + D("2.00")
    lines = [RateLine(rate=higher, units=c.units)]
    _reprice(c, calc.cost_of_electricity(lines), hh.bill_month)
    return assemble(hh, bid, c.units, lines, c.parts, c.printed, c.history)


# --- consistent with everything on the page: a single bill cannot reveal it -------------
def inflated_meter_reading(hh, rng, bid):
    """Meter reader records a higher present reading; the whole bill follows it.
    Only the meter photo (milestone 3) or the next month's reading can expose this."""
    hh.usage[hh.bill_month] += rng.randint(40, 150)
    return build_bill(hh, bid)


def _fpa_month_distinguishable(hh: Household) -> bool:
    """Only plant 'FPA on wrong month' if some other month has different units -
    otherwise the 'error' changes nothing (found by the eval: 98 vs 98 units)."""
    right = hh.usage[shift_month(hh.bill_month, -2)]
    return any(hh.usage[shift_month(hh.bill_month, -k)] != right for k in (1, 3, 4, 5, 6))


def _is_protected(hh: Household) -> bool:
    return hh.protected_profile


def _is_unprotected(hh: Household) -> bool:
    return not hh.protected_profile


ERROR_TYPES: list[ErrorType] = [
    ErrorType("gst_inflated", "GST line higher than GST law gives", "gst_on_energy",
              _always, gst_inflated),
    ErrorType("wrong_ed_rate", "Electricity duty at 2% instead of 1.5%", "electricity_duty",
              _always, wrong_ed_rate),
    ErrorType("fpa_on_wrong_month", "FPA applied to the wrong month's units",
              "fpa_units_vs_history", _fpa_month_distinguishable, fpa_on_wrong_month),
    ErrorType("fpa_line_inflated", "FPA line not equal to units x rate", "fpa_line",
              _always, fpa_line_inflated),
    ErrorType("current_bill_arithmetic", "Current bill doesn't equal its lines",
              "legacy_current_bill", _always, current_bill_arithmetic),
    ErrorType("arrears_not_in_history", "Arrears charged although history shows paid",
              "arrears_vs_history", _always, arrears_not_in_history),
    ErrorType("lp_surcharge_mismatch", "After-due amount != within-due + LP",
              "payable_after_due", _always, lp_surcharge_mismatch),
    ErrorType("units_not_matching_meter", "Billed units exceed meter readings",
              "register_units", _always, units_not_matching_meter),
    ErrorType("protected_billed_as_unprotected", "Protected household charged unprotected rates",
              "tariff_rates", _is_protected, protected_billed_as_unprotected),
    ErrorType("next_slab_rate", "Charged the next slab's rate", "tariff_rates",
              _is_unprotected, next_slab_rate),
    ErrorType("inflated_meter_reading", "Higher meter reading, bill fully consistent",
              None, _always, inflated_meter_reading),
]
