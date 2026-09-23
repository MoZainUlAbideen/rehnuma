"""BillStory: the verified facts a household actually cares about.

Built by user research (docs/USER_RESEARCH.md): most people ask the lineman to
"summarise the bill". Solar owners want units sold vs used and how that became the
bill; households without solar worry about peak hours. So the story carries:

  * what to pay (or how much credit) and by when
  * solar: taken from grid vs sent back, per time slot, and the banked units
  * no solar: flat vs time-of-use tariff, and the 200-unit protected limit
  * where the money went, and whether Rehnuma's audit found anything

Every number here comes from the bill or the deterministic engine. The renderer
(and later the LLM) may only phrase these numbers - never compute new ones.
Money is rounded to whole rupees, the way a lineman would say it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from rehnuma.engine import Status, audit_bill
from rehnuma.schema import Bill, ConnectionType, Layout, shift_month
from rehnuma.tariffs import (
    PROTECTED_LIMIT_KWH,
    PROTECTED_LOOKBACK_MONTHS,
    protected_eligible,
    schedule_for,
)

NEAR_LIMIT_KWH = 170   # warn a protected household from here on


def rs(x: Decimal | int) -> int:
    return int(Decimal(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Slots:
    offpeak: int
    peak: int

    @property
    def total(self) -> int:
        return self.offpeak + self.peak


@dataclass(frozen=True)
class Protected:
    is_protected: bool
    months_over_limit: int          # in the 6-month lookback
    near_limit: bool                # protected, but this month is close to 200


@dataclass(frozen=True)
class Solar:
    imported: Slots
    exported: Slots
    net: Slots                      # imported - exported (negative = sent more than used)
    month_count: int
    cycle_length: int
    banked: Slots                   # after this bill; offpeak > 0 = extra units saved
    settling: bool


@dataclass(frozen=True)
class Fpa:
    ref_month: str
    units: int


@dataclass(frozen=True)
class Audit:
    checks_passed: int
    problems: int
    largest_gap_rs: int             # biggest |difference| among the problems


@dataclass(frozen=True)
class BillStory:
    bill_id: str
    bill_month: str
    due_date: date | None
    payable: int
    payable_after_due: int
    current_bill: int
    bill_effect: int                # payable - arrears: what THIS bill added (+) or credited (-),
                                    # including FPA billed on its own line (legacy layout)
    tariff: str
    tariff_kind: str                # "flat" (A-1a) | "tou" (A-1b)
    solar: Solar | None
    units: int | None               # conventional only
    tou_units: Slots | None         # conventional ToU only
    last_year_units: int | None
    protected: Protected | None
    energy_rs: int
    taxes_rs: int
    fpa_rs: int | None              # total FPA incl. its taxes (legacy layout)
    fpa_months: list[Fpa] = field(default_factory=list)
    audit: Audit | None = None

    @property
    def is_credit(self) -> bool:
        return self.payable < 0

    def allowed_numbers(self) -> set[Decimal]:
        """Every number a summary is allowed to state (used by the faithfulness check)."""
        vals: list[int] = [self.payable, self.payable_after_due, self.current_bill,
                           self.bill_effect,
                           self.energy_rs, self.taxes_rs,
                           PROTECTED_LIMIT_KWH, PROTECTED_LOOKBACK_MONTHS]
        y, m = (int(p) for p in self.bill_month.split("-"))
        vals += [y, m]
        if self.due_date:
            vals += [self.due_date.day, self.due_date.month, self.due_date.year]
        for opt in (self.units, self.last_year_units, self.fpa_rs):
            if opt is not None:
                vals.append(opt)
        if self.tou_units:
            vals += [self.tou_units.offpeak, self.tou_units.peak]
        if self.protected:
            vals.append(self.protected.months_over_limit)
        for f in self.fpa_months:
            fy, fm = (int(p) for p in f.ref_month.split("-"))
            vals += [f.units, fy, fm]
        if self.solar:
            s = self.solar
            for slots in (s.imported, s.exported, s.net, s.banked):
                vals += [slots.offpeak, slots.peak, slots.total]
            vals += [s.month_count, s.cycle_length]
        if self.audit:
            vals += [self.audit.checks_passed, self.audit.problems, self.audit.largest_gap_rs]
        return {Decimal(abs(v)) for v in vals}


def _slots(t) -> Slots:
    return Slots(int(t.offpeak), int(t.peak))


def _protected(bill: Bill, units: int) -> Protected | None:
    if not bill.tariff.startswith("A-1a"):
        return None
    schedule = schedule_for(bill.tariff, bill.bill_month)
    if schedule is None or not schedule.has_protected:
        return None          # e.g. 2019/2021: no protected category on those bills
    eligible = protected_eligible(bill.history, bill.bill_month, bill.tariff)
    if eligible is None:
        return None
    lookback = [bill.history_for(shift_month(bill.bill_month, -k))
                for k in range(1, PROTECTED_LOOKBACK_MONTHS + 1)]
    over = sum(1 for h in lookback if h is not None and h.units > PROTECTED_LIMIT_KWH)
    return Protected(eligible, over, eligible and units >= NEAR_LIMIT_KWH)


def _money(bill: Bill) -> tuple[int, int, int | None]:
    """(energy, taxes, total FPA) in whole rupees."""
    if bill.layout == Layout.PITC_LEGACY:
        c = bill.legacy_charges
        on_fpa = sum((v for k, v in c.govt.items() if k.endswith("_on_fpa")), Decimal(0))
        taxes = sum(c.govt.values(), Decimal(0)) - on_fpa
        energy = (c.cost_of_electricity + c.meter_rent + c.service_rent + c.fixed_charges
                  + c.fc_surcharge + c.tr_surcharge + c.qta)
        return rs(energy), rs(taxes), rs(c.total_fpa)
    c = bill.v2_charges
    return rs(c.net_electricity_charges), rs(c.taxes), None


def _audit(bill: Bill) -> Audit:
    findings = audit_bill(bill)
    fails = [f for f in findings if f.status == Status.FAIL]
    gaps = [abs(f.delta) for f in fails if f.delta is not None]
    return Audit(sum(f.status == Status.PASS for f in findings), len(fails),
                 rs(max(gaps)) if gaps else 0)


def build_story(bill: Bill) -> BillStory:
    solar = units = tou = last_year = protected = None
    if bill.connection_type == ConnectionType.NET_METERING:
        nm = bill.net_metering
        solar = Solar(_slots(nm.import_kwh), _slots(nm.export_kwh), _slots(nm.net_kwh),
                      nm.month_count, nm.cycle_length, _slots(nm.remaining_present),
                      nm.month_count == nm.cycle_length)
    else:
        units = (bill.legacy_charges.units_consumed if bill.legacy_charges
                 else sum(r.units for r in bill.registers if r.name.startswith("import")))
        off, peak = bill.register("import_offpeak"), bill.register("import_peak")
        if off and peak:
            tou = Slots(off.units, peak.units)
        ly = bill.history_for(shift_month(bill.bill_month, -12))
        last_year = int(ly.units) if ly is not None else None
        protected = _protected(bill, units)

    energy, taxes, fpa = _money(bill)
    fpa_months = ([Fpa(p.ref_month, p.units) for p in bill.legacy_charges.fpa_parts]
                  if bill.legacy_charges else [])
    return BillStory(
        bill_id=bill.bill_id, bill_month=bill.bill_month, due_date=bill.due_date,
        payable=bill.totals.payable_within_due, payable_after_due=bill.totals.payable_after_due,
        current_bill=bill.totals.current_bill,
        bill_effect=bill.totals.payable_within_due - bill.totals.arrears,
        tariff=bill.tariff,
        tariff_kind="flat" if bill.tariff.startswith("A-1a") else "tou",
        solar=solar, units=units, tou_units=tou, last_year_units=last_year,
        protected=protected, energy_rs=energy, taxes_rs=taxes, fpa_rs=fpa,
        fpa_months=fpa_months, audit=_audit(bill),
    )
