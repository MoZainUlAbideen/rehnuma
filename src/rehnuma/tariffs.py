"""Domestic tariff schedules and the slab engine.

Slab rules (from S.R.O. 1165(I)/2022 as reported, and confirmed on real bills):
  * "all"            - every consumer gets the benefit of ONE previous slab: units up to
                       the top of the previous slab are charged at that slab's rate, the
                       rest at the current slab's rate. (IESCO Jul-19: 8.11x200 + 10.20x3)
  * "protected_only" - only protected consumers get that benefit; unprotected consumers
                       pay the rate of the slab reached on EVERY unit. (IESCO Mar-23: 25.53x393)

Protected = non-ToU residential, <= 200 kWh in each of the previous 6 months.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from importlib import resources

from rehnuma.schema import HistoryEntry, RateLine, shift_month

PROTECTED_LIMIT_KWH = 200
PROTECTED_LOOKBACK_MONTHS = 6


class UnknownRate(LookupError):
    """The schedule doesn't know the rate for the slab this bill needs."""


@dataclass(frozen=True)
class Band:
    upper: int | None          # None = no upper limit
    rate: Decimal | None       # None = not known for this schedule


@dataclass(frozen=True)
class Schedule:
    id: str
    tariff_prefix: str
    effective_from: date
    confidence: str
    source: str
    slab_benefit: str
    has_protected: bool
    unprotected: tuple[Band, ...]
    protected: tuple[Band, ...] = ()
    caveat: str | None = None


def _bands(raw: list) -> tuple[Band, ...]:
    return tuple(Band(u, Decimal(r) if r is not None else None) for u, r in raw)


@lru_cache(maxsize=1)
def load_schedules() -> tuple[Schedule, ...]:
    text = resources.files("rehnuma.data").joinpath("tariff_schedules.json").read_text("utf-8")
    out = []
    for s in json.loads(text)["schedules"]:
        out.append(Schedule(
            id=s["id"], tariff_prefix=s["tariff_prefix"],
            effective_from=date.fromisoformat(s["effective_from"]),
            confidence=s["confidence"], source=s["source"], slab_benefit=s["slab_benefit"],
            has_protected=s["has_protected"], unprotected=_bands(s["unprotected"]),
            protected=_bands(s.get("protected", [])), caveat=s.get("caveat"),
        ))
    return tuple(sorted(out, key=lambda x: x.effective_from))


def schedule_for(tariff: str, bill_month: str) -> Schedule | None:
    """Latest schedule for this tariff in force on the first day of the bill month."""
    year, mon = (int(p) for p in bill_month.split("-"))
    day = date(year, mon, 1)
    matches = [s for s in load_schedules()
               if tariff.startswith(s.tariff_prefix) and s.effective_from <= day]
    return matches[-1] if matches else None


def _band_index(bands: tuple[Band, ...], units: int) -> int:
    for i, band in enumerate(bands):
        if band.upper is None or units <= band.upper:
            return i
    raise ValueError(f"{units} units exceed every band")


def _rate(band: Band, schedule: Schedule) -> Decimal:
    if band.rate is None:
        raise UnknownRate(f"schedule {schedule.id} has no rate for band up to {band.upper}")
    return band.rate


def slab_rate_lines(units: int, schedule: Schedule, protected: bool) -> list[RateLine]:
    """The 'Bill Calculation' lines this consumer should have been charged."""
    if units <= 0:
        return []
    if protected and not schedule.has_protected:
        raise ValueError(f"schedule {schedule.id} has no protected category")
    bands = schedule.protected if protected else schedule.unprotected
    if protected and units > PROTECTED_LIMIT_KWH:
        bands = schedule.unprotected   # a protected consumer above 200 pays unprotected rates
        protected = False
    i = _band_index(bands, units)
    benefit = schedule.slab_benefit == "all" or (
        schedule.slab_benefit == "protected_only" and protected)
    if i == 0 or not benefit:
        return [RateLine(rate=_rate(bands[i], schedule), units=units)]
    prev_upper = bands[i - 1].upper
    return [RateLine(rate=_rate(bands[i - 1], schedule), units=prev_upper),
            RateLine(rate=_rate(bands[i], schedule), units=units - prev_upper)]


def protected_eligible(history: list[HistoryEntry], bill_month: str, tariff: str) -> bool | None:
    """True/False from the previous 6 months of history; None if history is incomplete.
    ToU tariffs (A-1b) can never be protected."""
    if not tariff.startswith("A-1a"):
        return False
    by_month = {h.month: h for h in history}
    lookback = range(1, PROTECTED_LOOKBACK_MONTHS + 1)
    rows = [by_month.get(shift_month(bill_month, -k)) for k in lookback]
    if any(r is None for r in rows):
        return None
    return all(r.units <= PROTECTED_LIMIT_KWH for r in rows)
