"""Tax and levy rates that change over time.

Each entry cites its source. INFERRED values were fitted to real bills and still
need an official source before Rehnuma quotes them to a user.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

# General Sales Tax on electricity, by effective date.
#   17% from Jul-2013 (Finance Act 2013)                          -- verify exact date
#   18% from 14-Feb-2023 (Finance (Supplementary) Act 2023)
# Real-bill evidence: IESCO Jul-19 / Jan-21 fit 17%, IESCO Mar-23 energy GST fits 18%,
# PESCO Mar-26 fits 18%.
GST_SCHEDULE: list[tuple[date, Decimal]] = [
    (date(2013, 7, 1), Decimal("0.17")),
    (date(2023, 2, 14), Decimal("0.18")),
]

# INFERRED: Neelum-Jhelum surcharge, Rs 0.10/kWh. Present on IESCO 2019 and 2021 bills,
# absent on 2023+ bills, so it is only checked when the bill prints the line.
NJ_SURCHARGE_PER_KWH = Decimal("0.10")


def gst_rate(month: str) -> Decimal:
    """GST rate in force on the first day of `month` ('YYYY-MM').
    Note: Feb-2023 resolves to 17% because the change came mid-month."""
    year, mon = (int(p) for p in month.split("-"))
    day = date(year, mon, 1)
    applicable = [rate for start, rate in GST_SCHEDULE if start <= day]
    if not applicable:
        raise ValueError(f"no GST rate known for {month}")
    return applicable[-1]
