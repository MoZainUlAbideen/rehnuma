"""Single-bill reconciliation checks.

Each check takes a Bill and returns a list of Findings. Checks that do not apply
(e.g. net-metering checks on a conventional bill) return SKIP, never PASS —
a skipped check must never inflate the pass rate.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from rehnuma.engine.findings import Finding, compare, skip, to_rupees
from rehnuma.engine.rates import AMOUNT_TOLERANCE_RS, GST_RATE
from rehnuma.schema import Bill, ConnectionType, Layout, shift_month

TOL = AMOUNT_TOLERANCE_RS

# register name  ->  (net-metering field, ToU slot)
NM_REGISTER_MAP = {
    "import_offpeak": ("import_kwh", "offpeak"),
    "import_peak": ("import_kwh", "peak"),
    "export_offpeak": ("export_kwh", "offpeak"),
    "export_peak": ("export_kwh", "peak"),
}


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


# --- legacy layout charges -------------------------------------------------------
def _legacy_only(name: str, bill: Bill) -> Finding | None:
    if bill.layout != Layout.PESCO_LEGACY or bill.legacy_charges is None:
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


def _govt_split(bill: Bill) -> tuple[int, int]:
    """(government charges on FPA, all other government charges)"""
    govt = bill.legacy_charges.govt
    on_fpa = sum(v for k, v in govt.items() if k.endswith("_on_fpa"))
    return on_fpa, sum(govt.values()) - on_fpa


def check_legacy_current_bill(bill: Bill) -> list[Finding]:
    """Legacy layout: current bill = DISCO charges (excluding FPA) + non-FPA govt charges.
    FPA and its taxes are billed separately as 'Total FPA'."""
    if (s := _legacy_only("legacy_current_bill", bill)):
        return [s]
    c = bill.legacy_charges
    _, govt_other = _govt_split(bill)
    expected = (c.cost_of_electricity + c.meter_rent + c.service_rent + c.fixed_charges
                + c.qta + govt_other)
    return [compare("legacy_current_bill", bill.bill_id, expected, bill.totals.current_bill, TOL)]


def check_legacy_section_totals(bill: Bill) -> list[Finding]:
    if (s := _legacy_only("legacy_section_totals", bill)):
        return [s]
    c = bill.legacy_charges
    out = []
    if c.pesco_total is None:
        out.append(skip("legacy_pesco_total", bill.bill_id, "not printed"))
    else:
        expected = (c.cost_of_electricity + c.meter_rent + c.service_rent + c.fixed_charges
                    + c.fpa + c.qta)
        out.append(compare("legacy_pesco_total", bill.bill_id, expected, c.pesco_total, TOL))
    if c.govt_total is None:
        out.append(skip("legacy_govt_total", bill.bill_id, "not printed"))
    else:
        out.append(compare("legacy_govt_total", bill.bill_id, sum(c.govt.values()),
                           c.govt_total, TOL))
    return out


def check_fpa(bill: Bill) -> list[Finding]:
    """FPA line = units of the reference month x FPA rate; Total FPA = FPA + taxes on FPA;
    and the full tax cascade computed unrounded must reproduce Total FPA."""
    if (s := _legacy_only("fpa", bill)):
        return [s]
    c = bill.legacy_charges
    if c.fpa == 0 and c.total_fpa == 0:
        return [skip("fpa", bill.bill_id, "no FPA on this bill")]
    on_fpa, _ = _govt_split(bill)
    out = [compare("fpa_total_from_lines", bill.bill_id, c.fpa + on_fpa, c.total_fpa, TOL,
                   what="FPA + printed taxes on FPA")]
    if c.fpa_units is None or c.fpa_rate is None:
        out.append(skip("fpa_line", bill.bill_id, "FPA units/rate not printed"))
        return out
    raw = Decimal(c.fpa_units) * c.fpa_rate
    out.append(compare("fpa_line", bill.bill_id, to_rupees(raw), c.fpa, TOL,
                       what=f"{c.fpa_units} units x {c.fpa_rate}"))
    if bill.ed_rate_pct is None:
        out.append(skip("fpa_tax_cascade", bill.bill_id, "ED rate not printed"))
        return out
    ed = raw * bill.ed_rate_pct / 100
    gst = (raw + ed) * GST_RATE
    out.append(compare("fpa_tax_cascade", bill.bill_id, to_rupees(raw + ed + gst), c.total_fpa,
                       TOL, what=f"(FPA + ED {bill.ed_rate_pct}%) x (1 + GST {GST_RATE}), "
                                 "rounded once at the end"))
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
    expected = t.arrears + t.current_bill + t.installment + t.adjustments
    what = "arrears + current bill + installment + adjustments"
    if bill.layout == Layout.PESCO_LEGACY:
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
    check_fpa,
    check_v2_charges,
    check_payable,
    check_arrears_vs_history,
]
