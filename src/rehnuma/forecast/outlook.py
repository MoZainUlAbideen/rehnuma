"""The 12-month outlook for a conventional (A-1a) household: units, rupees, and the
200-unit protected limit - the thing that actually moves these bills.

Going over 200 units in ONE month removes protected rates for the next six. And an
unprotected household pays the rate of the slab it reaches on EVERY unit (IESCO Mar-23:
25.53 x 393), so each slab edge (100, 200, ... 700) is a cliff too: 501 units cost more
than 500 by far more than one unit's price.

The outlook finds months forecast just above an edge - within reach, i.e. at most 15% over
it - and prices the counterfactual of holding that month at the edge, through the full
12-month cost path (so a kept protected status counts for the six months it protects).
Months far above every edge get no advice: cutting 558 units to 200 is not a tip.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from rehnuma.forecast.cost import MonthCost, cost_path, latest_schedule
from rehnuma.forecast.units import UnitForecast, forecast_units, monthly_units
from rehnuma.schema import Bill, ConnectionType
from rehnuma.tariffs import PROTECTED_LIMIT_KWH, Schedule

DEFAULT_ED_PCT = Decimal("1.5")
REACH = 0.15            # "just above an edge": at most 15% over it (200 -> 230, 500 -> 575)


class NotSupported(ValueError):
    """This bill can't get an outlook yet (solar, time-of-use, missing history)."""


@dataclass(frozen=True)
class EdgeChance:
    month: str
    units: int
    edge: int
    saving: Decimal         # 12-month saving from holding THIS month at the edge
    protected_gained: int = 0   # months that become protected because of it

    @property
    def over(self) -> int:
        return self.units - self.edge

    @property
    def keeps_protection(self) -> bool:
        """Only when holding this month at 200 actually changes later months - a household
        already unprotected by an earlier month gains nothing but the slab edge."""
        return self.protected_gained > 0

    @property
    def per_unit(self) -> Decimal:
        """Rupees saved per unit NOT used - the leverage. A normal unit costs Rs 10-50;
        a unit that pushes a household over 200 can cost over Rs 1,000."""
        return self.saving / self.over


@dataclass
class Outlook:
    bill_id: str
    from_month: str
    schedule: Schedule
    units: list[UnitForecast]
    months: list[MonthCost]
    cross_months: list[str]                 # forecast above 200 units
    chances: list[EdgeChance] = field(default_factory=list)
    capped: list[MonthCost] = field(default_factory=list)   # every chance taken at once
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((m.total for m in self.months), Decimal(0))

    @property
    def total_if_capped(self) -> Decimal:
        return sum((m.total for m in self.capped), Decimal(0)) if self.capped else self.total

    @property
    def saving_if_capped(self) -> Decimal:
        return self.total - self.total_if_capped

    @property
    def unprotected_months(self) -> list[str]:
        return [m.month for m in self.months if not m.protected]


def edges(schedule: Schedule) -> list[int]:
    out = {b.upper for b in schedule.unprotected if b.upper is not None}
    if schedule.has_protected:
        out.add(PROTECTED_LIMIT_KWH)
    return sorted(out)


def edge_in_reach(units: int, schedule: Schedule) -> int | None:
    """The slab edge just below `units`, if the month is at most REACH over it."""
    below = [e for e in edges(schedule) if e < units]
    if not below:
        return None
    edge = below[-1]
    return edge if units - edge <= math.ceil(REACH * edge) else None


def outlook(bill: Bill, schedule: Schedule | None = None) -> Outlook:
    if bill.connection_type != ConnectionType.CONVENTIONAL:
        raise NotSupported("solar (net-metering) bills get the settlement outlook instead")
    if not bill.tariff.startswith("A-1a"):
        raise NotSupported(f"tariff {bill.tariff}: only flat A-1a residential is modelled")
    schedule = schedule or latest_schedule("A-1a")
    series = monthly_units(bill)
    try:
        units = forecast_units(series, bill.bill_month)
    except ValueError as e:
        raise NotSupported(str(e)) from e
    kw = bill.sanctioned_load_kw or Decimal(1)
    ed = bill.ed_rate_pct if bill.ed_rate_pct is not None else DEFAULT_ED_PCT
    notes = []
    if bill.sanctioned_load_kw is None:
        notes.append("sanctioned load not on the bill: fixed charge priced for 1 kW")
    if schedule.confidence != "official":
        notes.append(f"rates: {schedule.id} ({schedule.confidence} source)")
    plan = [(u.month, u.units) for u in units]
    months = cost_path(series, plan, schedule, kw, ed, bill.tariff)
    cross = [u.month for u in units if u.units > PROTECTED_LIMIT_KWH]
    total = sum((m.total for m in months), Decimal(0))

    def total_with(cuts: dict[str, int]) -> tuple[Decimal, list[MonthCost]]:
        path = cost_path(series, [(m, cuts.get(m, n)) for m, n in plan], schedule, kw, ed,
                         bill.tariff)
        return sum((m.total for m in path), Decimal(0)), path

    chances = []
    for m, n in plan:
        edge = edge_in_reach(n, schedule)
        if edge is not None:
            cut_total, cut_path = total_with({m: edge})
            gained = sum(mc.protected for mc in cut_path if mc.month != m) \
                - sum(mc.protected for mc in months if mc.month != m)
            chances.append(EdgeChance(m, n, edge, total - cut_total, max(gained, 0)))
    chances.sort(key=lambda c: c.per_unit, reverse=True)
    capped = total_with({c.month: c.edge for c in chances})[1] if chances else []
    return Outlook(bill.bill_id, bill.bill_month, schedule, units, months, cross, chances,
                   capped, notes)
