"""Checks that need more than one bill from the same connection.

A single bill can be internally consistent and still be wrong — e.g. the meter's
'previous reading' doesn't match last month's 'present reading'. These checks
catch that class of error.
"""

from __future__ import annotations

from itertools import combinations

from rehnuma.engine.findings import Finding, compare, skip
from rehnuma.engine.rates import AMOUNT_TOLERANCE_RS
from rehnuma.schema import Bill, Layout, shift_month

TOL = AMOUNT_TOLERANCE_RS


def _pair_id(a: Bill, b: Bill) -> str:
    return f"{a.bill_id}->{b.bill_id}"


def check_history_agreement(a: Bill, b: Bill) -> list[Finding]:
    """Months that appear in both bills' history tables must agree."""
    months_a = {h.month: h for h in a.history}
    shared = [h for h in b.history if h.month in months_a]
    if not shared:
        return [skip("history_agreement", _pair_id(a, b), "no overlapping history months")]
    out = []
    for hb in shared:
        ha = months_a[hb.month]
        for field in ("units", "bill", "payment"):
            out.append(compare(f"history_agreement[{hb.month}.{field}]", _pair_id(a, b),
                               getattr(ha, field), getattr(hb, field)))
    return out


def check_bill_in_later_history(a: Bill, b: Bill) -> list[Finding]:
    """Bill `a` should appear in the history table of the later bill `b`."""
    row = b.history_for(a.bill_month)
    if row is None:
        return [skip("bill_in_later_history", _pair_id(a, b), f"{a.bill_month} not in history")]
    out = [compare(f"bill_in_later_history[{a.bill_month}.bill]", _pair_id(a, b),
                   a.totals.payable_within_due, row.bill, TOL)]
    if a.layout == Layout.PITC_LEGACY:
        out.append(compare(f"bill_in_later_history[{a.bill_month}.units]", _pair_id(a, b),
                           a.legacy_charges.units_consumed, row.units))
    return out


def check_consecutive(a: Bill, b: Bill) -> list[Finding]:
    """Checks that only make sense when `b` is the month right after `a`."""
    pid = _pair_id(a, b)
    out: list[Finding] = []

    # Meter continuity: previous reading this month == present reading last month
    for rb in b.registers:
        ra = a.register(rb.name)
        if ra is None:
            out.append(skip(f"meter_continuity[{rb.name}]", pid,
                            "register missing on earlier bill"))
            continue
        out.append(compare(f"meter_continuity[{rb.name}]", pid, ra.present, rb.previous))

    # Arrears carry forward (less any payment recorded in b's history)
    row = b.history_for(a.bill_month)
    payment = row.payment if row else 0
    out.append(compare("arrears_carry_forward", pid, a.totals.payable_within_due - payment,
                       b.totals.arrears, TOL, what="last payable - payment"))

    # Net-metering bank carry-forward and cycle counter
    if a.net_metering and b.net_metering:
        na, nb = a.net_metering, b.net_metering
        for slot in ("offpeak", "peak"):
            out.append(compare(f"nm_bank_carry_forward[{slot}]", pid,
                               getattr(na.remaining_present, slot),
                               getattr(nb.remaining_prev, slot)))
        out.append(compare("nm_month_counter", pid, na.month_count % na.cycle_length + 1,
                           nb.month_count, what="cycle counter advances by one"))
    return out


def audit_pairs(bills: list[Bill]) -> list[Finding]:
    ordered = sorted(bills, key=lambda x: x.bill_month)
    out: list[Finding] = []
    for a, b in combinations(ordered, 2):
        out += check_history_agreement(a, b)
        out += check_bill_in_later_history(a, b)
        if shift_month(a.bill_month, 1) == b.bill_month:
            out += check_consecutive(a, b)
    return out
