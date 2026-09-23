"""The result type every check returns."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class Finding:
    check: str
    status: Status
    message: str
    bill_id: str | None = None
    expected: Decimal | None = None
    actual: Decimal | None = None

    @property
    def delta(self) -> Decimal | None:
        if self.expected is None or self.actual is None:
            return None
        return self.actual - self.expected


def to_rupees(value: Decimal) -> int:
    """Round half-up to whole rupees/units (banker's rounding would be wrong here)."""
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compare(
    check: str,
    bill_id: str | None,
    expected: Decimal | int,
    actual: Decimal | int,
    tolerance: Decimal | int = 0,
    what: str = "",
) -> Finding:
    """PASS if |actual - expected| <= tolerance, otherwise FAIL."""
    exp, act = Decimal(expected), Decimal(actual)
    diff = act - exp
    ok = abs(diff) <= Decimal(tolerance)
    label = f"{what}: " if what else ""
    if diff == 0:
        msg = f"{label}expected {exp}, got {act}"
    elif ok:
        msg = f"{label}expected {exp}, got {act} (delta {diff:+}, within Rs {tolerance})"
    else:
        msg = f"{label}expected {exp}, got {act} (delta {diff:+})"
    return Finding(check, Status.PASS if ok else Status.FAIL, msg, bill_id, exp, act)


def skip(check: str, bill_id: str | None, reason: str) -> Finding:
    return Finding(check, Status.SKIP, reason, bill_id)
