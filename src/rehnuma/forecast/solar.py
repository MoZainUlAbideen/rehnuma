"""Solar (net-metering) households: the last 12 months, and what the 2026 rules change
at renewal.

Two parts, kept apart on purpose:

1. What HAPPENED - from the bill itself, no rates needed. The history table prints the
   running balance each month (for a credit account it only grows more negative), so each
   month's amount is this month's balance minus last month's (payments added back).
   Settlement months - where banked units were cashed out - show as big credits; the
   units column gives the net units settled, so each settlement has a rupees-per-unit.

2. What RENEWAL would change - needs rates, all from secondary sources (solar_rates.json).
   Reg. 21(2) of the Prosumer Regulations 2026: agreements signed before them keep the
   national average POWER purchase price until they expire; renewals move to net billing
   (reg. 14): every imported unit at the retail tariff, every exported unit at the energy
   purchase price. The comparison uses the household's REAL meter readings for a full
   billing cycle and the bills' REAL charges - only the renewal side is computed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from importlib import resources

from rehnuma.schema import Bill, ConnectionType, shift_month


@dataclass(frozen=True)
class MonthAmount:
    month: str
    net_units: int          # history "units": net settled units (0 inside a cycle)
    amount: int             # + charged, - credited that month


@dataclass(frozen=True)
class Settlement:
    month: str
    net_units: int          # negative = net export settled
    amount: int

    @property
    def per_unit(self) -> Decimal:
        """Rupees credited per net exported unit (includes that month's own charges)."""
        return Decimal(self.amount) / Decimal(self.net_units)


@lru_cache(maxsize=1)
def solar_rates() -> dict:
    text = resources.files("rehnuma.data").joinpath("solar_rates.json").read_text("utf-8")
    return json.loads(text)


def monthly_amounts(bill: Bill) -> list[MonthAmount]:
    """Each month's own amount, from consecutive rows of the balance history, plus this
    bill's own current bill. A gap in the history ends the series (nothing is guessed)."""
    rows = sorted(bill.history, key=lambda h: h.month)
    out: list[MonthAmount] = []
    for prev, cur in zip(rows, rows[1:], strict=False):
        if shift_month(prev.month, 1) != cur.month:
            out = []                                 # keep only the latest unbroken run
            continue
        out.append(MonthAmount(cur.month, int(cur.units), cur.bill - prev.bill + prev.payment))
    if rows and shift_month(rows[-1].month, 1) == bill.bill_month:
        # the balance change, not "current bill": the fuel adjustment is billed on top of it
        # (Mar-26: current bill -872, FPA +1,164, balance moved +292 - as its next history row)
        change = bill.totals.payable_within_due - bill.totals.arrears
        out.append(MonthAmount(bill.bill_month, _own_net_units(bill), change))
    return out


def _own_net_units(bill: Bill) -> int:
    nm = bill.net_metering
    if nm is None or nm.month_count != nm.cycle_length:
        return 0                                      # inside a cycle nothing is settled
    return nm.net_kwh.total - nm.remaining_prev.total   # banked export is + in the box


def settlements(amounts: list[MonthAmount]) -> list[Settlement]:
    return [Settlement(a.month, a.net_units, a.amount) for a in amounts if a.net_units < 0]


# ----------------------------------------------------------------- renewal comparison
@dataclass(frozen=True)
class CycleUsage:
    months: tuple[str, ...]
    import_offpeak: int
    import_peak: int
    export_total: int
    actual_electricity: int      # what the bills charged for electricity (- = credit)


def cycle_bills(bill: Bill, others: list[Bill]) -> list[Bill] | None:
    """The bills of the billing cycle that ends with `bill`, linked by meter continuity
    (each bill's previous reading = the earlier bill's present reading). None if any
    month of the cycle is missing."""
    nm = bill.net_metering
    if nm is None or nm.month_count != nm.cycle_length:
        return None
    chain = [bill]
    while len(chain) < nm.cycle_length:
        first = chain[0]
        prev = next((b for b in others if b.bill_month == shift_month(first.bill_month, -1)
                     and _continuous(b, first)), None)
        if prev is None:
            return None
        chain.insert(0, prev)
    return chain


def _continuous(a: Bill, b: Bill) -> bool:
    pairs = [(a.register(r.name), r) for r in b.registers]
    return bool(pairs) and all(ra is not None and ra.present == rb.previous for ra, rb in pairs)


def _electricity(b: Bill) -> int:
    if b.v2_charges is not None:
        return b.v2_charges.total_electricity_charges
    return int(b.legacy_charges.cost_of_electricity)    # legacy layout


def cycle_usage(bills: list[Bill]) -> CycleUsage:
    nm = [b.net_metering for b in bills]
    return CycleUsage(
        months=tuple(b.bill_month for b in bills),
        import_offpeak=sum(n.import_kwh.offpeak for n in nm),
        import_peak=sum(n.import_kwh.peak for n in nm),
        export_total=sum(n.export_kwh.total for n in nm),
        actual_electricity=sum(_electricity(b) for b in bills),
    )


@dataclass(frozen=True)
class RenewalScenario:
    usage: CycleUsage
    imports_cost: Decimal
    exports_credit: dict[str, Decimal]        # "low" / "high" energy purchase price
    fixed_estimate: Decimal                   # non-energy charges, kept the same

    def renewal_total(self, which: str) -> Decimal:
        return self.imports_cost - self.exports_credit[which] + self.fixed_estimate

    def difference(self, which: str) -> Decimal:
        """How much MORE the same cycle would cost on renewal terms (+ = worse)."""
        return self.renewal_total(which) - self.usage.actual_electricity


def renewal_scenario(bills: list[Bill]) -> RenewalScenario:
    """Price one real billing cycle on renewal terms (reg. 14 net billing at the energy
    purchase price). The non-energy charges (fixed charges) are taken from the cycle's
    in-cycle months, where no energy is billed because units are banked, and assumed the
    same on renewal - so the difference is the energy terms only."""
    r = solar_rates()
    u = cycle_usage(bills)
    tou = r["tou"]
    imports = u.import_offpeak * Decimal(tou["offpeak"]) + u.import_peak * Decimal(tou["peak"])
    epp = r["epp"]
    credits = {k: u.export_total * Decimal(epp[k]) for k in ("low", "high")}
    in_cycle = [_electricity(b) for b in bills
                if b.net_metering.month_count != b.net_metering.cycle_length]
    fixed = Decimal(sum(in_cycle)) / len(in_cycle) * len(bills) if in_cycle else Decimal(0)
    return RenewalScenario(u, imports, credits, fixed)


@dataclass
class SolarOutlook:
    bill_id: str
    amounts: list[MonthAmount]
    settlements: list[Settlement]
    renewal: RenewalScenario | None

    @property
    def last_12(self) -> list[MonthAmount]:
        return self.amounts[-12:]

    @property
    def last_12_total(self) -> int:
        return sum(a.amount for a in self.last_12)

    @property
    def import_months(self) -> list[MonthAmount]:
        """Months billed as net imports (Jan/Feb-26: units billed monthly, not banked)."""
        return [a for a in self.last_12 if a.net_units > 0]

    def in_cycle_level(self, latest: bool) -> tuple[list[str], int] | None:
        """Average charge of the first / last two in-cycle months (nothing settled)."""
        months = [a for a in self.last_12 if a.net_units == 0]
        pick = months[-2:] if latest else months[:2]
        if len(pick) < 2:
            return None
        return [a.month for a in pick], round(sum(a.amount for a in pick) / len(pick))


def solar_outlook(bill: Bill, others: list[Bill] | None = None) -> SolarOutlook:
    if bill.connection_type != ConnectionType.NET_METERING:
        raise ValueError("not a net-metering bill")
    amounts = monthly_amounts(bill)
    cycle = cycle_bills(bill, others or [])
    return SolarOutlook(bill.bill_id, amounts, settlements(amounts),
                        renewal_scenario(cycle) if cycle else None)
