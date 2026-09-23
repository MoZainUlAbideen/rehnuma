"""Single-bill reconciliation checks.

Each check takes a Bill and returns a list of Findings. Checks that do not apply
(e.g. net-metering checks on a conventional bill) return SKIP, never PASS -
a skipped check must never inflate the pass rate.

Two kinds of check live here:
  * reconciliation - do the printed lines add up to the printed totals?
  * recomputation  - does calculator.py, working from first principles,
                     reproduce each printed line?
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

from rehnuma.engine import calculator as calc
from rehnuma.engine.findings import Finding, compare, skip, to_rupees
from rehnuma.engine.rates import AMOUNT_TOLERANCE_RS
from rehnuma.schema import Bill, ConnectionType, Layout, shift_month

TOL = AMOUNT_TOLERANCE_RS

# register name  ->  (net-metering field, ToU slot)
NM_REGISTER_MAP = {
    "import_offpeak": ("import_kwh", "offpeak"),
    "import_peak": ("import_kwh", "peak"),
    "export_offpeak": ("export_kwh", "offpeak"),
    "export_peak": ("export_kwh", "peak"),
}


def printed_step(printed: Decimal) -> Decimal:
    """Smallest unit the bill printed: Rs 1 for '1,164', 0.01 for '12.34'."""
    return Decimal(1).scaleb(min(printed.as_tuple().exponent, 0))


def as_printed(value: Decimal, printed: Decimal) -> Decimal:
    """Round an unrounded computed value to the precision the bill printed."""
    return value.quantize(printed_step(printed), rounding=ROUND_HALF_UP)


def compare_printed(check: str, bill_id: str, computed: Decimal, printed: Decimal,
                    what: str) -> Finding:
    """Compare a RECOMPUTED line with the printed one. Tolerance is one step of the
    printed precision - never the flat Rs 1 used for totals, which would let a wrong
    Rs 5.41 pass for a printed Rs 5.04."""
    return compare(check, bill_id, as_printed(computed, printed), printed,
                   printed_step(printed), what=f"{what} = {computed:.4f}")


# --- meter -------------------------------------------------------------------
def check_register_units(bill: Bill) -> list[Finding]:
    """units == round((present - previous) * MF) for every register row."""
    if not bill.registers:
        return [skip("register_units", bill.bill_id, "no register rows on bill")]
    out = []
    for r in bill.registers:
        expected = to_rupees((r.present - r.previous) * r.mf)
        out.append(compare(f"register_units[{r.name}]", bill.bill_id, expected, r.units,
                           what=f"{r.present} - {r.previous}"))
    return out


# --- net metering ------------------------------------------------------------
def check_nm_registers_match_box(bill: Bill) -> list[Finding]:
    """Register rows must agree with the import/export figures in the net-metering box."""
    nm = bill.net_metering
    if nm is None:
        return [skip("nm_registers_match_box", bill.bill_id, "conventional connection")]
    out = []
    for reg_name, (field, slot) in NM_REGISTER_MAP.items():
        reg = bill.register(reg_name)
        box_value = getattr(getattr(nm, field), slot)
        if reg is None:
            out.append(skip(f"nm_registers_match_box[{reg_name}]", bill.bill_id,
                            f"register row not on bill (box shows {box_value})"))
            continue
        out.append(compare(f"nm_registers_match_box[{reg_name}]", bill.bill_id,
                           reg.units, box_value))
    return out


def check_nm_net_kwh(bill: Bill) -> list[Finding]:
    """net = import - export, per ToU slot."""
    nm = bill.net_metering
    if nm is None:
        return [skip("nm_net_kwh", bill.bill_id, "conventional connection")]
    return [
        compare(f"nm_net_kwh[{slot}]", bill.bill_id,
                getattr(nm.import_kwh, slot) - getattr(nm.export_kwh, slot),
                getattr(nm.net_kwh, slot))
        for slot in ("offpeak", "peak")
    ]


def check_nm_remaining_kwh(bill: Bill) -> list[Finding]:
    """Banked units: inside a cycle, remaining = previous remaining - net.
    On the last month of the cycle the bank is settled and resets to 0."""
    nm = bill.net_metering
    if nm is None:
        return [skip("nm_remaining_kwh", bill.bill_id, "conventional connection")]
    out = []
    settling = nm.month_count == nm.cycle_length
    for slot in ("offpeak", "peak"):
        if settling:
            expected = 0
        else:
            expected = getattr(nm.remaining_prev, slot) - getattr(nm.net_kwh, slot)
        out.append(compare(f"nm_remaining_kwh[{slot}]", bill.bill_id, expected,
                           getattr(nm.remaining_present, slot),
                           what=f"month {nm.month_count}/{nm.cycle_length}"))
    return out


# --- legacy (PITC) layout: reconciliation ------------------------------------------
def _legacy_only(name: str, bill: Bill) -> Finding | None:
    if bill.layout != Layout.PITC_LEGACY or bill.legacy_charges is None:
        return skip(name, bill.bill_id, f"not applicable to layout {bill.layout.value}")
    return None


def check_legacy_units_consumed(bill: Bill) -> list[Finding]:
    if (s := _legacy_only("legacy_units_consumed", bill)):
        return [s]
    c = bill.legacy_charges
    if bill.connection_type == ConnectionType.NET_METERING:
        expected = bill.net_metering.net_kwh.total
        what = "net off-peak + net peak"
    else:
        expected = sum(r.units for r in bill.registers if r.name.startswith("import"))
        what = "sum of import registers"
    return [compare("legacy_units_consumed", bill.bill_id, expected, c.units_consumed, what=what)]


def _govt_split(bill: Bill) -> tuple[Decimal, Decimal]:
    """(government charges on FPA, all other government charges)"""
    govt = bill.legacy_charges.govt
    on_fpa = sum((v for k, v in govt.items() if k.endswith("_on_fpa")), Decimal(0))
    return on_fpa, sum(govt.values(), Decimal(0)) - on_fpa


def _disco_lines_excl_fpa(bill: Bill) -> Decimal:
    c = bill.legacy_charges
    return (c.cost_of_electricity + c.meter_rent + c.service_rent + c.fixed_charges
            + c.fc_surcharge + c.tr_surcharge + c.qta)


def check_legacy_current_bill(bill: Bill) -> list[Finding]:
    """Current bill = DISCO charges (excluding FPA) + non-FPA govt charges.
    FPA and its taxes are billed separately as 'Total FPA'."""
    if (s := _legacy_only("legacy_current_bill", bill)):
        return [s]
    _, govt_other = _govt_split(bill)
    return [compare("legacy_current_bill", bill.bill_id,
                    _disco_lines_excl_fpa(bill) + govt_other, bill.totals.current_bill, TOL)]


def check_legacy_section_totals(bill: Bill) -> list[Finding]:
    if (s := _legacy_only("legacy_section_totals", bill)):
        return [s]
    c = bill.legacy_charges
    out = []
    if c.disco_total is None:
        out.append(skip("legacy_disco_total", bill.bill_id, "not printed"))
    else:
        out.append(compare("legacy_disco_total", bill.bill_id,
                           _disco_lines_excl_fpa(bill) + c.fpa, c.disco_total, TOL))
    if c.govt_total is None:
        out.append(skip("legacy_govt_total", bill.bill_id, "not printed"))
    else:
        out.append(compare("legacy_govt_total", bill.bill_id,
                           sum(c.govt.values(), Decimal(0)), c.govt_total, TOL))
    return out


# --- legacy (PITC) layout: recomputation --------------------------------------------
def check_rate_lines(bill: Bill) -> list[Finding]:
    """Cost of electricity = sum of the printed rate x units lines."""
    if (s := _legacy_only("rate_lines", bill)):
        return [s]
    c = bill.legacy_charges
    if not c.rate_lines:
        return [skip("rate_lines", bill.bill_id, "no Bill Calculation block printed")]
    lines = " + ".join(f"{ln.rate}x{ln.units}" for ln in c.rate_lines)
    out = [compare_printed("rate_lines", bill.bill_id, calc.cost_of_electricity(c.rate_lines),
                           c.cost_of_electricity, what=lines)]
    billed_units = sum(ln.units for ln in c.rate_lines)
    if bill.connection_type == ConnectionType.CONVENTIONAL:
        out.append(compare("rate_lines_units", bill.bill_id, c.units_consumed, billed_units,
                           what="units across rate lines"))
    return out


def _unrounded_cost(bill: Bill) -> Decimal:
    """Prefer the unrounded cost from the rate lines; bills print it rounded."""
    c = bill.legacy_charges
    return calc.cost_of_electricity(c.rate_lines) if c.rate_lines else c.cost_of_electricity


def check_levies(bill: Bill) -> list[Finding]:
    """Recompute ED, GST and NJ surcharge from first principles."""
    if (s := _legacy_only("levies", bill)):
        return [s]
    c, govt, bid = bill.legacy_charges, bill.legacy_charges.govt, bill.bill_id
    cost = _unrounded_cost(bill)
    out: list[Finding] = []

    ed = None
    if bill.ed_rate_pct is not None:
        ed = calc.electricity_duty(cost, c.qta, bill.ed_rate_pct)
    if "electricity_duty" not in govt:
        out.append(skip("electricity_duty", bid, "line not printed"))
    elif ed is None:
        out.append(skip("electricity_duty", bid, "ED rate not printed"))
    else:
        out.append(compare_printed("electricity_duty", bid, ed, govt["electricity_duty"],
                                   what=f"{bill.ed_rate_pct}% x (cost + QTA)"))

    if "gst" not in govt:
        out.append(skip("gst_on_energy", bid, "line not printed"))
    elif ed is None:
        out.append(skip("gst_on_energy", bid, "needs ED rate"))
    else:
        gst = calc.gst_on_energy(cost, c.fc_surcharge, c.qta, ed, bill.bill_month)
        out.append(compare_printed("gst_on_energy", bid, gst, govt["gst"],
                                   what="GST x (cost + FC + QTA + ED)"))

    if "nj_surcharge" in govt:
        out.append(compare_printed("nj_surcharge", bid, calc.nj_surcharge(c.units_consumed),
                                   govt["nj_surcharge"], what=f"0.10 x {c.units_consumed}"))
    else:
        out.append(skip("nj_surcharge", bid, "line not printed"))
    return out


def check_fpa(bill: Bill) -> list[Finding]:
    """FPA lines add up to Total FPA; each FPA month matches the bill's own history;
    and the unrounded tax cascade reproduces Total FPA."""
    if (s := _legacy_only("fpa", bill)):
        return [s]
    c, bid = bill.legacy_charges, bill.bill_id
    if c.fpa == 0 and c.total_fpa == 0:
        return [skip("fpa", bid, "no FPA on this bill")]
    on_fpa, _ = _govt_split(bill)
    out = [compare("fpa_total_from_lines", bid, c.fpa + on_fpa, c.total_fpa, TOL,
                   what="FPA + printed taxes on FPA")]
    if not c.fpa_parts:
        out.append(skip("fpa_cascade", bid, "FPA reference month/units not printed"))
        return out

    for part in c.fpa_parts:
        row = bill.history_for(part.ref_month)
        if row is None:
            out.append(skip(f"fpa_units_vs_history[{part.ref_month}]", bid, "month not in history"))
        else:
            out.append(compare(f"fpa_units_vs_history[{part.ref_month}]", bid, row.units,
                               part.units))

    if all(p.rate is not None for p in c.fpa_parts):
        raw = sum((p.rate * p.units for p in c.fpa_parts), Decimal(0))
        out.append(compare_printed("fpa_line", bid, raw, c.fpa, what="sum(units x FPA rate)"))
    else:
        out.append(skip("fpa_line", bid, "FPA rate not printed"))

    if bill.ed_rate_pct is None:
        out.append(skip("fpa_tax_cascade", bid, "ED rate not printed"))
        return out
    b = calc.fpa_breakdown(c.fpa_parts, bill.ed_rate_pct, printed_fpa=c.fpa)
    out.append(compare_printed("fpa_tax_cascade", bid, b.total, c.total_fpa,
                               what="FPA + ED + GST(ref-month rate, rounded per month)"))
    if "gst_on_fpa" in c.govt:
        out.append(compare_printed("gst_on_fpa", bid, b.gst_on_fpa, c.govt["gst_on_fpa"],
                                   what="GST at FPA reference-month rate"))
    return out


# --- v2 layout charges -------------------------------------------------------
def check_v2_charges(bill: Bill) -> list[Finding]:
    if bill.layout != Layout.PESCO_V2_2026 or bill.v2_charges is None:
        return [skip("v2_charges", bill.bill_id, f"not applicable to layout {bill.layout.value}")]
    c = bill.v2_charges
    return [
        compare("v2_net_charges", bill.bill_id, c.total_electricity_charges - c.subsidies,
                c.net_electricity_charges, TOL, what="total - subsidies"),
        compare("v2_current_bill", bill.bill_id, c.net_electricity_charges + c.taxes,
                bill.totals.current_bill, TOL, what="net charges + taxes"),
    ]


# --- totals (both layouts) ---------------------------------------------------
def check_payable(bill: Bill) -> list[Finding]:
    t = bill.totals
    expected = Decimal(t.arrears + t.current_bill + t.installment + t.adjustments)
    what = "arrears + current bill + installment + adjustments"
    if bill.layout == Layout.PITC_LEGACY:
        expected += bill.legacy_charges.total_fpa
        what += " + total FPA"
    return [
        compare("payable_within_due", bill.bill_id, expected, t.payable_within_due, TOL, what),
        compare("payable_after_due", bill.bill_id, t.payable_within_due + t.lp_surcharge,
                t.payable_after_due, TOL, what="payable within due + LP surcharge"),
    ]


def check_arrears_vs_history(bill: Bill) -> list[Finding]:
    """This month's arrears should equal last month's balance in the bill-history table,
    less any payment recorded against it."""
    prev = bill.history_for(shift_month(bill.bill_month, -1))
    if prev is None:
        return [skip("arrears_vs_history", bill.bill_id, "previous month not in history")]
    return [compare("arrears_vs_history", bill.bill_id, prev.bill - prev.payment,
                    bill.totals.arrears, TOL, what=f"history {prev.month} balance - payment")]


SINGLE_BILL_CHECKS: list[Callable[[Bill], list[Finding]]] = [
    check_register_units,
    check_nm_registers_match_box,
    check_nm_net_kwh,
    check_nm_remaining_kwh,
    check_legacy_units_consumed,
    check_legacy_current_bill,
    check_legacy_section_totals,
    check_rate_lines,
    check_levies,
    check_fpa,
    check_v2_charges,
    check_payable,
    check_arrears_vs_history,
]