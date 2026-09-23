"""Constants the engine relies on.

Every value here says where it came from. Anything marked INFERRED was fitted to
real bills and must be confirmed against NEPRA / FBR sources in milestone 2.
"""

from decimal import Decimal

# Bills print whole rupees; we observed Rs 1 rounding gaps on real PESCO bills
# (e.g. Jul-2026: 2,687 + 484 = 3,171 but current bill printed as 3,170).
AMOUNT_TOLERANCE_RS = Decimal("1")

# INFERRED from the Mar-2026 PESCO bill: GST applied on (FPA + ED on FPA) at 18%
# reproduces the printed total FPA of Rs 1,164 exactly. Confirm in milestone 2.
GST_RATE = Decimal("0.18")
