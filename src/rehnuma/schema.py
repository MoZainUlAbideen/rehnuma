"""Typed schema for a Pakistani electricity bill.

One schema covers both user groups Rehnuma serves:
  * conventional households (no solar)  -> connection_type = "conventional"
  * solar prosumers (net metering)      -> connection_type = "net_metering"

and the layouts seen in real bills:
  * "pitc_legacy"    — the PITC-generated bill shared by ex-WAPDA DISCOs
                       (seen on IESCO 2019-2023 and PESCO up to Mar-2026)
  * "pesco_v2_2026"  — PESCO's redesigned bill with QR code (seen from Jul-2026)

Charge lines are Decimal because legacy bills print paisa (e.g. 1,652.60) while
newer bills print whole rupees; the engine compares at the precision printed.
Totals the consumer pays are whole rupees (int).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Layout(StrEnum):
    PITC_LEGACY = "pitc_legacy"
    PESCO_V2_2026 = "pesco_v2_2026"


class ConnectionType(StrEnum):
    CONVENTIONAL = "conventional"
    NET_METERING = "net_metering"


class Source(StrEnum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class Register(BaseModel):
    """One meter register row. Names: import / import_offpeak / import_peak /
    export_offpeak / export_peak."""

    name: str
    previous: Decimal
    present: Decimal
    mf: Decimal = Decimal(1)
    units: int


class Tou(BaseModel):
    """A value split into off-peak / peak time-of-use slots."""

    offpeak: int
    peak: int

    @property
    def total(self) -> int:
        return self.offpeak + self.peak


class NetMetering(BaseModel):
    """The net-metering box on the bill (import/export/net + banked units)."""

    dg_capacity_kw: Decimal | None = None
    import_kwh: Tou
    export_kwh: Tou
    net_kwh: Tou
    month_count: int = Field(ge=1)
    cycle_length: int = Field(default=3, ge=1)
    remaining_prev: Tou
    remaining_present: Tou

    @model_validator(mode="after")
    def _count_within_cycle(self) -> NetMetering:
        if self.month_count > self.cycle_length:
            raise ValueError("month_count cannot exceed cycle_length")
        return self


class FpaPart(BaseModel):
    """One month's fuel price adjustment. A bill can carry several
    (IESCO Jan-2021 charged FPA for both Oct-20 and Nov-20)."""

    ref_month: str = Field(pattern=MONTH_PATTERN)
    units: int
    rate: Decimal | None = None  # Rs/kWh; None when the bill doesn't print it


class RateLine(BaseModel):
    """One line of the printed 'Bill Calculation' block: rate x units."""

    rate: Decimal
    units: int


class LegacyCharges(BaseModel):
    """Charge lines on the PITC legacy layout.

    `govt` holds government-charge lines by key (electricity_duty, tv_fee, gst,
    nj_surcharge, ...). Keys ending in `_on_fpa` are the taxes levied on the FPA.
    """

    units_consumed: int
    cost_of_electricity: Decimal
    meter_rent: Decimal = Decimal(0)
    service_rent: Decimal = Decimal(0)
    fixed_charges: Decimal = Decimal(0)
    fpa: Decimal = Decimal(0)
    fc_surcharge: Decimal = Decimal(0)
    tr_surcharge: Decimal = Decimal(0)
    qta: Decimal = Decimal(0)
    disco_total: Decimal | None = None
    govt: dict[str, Decimal] = Field(default_factory=dict)
    govt_total: Decimal | None = None
    total_fpa: Decimal = Decimal(0)
    fpa_parts: list[FpaPart] = Field(default_factory=list)
    rate_lines: list[RateLine] = Field(default_factory=list)


class V2Charges(BaseModel):
    """'Bill Charges Breakdown' block on the 2026 PESCO layout."""

    total_electricity_charges: int
    subsidies: int = 0
    net_electricity_charges: int
    taxes: int


class Totals(BaseModel):
    arrears: int
    current_bill: int
    installment: int = 0
    adjustments: int = 0
    payable_within_due: int
    lp_surcharge: int = 0
    payable_after_due: int


class HistoryEntry(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    status: str | None = None
    units: Decimal  # usually whole units, but IESCO printed "LK 337.5" once
    bill: int
    payment: int = 0


class Bill(BaseModel):
    bill_id: str
    connection_id: str | None = None  # pseudonymous id of the household/meter
    source: Source
    disco: str
    layout: Layout
    connection_type: ConnectionType
    tariff: str
    sanctioned_load_kw: Decimal | None = None
    bill_month: str = Field(pattern=MONTH_PATTERN)
    reading_date: date | None = None
    issue_date: date | None = None
    due_date: date | None = None
    ed_rate_pct: Decimal | None = None
    registers: list[Register] = Field(default_factory=list)
    net_metering: NetMetering | None = None
    legacy_charges: LegacyCharges | None = None
    v2_charges: V2Charges | None = None
    totals: Totals
    history: list[HistoryEntry] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _layout_and_connection_consistency(self) -> Bill:
        if self.layout == Layout.PITC_LEGACY and self.legacy_charges is None:
            raise ValueError("legacy layout requires legacy_charges")
        if self.layout == Layout.PESCO_V2_2026 and self.v2_charges is None:
            raise ValueError("pesco_v2_2026 layout requires v2_charges")
        if self.connection_type == ConnectionType.NET_METERING and self.net_metering is None:
            raise ValueError("net_metering connection requires the net_metering block")
        if self.connection_type == ConnectionType.CONVENTIONAL and self.net_metering is not None:
            raise ValueError("conventional connection must not have a net_metering block")
        return self

    # --- convenience -----------------------------------------------------
    def register(self, name: str) -> Register | None:
        return next((r for r in self.registers if r.name == name), None)

    def history_for(self, month: str) -> HistoryEntry | None:
        return next((h for h in self.history if h.month == month), None)


# --- month helpers -----------------------------------------------------------
def shift_month(month: str, delta: int) -> str:
    """shift_month('2026-01', -1) -> '2025-12'"""
    year, mon = (int(p) for p in month.split("-"))
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"