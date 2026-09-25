"""Next-12-months units, from the household's own bill history.

Every bill prints the last 12 months of units, so "the same month last year" is always
known. That is the forecast. No trend or level adjustment: nothing in our data can show
whether one helps (see docs/FORECAST.md), and an unmeasured adjustment is a guess.

Why the household's OWN months and not a national seasonal profile: on our three IESCO
households, two peak in summer (air-conditioning) and correlate 0.89, while the third
peaks in winter (Dec-Feb, likely electric heating) and correlates -0.49 with both. A
shared profile would forecast that household backwards.

The range for each month is the lowest and highest of last year's month and its two
neighbours: a hot spell or a wedding a few weeks earlier or later moves units between
adjacent months, and the range says so instead of pretending to precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rehnuma.schema import Bill, ConnectionType, shift_month

HORIZON = 12


@dataclass(frozen=True)
class UnitForecast:
    month: str
    units: int          # same month last year
    low: int            # min of last year's month -1, month, month +1
    high: int           # max of the same three


def current_units(bill: Bill) -> int | None:
    """Units consumed on this bill (conventional meters only)."""
    if bill.connection_type != ConnectionType.CONVENTIONAL:
        return None
    if bill.legacy_charges is not None:
        return int(bill.legacy_charges.units_consumed)
    imports = [r.units for r in bill.registers if r.name.startswith("import")]
    return sum(imports) if imports else None


def monthly_units(bill: Bill) -> dict[str, int]:
    """Month -> units: the printed 12-month history plus this bill's own month."""
    series = {h.month: int(Decimal(h.units).to_integral_value()) for h in bill.history}
    now = current_units(bill)
    if now is not None:
        series[bill.bill_month] = now
    return series


def forecast_units(series: dict[str, int], last_month: str,
                   horizon: int = HORIZON) -> list[UnitForecast]:
    """Forecast the `horizon` months after `last_month` from `series`."""
    out = []
    for h in range(1, horizon + 1):
        month = shift_month(last_month, h)
        ref = shift_month(month, -12)
        if ref not in series:
            raise ValueError(f"no units for {ref}: need 12 months of history")
        around = [series[m] for m in (shift_month(ref, -1), ref, shift_month(ref, 1))
                  if m in series]
        out.append(UnitForecast(month, series[ref], min(around), max(around)))
    return out
