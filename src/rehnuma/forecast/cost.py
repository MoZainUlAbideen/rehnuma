"""What a month's units cost at today's rates, with protected status tracked month by month.

Included: energy (slab engine), electricity duty and GST on energy (engine/calculator.py -
the same functions that reproduce real bills), and the fixed charge per sanctioned kW.
Left out, and said so to the user: the fuel adjustment (FPA - NEPRA sets it after each
month, it cannot be known in advance), quarterly adjustments, TV fee and arrears.

The fixed charge comes from a secondary source and its tax treatment is not confirmed, so
it is added untaxed and reported as its own line.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from importlib import resources

from rehnuma.engine.calculator import cost_of_electricity, electricity_duty, gst_on_energy
from rehnuma.schema import HistoryEntry
from rehnuma.tariffs import (
    PROTECTED_LIMIT_KWH,
    Schedule,
    load_schedules,
    protected_eligible,
    slab_rate_lines,
)


@dataclass(frozen=True)
class MonthCost:
    month: str
    units: int
    protected: bool
    energy: Decimal
    ed: Decimal
    gst: Decimal
    fixed: Decimal

    @property
    def total(self) -> Decimal:
        return self.energy + self.ed + self.gst + self.fixed


def latest_schedule(tariff_prefix: str = "A-1a") -> Schedule:
    """Today's rates: the newest schedule for this tariff."""
    return [s for s in load_schedules() if s.tariff_prefix == tariff_prefix][-1]


@lru_cache(maxsize=1)
def _fixed_tables() -> dict[str, dict]:
    text = resources.files("rehnuma.data").joinpath("tariff_schedules.json").read_text("utf-8")
    return {s["id"]: s.get("fixed_charges_per_kw", {}) for s in json.loads(text)["schedules"]}


def fixed_per_kw(schedule: Schedule, units: int, protected: bool) -> Decimal:
    """Rs per sanctioned kW for the band this month's units reach (0 if not published)."""
    table = _fixed_tables().get(schedule.id, {})
    bands = table.get("protected" if protected and units <= PROTECTED_LIMIT_KWH
                      else "unprotected", [])
    for upper, rate in bands:
        if upper is None or units <= upper:
            return Decimal(rate)
    return Decimal(0)


def month_cost(month: str, units: int, protected: bool, schedule: Schedule,
               sanctioned_kw: Decimal, ed_rate_pct: Decimal) -> MonthCost:
    energy = cost_of_electricity(slab_rate_lines(units, schedule, protected))
    ed = electricity_duty(energy, Decimal(0), ed_rate_pct)
    gst = gst_on_energy(energy, Decimal(0), Decimal(0), ed, month)
    fixed = fixed_per_kw(schedule, units, protected) * sanctioned_kw if units > 0 else Decimal(0)
    return MonthCost(month, units, protected and units <= PROTECTED_LIMIT_KWH, energy, ed, gst,
                     fixed)


def cost_path(history: dict[str, int], plan: list[tuple[str, int]], schedule: Schedule,
              sanctioned_kw: Decimal, ed_rate_pct: Decimal,
              tariff: str = "A-1a") -> list[MonthCost]:
    """Cost of each planned month in order. Protected status is re-decided every month
    from the 6 months before it - including forecast months - so crossing 200 units once
    costs protected rates for the next six months, exactly as the rule works."""
    seen = [HistoryEntry(month=m, units=Decimal(u), bill=0) for m, u in history.items()]
    out = []
    for month, units in plan:
        status = protected_eligible(seen, month, tariff)
        if status is None:
            raise ValueError(f"not enough history before {month} to decide protected status")
        out.append(month_cost(month, units, status, schedule, sanctioned_kw, ed_rate_pct))
        seen.append(HistoryEntry(month=month, units=Decimal(units), bill=0))
    return out
