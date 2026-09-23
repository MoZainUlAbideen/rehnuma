"""Typed schema for a Pakistani electricity bill.

One schema covers both user groups Rehnuma serves:
  * conventional households (no solar)  -> connection_type = "conventional"
  * solar prosumers (net metering)      -> connection_type = "net_metering"

and both PESCO layouts seen in real bills:
  * "pesco_legacy"   — the older PITC-style bill (seen up to Mar-2026)
  * "pesco_v2_2026"  — the redesigned bill with QR code (seen from Jul-2026)

Money is stored as whole rupees (int) because that is what the bill prints.
Meter readings are Decimal so subtraction never picks up float noise.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Layout(StrEnum):
    PESCO_LEGACY = "pesco_legacy"
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


class LegacyCharges(BaseModel):
    """Charge lines on the legacy PESCO layout.

    `govt` holds government-charge lines by key; keys ending in `_on_fpa`
    are the taxes levied on the fuel price adjustment.
    """

    units_consumed: int
    cost_of_electricity: int
    meter_rent: int = 0
    service_rent: int = 0
    fixed_charges: int = 0
    fpa: int = 0
    qta: int = 0
    pesco_total: int | None = None
    govt: dict[str, int] = Field(default_factory=dict)
    govt_total: int | None = None
    total_fpa: int = 0
    fpa_ref_month: str | None = Field(default=None, pattern=MONTH_PATTERN)
    fpa_units: int | None = None
    fpa_rate: Decimal | None = None


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
    units: int
    bill: int
    payment: int = 0


class Bill(BaseModel):
    bill_id: str
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
        if self.layout == Layout.PESCO_LEGACY and self.legacy_charges is None:
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
