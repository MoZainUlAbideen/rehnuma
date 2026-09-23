"""Constants the engine relies on. Time-varying tax rates live in taxes.py."""

from decimal import Decimal

# Bills print whole rupees; we observed Rs 1 rounding gaps on real PESCO bills
# (e.g. Jul-2026: 2,687 + 484 = 3,171 but current bill printed as 3,170).
AMOUNT_TOLERANCE_RS = Decimal("1")