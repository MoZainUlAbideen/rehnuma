"""Recompute bill lines from first principles.

Every function returns an UNROUNDED Decimal. Bills compute unrounded and round
only for display (seen on PESCO Mar-26 FPA and IESCO Mar-23 cost of electricity),
so callers round to the precision the bill prints, never earlier.

Rules below were derived from three IESCO bills (2019, 2021, 2023) and one PESCO
bill (2026), and every one is tested against them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from rehnuma.engine.taxes import NJ_SURCHARGE_PER_KWH, gst_rate
from rehnuma.schema import FpaPart, RateLine


def cost_of_electricity(lines: list[RateLine]) -> Decimal:
    """Sum of the 'Bill Calculation' block: rate x units per line."""
    return sum((ln.rate * ln.units for ln in lines), Decimal(0))


def electricity_duty(cost: Decimal, qta: Decimal, ed_rate_pct: Decimal) -> Decimal:
    """ED = rate x (cost of electricity + QTA). FC surcharge is NOT in the base."""
    return (cost + qta) * ed_rate_pct / 100


def gst_on_energy(cost: Decimal, fc_surcharge: Decimal, qta: Decimal, ed: Decimal,
                  bill_month: str) -> Decimal:
    """GST = rate(bill month) x (cost + FC surcharge + QTA + ED)."""
    return (cost + fc_surcharge + qta + ed) * gst_rate(bill_month)


def nj_surcharge(units: int) -> Decimal:
    return NJ_SURCHARGE_PER_KWH * units


@dataclass(frozen=True)
class FpaBreakdown:
    fpa: Decimal          # unrounded
    ed_on_fpa: Decimal    # unrounded
    gst_on_fpa: Decimal   # already rounded to whole rupees, per month
    total: Decimal        # unrounded sum


def fpa_breakdown(parts: list[FpaPart], ed_rate_pct: Decimal,
                  printed_fpa: Decimal | None = None) -> FpaBreakdown:
    """FPA and its taxes.

    * FPA per month = units of the reference month x that month's FPA rate.
    * ED on FPA = ED rate x FPA.
    * GST on FPA uses the GST rate of the FPA's *reference month* (IESCO Mar-23:
      Jan-23 FPA taxed at 17% while the rest of the bill used 18%) and is rounded to
      whole rupees *per month* (IESCO Jan-21: 6 + 8 = 14, single rounding gives 13).

    If a single part has no printed rate, the printed FPA amount is used instead.
    """
    if not parts:
        raise ValueError("no FPA parts")
    fpa_total = ed_total = gst_total = Decimal(0)
    for part in parts:
        if part.rate is not None:
            amount = part.rate * part.units
        elif len(parts) == 1 and printed_fpa is not None:
            amount = printed_fpa
        else:
            raise ValueError(f"FPA rate missing for {part.ref_month}")
        ed = amount * ed_rate_pct / 100
        gst = ((amount + ed) * gst_rate(part.ref_month)).quantize(Decimal(1), ROUND_HALF_UP)
        fpa_total += amount
        ed_total += ed
        gst_total += gst
    return FpaBreakdown(fpa_total, ed_total, gst_total, fpa_total + ed_total + gst_total)
